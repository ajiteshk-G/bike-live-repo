import glob
import os
import shutil

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.services import brand_service as brand_service_module
from app.services.brand_service import BrandService
from app.services.cache_service import cache

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

REAL_BRANDS_DIR = brand_service_module.DATA_DIR

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False
)


@pytest.fixture(autouse=True)
def isolated_brand_catalogs(tmp_path, monkeypatch):
    """Runs every test against a temp COPY of data/brands so the real crawled catalogs are never mutated."""
    brands_dir = tmp_path / "brands"
    brands_dir.mkdir()
    for f in glob.glob(os.path.join(REAL_BRANDS_DIR, "*.json")):
        shutil.copy(f, brands_dir)
    uploads_dir = tmp_path / "uploads"
    uploads_dir.mkdir()
    monkeypatch.setattr(brand_service_module, "DATA_DIR", str(brands_dir))
    monkeypatch.setattr("app.routers.brand.STATIC_UPLOAD_DIR", str(uploads_dir), raising=False)
    monkeypatch.setattr(BrandService, "_active_brand_id", "tvs")
    BrandService.initialize(force_reload=True)
    if BrandService.get_brand("tvs"):
        BrandService.set_active_brand("tvs")
    cache.invalidate()
    yield brands_dir
    cache.invalidate()
    BrandService._initialized = False


@pytest_asyncio.fixture(scope="function")
async def db_session():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # No synthetic customers are seeded: tests register riders explicitly via /customer/identify.
    async with TestingSessionLocal() as session:
        yield session
        await session.rollback()

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


async def register_rider(client, name="Priya Patel", phone="+91 98765 43210", vehicle_id="tvs_apache_rtr_160_4v", brand_id=None):
    """Registers a rider through the public API (the only way customers get created)."""
    payload = {"name": name, "phone": phone, "session_type": "LIVE_CALL", "vehicle_id": vehicle_id}
    if brand_id:
        payload["brand_id"] = brand_id
    res = await client.post("/api/customer/identify", json=payload)
    assert res.status_code == 200, res.text
    return res.json()

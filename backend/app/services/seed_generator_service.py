"""
Brand onboarding seed generator (two-wheeler edition).

When a new two-wheeler brand is onboarded, this service only ensures that the brand
has a couple of generic demo "Authorised Dealer" showrooms in the `dealerships`
table so bookings / slot lookup work immediately.

It deliberately does NOT create customers, bookings, test-ride recordings,
transcripts or outbound call logs: the demo DB must contain no synthetic users
or fabricated PII. Real rows are created only from genuine user interactions.
"""
import logging
import re
from typing import Optional, List, Dict, Any

from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dealership import Dealership
from app.schemas.brand import BrandCatalog, VehicleItem
from app.database import AsyncSessionLocal

logger = logging.getLogger("seed_generator_service")

# Generic demo showroom templates (city, state, area, address, PIN, STD code prefix)
GENERIC_SHOWROOM_TEMPLATES = [
    ("Mumbai", "Maharashtra", "Andheri West", "Veera Desai Road, Near Azad Nagar Metro, Andheri West, Mumbai", "400053", "+91 22 4000"),
    ("Bengaluru", "Karnataka", "Koramangala", "80 Feet Road, 4th Block, Koramangala, Bengaluru", "560034", "+91 80 4000"),
    ("Delhi", "Delhi", "Lajpat Nagar", "Ring Road, Lajpat Nagar IV, New Delhi", "110024", "+91 11 4000"),
]


def _brand_display_name(brand_or_id: Any) -> str:
    if isinstance(brand_or_id, str):
        return brand_or_id.replace("_", " ").title()
    return re.sub(r"\s*\(.*?\)", "", getattr(brand_or_id, "name", "") or "").strip() or brand_or_id.id.title()


class SeedGeneratorService:
    @classmethod
    async def seed_data_for_brand(cls, db: AsyncSession, brand: BrandCatalog) -> Dict[str, Any]:
        """Ensures demo dealerships exist for a newly onboarded brand. No customer data is generated."""
        b_id = brand.id.lower()
        logger.info(f"Ensuring demo dealerships for onboarded brand: {brand.name} ({b_id})")
        try:
            dealerships = await cls.ensure_dealerships_for_brand(db, brand)
            await db.commit()
            return {
                "brand_id": b_id,
                "dealerships_count": len(dealerships),
                "vehicles_seeded": 0,
                "details": [],
            }
        except Exception as e:
            await db.rollback()
            logger.error(f"Dealership seed failed for brand {brand.name}: {e}", exc_info=True)
            raise e

    @classmethod
    async def seed_data_for_brand_background(cls, brand: BrandCatalog):
        """Runs dealership seeding in a dedicated background session without blocking the HTTP response."""
        try:
            async with AsyncSessionLocal() as db:
                await cls.seed_data_for_brand(db, brand)
        except Exception as e:
            logger.warning(f"Background dealership seed notice for brand '{brand.name}': {e}")

    @classmethod
    async def seed_data_for_vehicle(
        cls,
        db: AsyncSession,
        brand_or_id: Any,
        vehicle: VehicleItem,
        default_dealerships: Optional[List[Dealership]] = None
    ) -> Dict[str, Any]:
        """Previously generated synthetic customers / bookings / recordings per vehicle.

        Now intentionally a no-op apart from making sure the brand has dealerships, so that
        adding a vehicle never fabricates users or PII.
        """
        if not default_dealerships:
            await cls.ensure_dealerships_for_brand(db, brand_or_id)
        return {
            "vehicle_id": vehicle.id.lower(),
            "vehicle_name": vehicle.name,
            "status": "skipped_no_synthetic_data",
        }

    @classmethod
    async def ensure_dealerships_for_brand(cls, db: AsyncSession, brand_or_id: Any) -> List[Dealership]:
        """Ensures at least 2 generic demo two-wheeler dealerships exist in the database for the brand."""
        b_id = (brand_or_id if isinstance(brand_or_id, str) else brand_or_id.id).lower()
        b_name = _brand_display_name(brand_or_id)

        res = await db.execute(select(Dealership).where(Dealership.brand_id == b_id))
        existing = list(res.scalars().all())
        if len(existing) >= 2:
            return existing

        created = list(existing)
        existing_ids = {d.id for d in existing}

        # 1. Prefer dealerships declared in the brand catalog JSON
        if not isinstance(brand_or_id, str):
            for d_item in getattr(brand_or_id, "dealerships", None) or []:
                d_id = getattr(d_item, "id", None) or f"{b_id}_{getattr(d_item, 'city', 'mumbai').lower()}"
                if d_id in existing_ids:
                    continue
                r = await db.execute(select(Dealership).where(Dealership.id == d_id))
                if r.scalars().first():
                    continue
                city = getattr(d_item, "city", None) or "Mumbai"
                tpl = next((t for t in GENERIC_SHOWROOM_TEMPLATES if t[0].lower() == city.lower()), GENERIC_SHOWROOM_TEMPLATES[0])
                d_row = Dealership(
                    id=d_id,
                    brand_id=b_id,
                    name=getattr(d_item, "name", None) or f"{b_name} Authorised Dealer – {tpl[2]}",
                    city=city,
                    state=tpl[1],
                    area=tpl[2],
                    address=getattr(d_item, "address", None) or tpl[3],
                    pin_code=tpl[4],
                    phone=getattr(d_item, "phone", None) or f"{tpl[5]} 9{len(created):03d}",
                    email=f"{d_id.replace('_', '.')}@dealer-demo.in",
                    rating=getattr(d_item, "rating", None) or 4.7,
                    available_advisors=getattr(d_item, "available_advisors", None) or ["Rahul Nair (Sales Consultant)"],
                    is_active=True,
                )
                db.add(d_row)
                created.append(d_row)
                existing_ids.add(d_id)

        # 2. Fill up with generic templates
        for city, state, area, address, pin, std in GENERIC_SHOWROOM_TEMPLATES:
            if len(created) >= 2:
                break
            d_id = f"{b_id}_{city.lower()}_{area.lower().replace(' ', '_')}"
            if d_id in existing_ids:
                continue
            r = await db.execute(select(Dealership).where(Dealership.id == d_id))
            if r.scalars().first():
                continue
            d_row = Dealership(
                id=d_id,
                brand_id=b_id,
                name=f"{b_name} Authorised Dealer – {area}",
                city=city,
                state=state,
                area=area,
                address=address,
                pin_code=pin,
                phone=f"{std} 9{len(created):03d}",
                email=f"{d_id.replace('_', '.')}@dealer-demo.in",
                rating=4.7,
                available_advisors=["Rahul Nair (Sales Consultant)", "Priya Menon (Product Specialist)"],
                is_active=True,
            )
            db.add(d_row)
            created.append(d_row)
            existing_ids.add(d_id)

        await db.flush()
        return created

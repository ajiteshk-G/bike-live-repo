import io

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.brand_service import BrandService

client = TestClient(app)

CAR_BRAND_IDS = {"mahindra", "bmw", "hyundai", "maruti_suzuki", "cymbal"}


def test_list_brands_only_two_wheelers():
    response = client.get("/api/brands")
    assert response.status_code == 200
    brand_ids = {b["id"] for b in response.json()}
    assert "tvs" in brand_ids
    assert not (brand_ids & CAR_BRAND_IDS)


def test_get_active_brand_defaults_to_tvs():
    response = client.get("/api/brands/active")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "tvs"
    assert len(data["vehicles"]) > 0


def test_switch_brand_and_dynamic_catalog():
    if not BrandService.get_brand("hero_motocorp"):
        pytest.skip("hero_motocorp catalog not crawled yet")
    switch_res = client.post("/api/brands/active", json={"brand_id": "hero_motocorp"})
    assert switch_res.status_code == 200
    assert switch_res.json()["id"] == "hero_motocorp"
    v_ids = [v["id"] for v in client.get("/api/catalog").json()]
    assert v_ids and all(not vid.startswith("tvs_") for vid in v_ids)

    switch_back = client.post("/api/brands/active", json={"brand_id": "tvs"})
    assert switch_back.status_code == 200
    v_ids2 = [v["id"] for v in client.get("/api/catalog").json()]
    assert "tvs_apache_rtr_160_4v" in v_ids2


def test_switch_to_unknown_brand_fails():
    res = client.post("/api/brands/active", json={"brand_id": "mahindra"})
    assert res.status_code in (400, 404)


def test_vehicle_edit_and_source_of_truth():
    update_res = client.put(
        "/api/brands/tvs/vehicles/tvs_apache_rtr_160_4v",
        json={"tagline": "Custom Verified Source of Truth Tagline", "price_range": "₹1,20,000"},
    )
    assert update_res.status_code == 200
    updated_v = update_res.json()
    assert updated_v["tagline"] == "Custom Verified Source of Truth Tagline"
    assert updated_v["price_range"] == "₹1,20,000"
    assert updated_v["is_custom_source_of_truth"] is True


def test_upload_vehicle_image_source_of_truth():
    fake_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    response = client.post(
        "/api/brands/tvs/upload-vehicle-image",
        data={"vehicle_id": "tvs_iqube"},
        files={"image": ("iqube_user_upload.png", io.BytesIO(fake_png), "image/png")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_custom_source_of_truth"] is True
    assert "/uploads/tvs/vehicles/" in data["hero_image"]


def test_missing_brand_json_does_not_crash(isolated_brand_catalogs):
    for f in isolated_brand_catalogs.glob("*.json"):
        if f.stem != "tvs":
            f.unlink()
    BrandService.initialize(force_reload=True)
    assert BrandService.get_brand("hero_motocorp") is None
    assert BrandService.get_active_brand().id == "tvs"
    assert client.get("/api/brands").status_code == 200

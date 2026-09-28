import pytest

BIKE_CATEGORIES = {
    "Commuter Motorcycle", "Premium Commuter", "Sports Motorcycle", "Naked Streetfighter", "Supersport",
    "Adventure Tourer", "Cruiser / Retro", "Scooter", "Performance Scooter", "Electric Scooter",
    "Electric Motorcycle", "Moped",
}

@pytest.mark.asyncio
async def test_list_all_vehicles(client):
    response = await client.get("/api/catalog")
    assert response.status_code == 200
    vehicles = response.json()
    assert len(vehicles) >= 5
    ids = [v["id"] for v in vehicles]
    assert "tvs_apache_rtr_160_4v" in ids
    assert "tvs_iqube" in ids
    for v in vehicles:
        assert v["category"] in BIKE_CATEGORIES
        assert v["seating_capacity"] in ("Rider + Pillion", "Single Seat", "Rider Only")

@pytest.mark.asyncio
async def test_get_vehicle_detail(client):
    response = await client.get("/api/catalog/tvs_apache_rtr_160_4v")
    assert response.status_code == 200
    data = response.json()
    assert "Apache RTR 160" in data["name"]
    assert len(data["variants"]) >= 2
    assert data["displacement_cc"]
    assert "ABS" in (data["braking"] or "") or "ABS" in str(data["key_highlights"])

@pytest.mark.asyncio
async def test_unknown_vehicle_404(client):
    response = await client.get("/api/catalog/thar_roxx")
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_compare_vehicles(client):
    response = await client.post("/api/catalog/compare", json={"vehicle_ids": ["tvs_apache_rtr_160_4v", "tvs_iqube"]})
    assert response.status_code == 200
    compared = response.json()
    assert [c["id"] for c in compared] == ["tvs_apache_rtr_160_4v", "tvs_iqube"]

@pytest.mark.asyncio
async def test_compare_specs_matrix(client):
    response = await client.post("/api/catalog/compare-specs", json={"vehicle_ids": ["tvs_apache_rtr_160_4v", "tvs_apache_rtr_200_4v"]})
    assert response.status_code == 200
    data = response.json()
    assert len(data["vehicles"]) == 2
    labels = [r["label"] for r in data["rows"]]
    assert "Max Power" in labels and "Braking & ABS" in labels
    assert all(len(r["values"]) == 2 for r in data["rows"])

@pytest.mark.asyncio
async def test_emi_estimate_two_wheeler_bounds(client):
    response = await client.get("/api/catalog/tvs_apache_rtr_160_4v/emi?down_payment_pct=5&tenure_months=84")
    assert response.status_code == 200
    q = response.json()
    assert q["down_payment_pct"] == 10.0  # clamped to 10-25%
    assert q["tenure_months"] == 48       # clamped to 12-48 months
    assert 0 < q["monthly_emi"] < q["loan_amount"]
    assert [t["tenure_months"] for t in q["tenure_options"]] == [12, 18, 24, 36, 48]

@pytest.mark.asyncio
async def test_dealerships(client):
    response = await client.get("/api/catalog/dealerships?brand_id=tvs")
    assert response.status_code == 200
    dealers = response.json()
    assert len(dealers) >= 1
    assert all("Mahindra" not in d["name"] for d in dealers)
    assert any("TVS" in d["name"] for d in dealers)

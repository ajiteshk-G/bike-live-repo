import pytest

@pytest.mark.asyncio
async def test_health_endpoint(client):
    response = await client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "Two-Wheeler" in data["service"]
    assert "Mahindra" not in data["service"]

@pytest.mark.asyncio
async def test_root_endpoint(client):
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "Two-Wheeler" in data["app"]
    assert data["active_brand"]["id"] == "tvs"

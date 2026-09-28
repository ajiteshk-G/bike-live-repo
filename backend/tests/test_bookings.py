import pytest
from tests.conftest import register_rider


@pytest.mark.asyncio
async def test_create_test_ride_booking(client):
    payload = {
        "customer_phone": "+91 98200 33344",
        "customer_name": "Rohan Patil",
        "vehicle_id": "tvs_apache_rtr_160_4v",
        "variant": "Dual Channel ABS",
        "color": "Racing Red",
        "booking_type": "HOME_DOORSTEP",
        "delivery_address": "Veera Desai Road, Andheri West",
        "scheduled_date": "Tomorrow",
        "scheduled_time_slot": "05:00 PM",
        "notes": "Customer wants to check ABS and seat height",
        "brand_id": "tvs",
    }
    response = await client.post("/api/bookings", json=payload)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["booking_reference"].startswith("BK-TVS")
    assert "TVS" in data["dealership_name"]
    assert "Mahindra" not in data["dealership_name"]
    assert data["status"] == "CONFIRMED"


@pytest.mark.asyncio
async def test_booking_unknown_customer_without_phone_is_404(client):
    response = await client.post("/api/bookings", json={
        "customer_id": "CUST-DOES-NOT-EXIST",
        "vehicle_id": "tvs_iqube",
        "variant": "Standard",
        "scheduled_date": "Tomorrow",
        "scheduled_time_slot": "11:00 AM",
    })
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_customer_bookings(client):
    rider = await register_rider(client, name="Meera Iyer", phone="+91 98200 55566", vehicle_id="tvs_iqube")
    await client.post("/api/bookings", json={
        "customer_id": rider["customer_id"],
        "vehicle_id": "tvs_iqube",
        "variant": "Standard",
        "scheduled_date": "This Saturday",
        "scheduled_time_slot": "11:00 AM",
    })
    response = await client.get(f"/api/bookings/my-bookings?customer_id={rider['customer_id']}")
    assert response.status_code == 200
    assert len(response.json()) >= 1

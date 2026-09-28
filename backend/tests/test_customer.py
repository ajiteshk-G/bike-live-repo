import pytest
from tests.conftest import register_rider


@pytest.mark.asyncio
async def test_no_synthetic_default_customer(client):
    # Clean DB: no fabricated default customer is created on lookup.
    response = await client.get("/api/customer/profile?phone=+919820155432")
    assert response.status_code == 200
    assert response.json() is None

    patch = await client.patch("/api/customer/profile", json={"city": "Pune"})
    assert patch.status_code == 404
    phase = await client.post("/api/customer/update-phase?phase=FINANCING")
    assert phase.status_code == 404


@pytest.mark.asyncio
async def test_get_customer_profile_after_identify(client):
    await register_rider(client, name="Sneha Kulkarni", phone="+91 98200 11122")
    response = await client.get("/api/customer/profile?phone=+919820011122")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Sneha Kulkarni"
    assert data["phone"] == "+919820011122"
    assert data["pan_number"] is None
    assert data["aadhaar_masked"] is None
    assert data["owned_vin"] is None
    assert data["interested_vehicle_id"] == "tvs_apache_rtr_160_4v"


@pytest.mark.asyncio
async def test_identify_new_and_returning_customer(client):
    data1 = await register_rider(client, name="Priya Patel", phone="+91 98765 43210", vehicle_id="tvs_iqube")
    assert data1["phone"] == "+919876543210"
    assert data1["is_returning"] is False
    assert data1["session_id"].startswith("SESS-")
    assert data1["past_session_count"] == 1
    session_id_1 = data1["session_id"]
    customer_id = data1["customer_id"]

    t_res1 = await client.post("/api/customer/transcript-turn", json={
        "session_id": session_id_1,
        "customer_id": customer_id,
        "speaker": "customer",
        "message": "iQube ki real-world range kitni hai? Budget around 1.2 lakh hai.",
        "extracted_intent": "VEHICLE_SPECS",
    })
    assert t_res1.status_code == 200

    data2 = await register_rider(client, name="Priya Patel", phone="9876543210", vehicle_id="tvs_apache_rtr_160_4v")
    assert data2["is_returning"] is True
    assert data2["session_id"] != session_id_1
    assert data2["past_session_count"] == 2

    sess_res = await client.get(f"/api/customer/sessions?customer_id={customer_id}")
    assert sess_res.status_code == 200
    session_ids = [s["session_id"] for s in sess_res.json()]
    assert session_id_1 in session_ids and data2["session_id"] in session_ids


@pytest.mark.asyncio
async def test_regex_validation_errors(client):
    res_bad_name = await client.post("/api/customer/identify", json={"name": "Rider123", "phone": "9820155432"})
    assert res_bad_name.status_code == 422
    res_bad_phone = await client.post("/api/customer/identify", json={"name": "Rahul Nair", "phone": "12345"})
    assert res_bad_phone.status_code == 422


def test_conversation_intelligence_two_wheeler():
    from app.services.customer_service import extract_conversation_intelligence
    intel = extract_conversation_intelligence([
        {"speaker": "customer", "text": "Apache RTR 200 lena hai, budget 1.5 lakh. ABS aur seat height kaisi hai? Wife pillion baithegi."},
        {"speaker": "ai", "text": "Jupiter bhi dekh sakte hain."},
    ])
    assert intel["primary_vehicle_id"] == "tvs_apache_rtr_200_4v"
    assert "ABS & Braking Confidence" in intel["interested_features"]
    assert "Seat Height & Rider Fit" in intel["interested_features"]
    assert "Pillion Comfort" in intel["interested_features"]
    assert "1,50,000" in intel["budget"]


def test_budget_extraction_ranges():
    from app.services.customer_service import extract_budget
    assert extract_budget("between 80k to 1.2 lakh") == "₹80,000 – ₹1,20,000"
    assert "85,000" in extract_budget("under 85000")
    assert extract_budget("I like the 160cc model") is None

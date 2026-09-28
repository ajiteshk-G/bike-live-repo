import pytest
from httpx import AsyncClient
from tests.conftest import register_rider


@pytest.fixture(autouse=True)
def _no_real_gcs_upload(monkeypatch):
    """Never upload test audio to the real recordings bucket."""
    class _FailingStorageClient:
        def __init__(self, *a, **k):
            raise RuntimeError("GCS disabled in tests")
    monkeypatch.setattr("google.cloud.storage.Client", _FailingStorageClient, raising=False)


@pytest.mark.asyncio
async def test_upload_test_ride_recording_simulated(client: AsyncClient, monkeypatch):
    # Force the deterministic (offline) path: no Gemini call during tests.
    monkeypatch.setattr("app.services.genai_client.get_genai_client", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("offline")))
    rider = await register_rider(client, name="Karthik Reddy", phone="+91 98450 12345")
    payload = {
        "customer_id": rider["customer_id"],
        "customer_name": "Karthik Reddy",
        "vehicle_id": "tvs_apache_rtr_160_4v",
        "variant": "Dual Channel ABS",
        "sales_advisor_name": "Rahul Nair (Sales Consultant)",
        "simulated_scenario": "test_ride_simulation",
        "brand_id": "tvs",
    }
    resp = await client.post("/api/sales/test-ride/upload-recording", json=payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["session_id"].startswith("TR-2026-")
    assert "/test_rides/" in data["gcs_uri"] and data["gcs_uri"].startswith("gs://")
    assert data["customer_sentiment_score"] >= 0.8
    assert len(data["loved_features"]) > 0
    assert len(data["objections_raised"]) > 0
    assert "Rahul" in data["sales_advisor_name"]
    t = data["transcript"].lower()
    assert "abs" in t and "pillion" in t and "helmet" in t
    for car_word in ["sunroof", "airbag", "ncap", "cabin", "steering"]:
        assert car_word not in t
    assert "12 se 48 months" in data["transcript"]

    get_resp = await client.get(f"/api/sales/test-ride/insights/{data['session_id']}")
    assert get_resp.status_code == 200


@pytest.mark.asyncio
async def test_upload_recording_unknown_customer_404(client: AsyncClient):
    resp = await client.post("/api/sales/test-ride/upload-recording", json={"customer_id": "CUST-NOPE", "brand_id": "tvs"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_outbound_call_and_dialogue_turns(client: AsyncClient, monkeypatch):
    monkeypatch.setattr("app.services.genai_client.get_genai_client", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("offline")))
    rider = await register_rider(client, name="Ananya Rao", phone="+91 98450 67890", vehicle_id="tvs_iqube")
    resp = await client.post("/api/outbound/trigger-call", json={
        "customer_id": rider["customer_id"],
        "vehicle_name": "TVS iQube",
        "advisor_name": "Rahul Nair (Sales Consultant)",
        "brand_id": "tvs",
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    call_ref = body["call_reference"]
    assert call_ref.startswith("CALL-")
    assert body["phone_number"] == "+919845067890"

    turn_resp = await client.post("/api/outbound/dialogue-turn", json={
        "call_reference": call_ref,
        "customer_speech": "Pickup aur braking bahut achha tha! But range aur loan EMI ka doubt hai.",
        "turn_index": 0,
    })
    assert turn_resp.status_code == 200
    assert "Kavya" in turn_resp.json()["speaker"]

    insights_resp = await client.get(f"/api/outbound/call-insights/{call_ref}")
    assert insights_resp.status_code == 200
    insights = insights_resp.json()
    assert insights["objection_resolution_status"].startswith("100%")
    assert insights["customer_name"] == "Ananya Rao"


@pytest.mark.asyncio
async def test_outbound_call_unknown_customer_404(client: AsyncClient):
    resp = await client.post("/api/outbound/trigger-call", json={"customer_id": "CUST-NOPE", "brand_id": "tvs"})
    assert resp.status_code == 404


def test_two_wheeler_emi_math():
    from app.services.financing_service import estimate_two_wheeler_emi, monthly_emi
    q = estimate_two_wheeler_emi(100000, down_payment_pct=20, tenure_months=24, annual_rate_pct=12)
    assert q["down_payment"] == 20000 and q["loan_amount"] == 80000
    assert q["monthly_emi"] == monthly_emi(80000, 12, 24) == 3766

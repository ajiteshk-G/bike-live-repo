"""Checks the (voice-worker owned) ChecklistService behaves for two-wheelers and feeds sales leads."""
import pytest
from app.services.checklist_service import ChecklistService
from tests.conftest import register_rider

CAR_TERMS = ["sunroof", "skyroof", "adas", "airbag", "fsd", "4xplor", "harman"]


def _no_car_terms(items):
    joined = " ".join(items).lower()
    return not any(t in joined for t in CAR_TERMS)


@pytest.mark.asyncio
async def test_static_two_wheeler_checklists():
    apache = ChecklistService.get_static_checklist("tvs_apache_rtr_160_4v")
    assert len(apache) >= 3
    assert _no_car_terms(apache)
    assert any("abs" in i.lower() or "brak" in i.lower() for i in apache)

    iqube = ChecklistService.get_static_checklist("tvs_iqube")
    assert len(iqube) >= 3
    assert any(k in " ".join(iqube).lower() for k in ["range", "charg", "battery"])

    unknown = ChecklistService.get_static_checklist("unknown_bike")
    assert len(unknown) >= 3
    assert _no_car_terms(unknown)


@pytest.mark.asyncio
async def test_dynamic_feature_extraction_from_customer_asks():
    q1 = "How is the ABS braking and is there Bluetooth navigation on the TFT?"
    e1 = ChecklistService.extract_checklist_items(q1, vehicle_id="tvs_apache_rtr_160_4v")
    assert len(e1) >= 2
    assert _no_car_terms(e1)

    q2 = "What is the real range and how long does home charging take?"
    e2 = ChecklistService.extract_checklist_items(q2, vehicle_id="tvs_iqube")
    assert any(k in " ".join(e2).lower() for k in ["range", "charg"])


@pytest.mark.asyncio
async def test_presales_booking_persists_checklist_and_leads(client):
    rider = await register_rider(client, name="Vikram Singh", phone="+91 98110 22233")
    await client.post("/api/customer/transcript-turn", json={
        "session_id": rider["session_id"],
        "customer_id": rider["customer_id"],
        "speaker": "customer",
        "message": "Apache RTR 160 ka ABS, riding modes aur seat height check karna hai.",
    })
    book_resp = await client.post("/api/bookings", json={
        "customer_id": rider["customer_id"],
        "vehicle_id": "tvs_apache_rtr_160_4v",
        "variant": "Dual Channel ABS",
        "scheduled_date": "Tomorrow",
        "scheduled_time_slot": "04:00 PM",
        "notes": "Wants to test ABS and riding modes",
        "brand_id": "tvs",
    })
    assert book_resp.status_code == 200, book_resp.text

    leads_resp = await client.get("/api/sales/leads?dealership_id=ALL&brand_id=tvs")
    assert leads_resp.status_code == 200
    lead = next((l for l in leads_resp.json() if l["customer_id"] == rider["customer_id"]), None)
    assert lead is not None
    assert lead["advisor_checklist"]
    assert lead["is_custom_checklist"] is True

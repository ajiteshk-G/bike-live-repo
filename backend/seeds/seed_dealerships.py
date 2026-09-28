"""
Re-runnable seed for the TWO-WHEELER dealership demo (TVS Motor + Hero MotoCorp).

Seeds brand-agnostic public holidays + test-ride slot timings, and generic
demo "Authorised Dealer" showrooms for the `tvs` and `hero_motocorp` brands.

It NEVER seeds customers, bookings, recordings, transcripts or any PII.

Usage:
    PYTHONPATH=. .venv/bin/python seeds/seed_dealerships.py            # upsert only
    PYTHONPATH=. .venv/bin/python seeds/seed_dealerships.py --purge    # also delete legacy car-brand rows
"""
import os
import sys
import asyncio
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from sqlalchemy.future import select
from sqlalchemy import text
from app.database import AsyncSessionLocal, db_url as _db_url
from app.models.dealership import Dealership
from app.models.booking import PublicHoliday, SlotConfig

logger = logging.getLogger("seed_dealerships")

PUBLIC_HOLIDAYS_DATA = [
    {"date": "2026-01-26", "name": "Republic Day", "state": "ALL"},
    {"date": "2026-03-03", "name": "Holi (Festival of Colours)", "state": "ALL"},
    {"date": "2026-03-20", "name": "Eid-ul-Fitr", "state": "ALL"},
    {"date": "2026-04-14", "name": "Dr. Ambedkar Jayanti", "state": "ALL"},
    {"date": "2026-05-01", "name": "Maharashtra Day / May Day", "state": "Maharashtra"},
    {"date": "2026-08-15", "name": "Independence Day", "state": "ALL"},
    {"date": "2026-09-04", "name": "Janmashtami", "state": "ALL"},
    {"date": "2026-10-02", "name": "Mahatma Gandhi Jayanti", "state": "ALL"},
    {"date": "2026-10-20", "name": "Dussehra (Vijayadashami)", "state": "ALL"},
    {"date": "2026-11-08", "name": "Diwali (Deepavali)", "state": "ALL"},
    {"date": "2026-11-09", "name": "Govardhan Puja", "state": "ALL"},
    {"date": "2026-11-24", "name": "Guru Nanak Jayanti", "state": "ALL"},
    {"date": "2026-12-25", "name": "Christmas Day", "state": "ALL"}
]

SLOT_CONFIGS_DATA = [
    {"slot_time": "09:00 AM", "order": 1},
    {"slot_time": "10:00 AM", "order": 2},
    {"slot_time": "11:00 AM", "order": 3},
    {"slot_time": "12:00 PM", "order": 4},
    {"slot_time": "01:00 PM", "order": 5},
    {"slot_time": "02:00 PM", "order": 6},
    {"slot_time": "03:00 PM", "order": 7},
    {"slot_time": "04:00 PM", "order": 8},
    {"slot_time": "05:00 PM", "order": 9}
]

DEALERSHIPS_DATA = [{'id': 'tvs_mumbai_andheri',
  'brand_id': 'tvs',
  'name': 'TVS Motor Authorised Dealer – Andheri West',
  'city': 'Mumbai',
  'state': 'Maharashtra',
  'area': 'Andheri West',
  'address': 'Shop 4-6, Veera Desai Road, Near Azad Nagar Metro, Andheri West, Mumbai',
  'pin_code': '400053',
  'phone': '+91 22 4000 1101',
  'email': 'tvs.mumbai.andheri@dealer-demo.in',
  'map_url': 'https://maps.google.com/?q=TVS+Motor+Authorised+Dealer+Andheri+West',
  'rating': 4.7,
  'available_advisors': ['Rahul Nair (Sales Consultant)', 'Sneha Kulkarni (EV Specialist)']},
 {'id': 'tvs_pune_kothrud',
  'brand_id': 'tvs',
  'name': 'TVS Motor Authorised Dealer – Kothrud',
  'city': 'Pune',
  'state': 'Maharashtra',
  'area': 'Kothrud',
  'address': 'Plot 21, Paud Road, Near Kothrud Depot, Kothrud, Pune',
  'pin_code': '411038',
  'phone': '+91 20 4000 1102',
  'email': 'tvs.pune.kothrud@dealer-demo.in',
  'map_url': 'https://maps.google.com/?q=TVS+Motor+Authorised+Dealer+Kothrud',
  'rating': 4.6,
  'available_advisors': ['Aditya Joshi (Sales Consultant)', 'Priya Deshmukh (Product Specialist)']},
 {'id': 'tvs_bengaluru_indiranagar',
  'brand_id': 'tvs',
  'name': 'TVS Motor Authorised Dealer – Indiranagar',
  'city': 'Bengaluru',
  'state': 'Karnataka',
  'area': 'Indiranagar',
  'address': 'No. 312, 100 Feet Road, HAL 2nd Stage, Indiranagar, Bengaluru',
  'pin_code': '560038',
  'phone': '+91 80 4000 1103',
  'email': 'tvs.bengaluru.indiranagar@dealer-demo.in',
  'map_url': 'https://maps.google.com/?q=TVS+Motor+Authorised+Dealer+Indiranagar',
  'rating': 4.8,
  'available_advisors': ['Karthik Reddy (Performance Bikes Specialist)', 'Ananya Rao (EV Specialist)']},
 {'id': 'tvs_delhi_karol_bagh',
  'brand_id': 'tvs',
  'name': 'TVS Motor Authorised Dealer – Karol Bagh',
  'city': 'Delhi',
  'state': 'Delhi',
  'area': 'Karol Bagh',
  'address': '12/8, Pusa Road, Near Karol Bagh Metro Station, New Delhi',
  'pin_code': '110005',
  'phone': '+91 11 4000 1104',
  'email': 'tvs.delhi.karol.bagh@dealer-demo.in',
  'map_url': 'https://maps.google.com/?q=TVS+Motor+Authorised+Dealer+Karol+Bagh',
  'rating': 4.6,
  'available_advisors': ['Vikram Singh (Sales Consultant)', 'Neha Arora (Finance Advisor)']},
 {'id': 'tvs_chennai_anna_nagar',
  'brand_id': 'tvs',
  'name': 'TVS Motor Authorised Dealer – Anna Nagar',
  'city': 'Chennai',
  'state': 'Tamil Nadu',
  'area': 'Anna Nagar',
  'address': 'AE-45, 2nd Avenue, Anna Nagar, Chennai',
  'pin_code': '600040',
  'phone': '+91 44 4000 1105',
  'email': 'tvs.chennai.anna.nagar@dealer-demo.in',
  'map_url': 'https://maps.google.com/?q=TVS+Motor+Authorised+Dealer+Anna+Nagar',
  'rating': 4.8,
  'available_advisors': ['Arun Kumar (Sales Consultant)', 'Divya Subramanian (Product Specialist)']},
 {'id': 'tvs_hyderabad_kukatpally',
  'brand_id': 'tvs',
  'name': 'TVS Motor Authorised Dealer – Kukatpally',
  'city': 'Hyderabad',
  'state': 'Telangana',
  'area': 'Kukatpally',
  'address': 'Plot 7, JNTU–Hitech City Road, KPHB Colony, Kukatpally, Hyderabad',
  'pin_code': '500072',
  'phone': '+91 40 4000 1106',
  'email': 'tvs.hyderabad.kukatpally@dealer-demo.in',
  'map_url': 'https://maps.google.com/?q=TVS+Motor+Authorised+Dealer+Kukatpally',
  'rating': 4.7,
  'available_advisors': ['Srinivas Rao (Sales Consultant)', 'Lakshmi Prasanna (EV Specialist)']},
 {'id': 'hero_mumbai_ghatkopar',
  'brand_id': 'hero_motocorp',
  'name': 'Hero MotoCorp Authorised Dealer – Ghatkopar East',
  'city': 'Mumbai',
  'state': 'Maharashtra',
  'area': 'Ghatkopar East',
  'address': 'Unit 3, R.B. Mehta Marg, Near Ghatkopar Station, Ghatkopar East, Mumbai',
  'pin_code': '400077',
  'phone': '+91 22 4000 2201',
  'email': 'hero.mumbai.ghatkopar@dealer-demo.in',
  'map_url': 'https://maps.google.com/?q=Hero+MotoCorp+Authorised+Dealer+Ghatkopar+East',
  'rating': 4.6,
  'available_advisors': ['Rohan Patil (Sales Consultant)', 'Meera Iyer (Finance Advisor)']},
 {'id': 'hero_pune_hadapsar',
  'brand_id': 'hero_motocorp',
  'name': 'Hero MotoCorp Authorised Dealer – Hadapsar',
  'city': 'Pune',
  'state': 'Maharashtra',
  'area': 'Hadapsar',
  'address': 'S. No. 150, Pune–Solapur Road, Near Magarpatta Chowk, Hadapsar, Pune',
  'pin_code': '411028',
  'phone': '+91 20 4000 2202',
  'email': 'hero.pune.hadapsar@dealer-demo.in',
  'map_url': 'https://maps.google.com/?q=Hero+MotoCorp+Authorised+Dealer+Hadapsar',
  'rating': 4.7,
  'available_advisors': ['Saurabh Pawar (Sales Consultant)', 'Pooja Shinde (Product Specialist)']},
 {'id': 'hero_bengaluru_koramangala',
  'brand_id': 'hero_motocorp',
  'name': 'Hero MotoCorp Authorised Dealer – Koramangala',
  'city': 'Bengaluru',
  'state': 'Karnataka',
  'area': 'Koramangala',
  'address': 'No. 88, 80 Feet Road, 4th Block, Koramangala, Bengaluru',
  'pin_code': '560034',
  'phone': '+91 80 4000 2203',
  'email': 'hero.bengaluru.koramangala@dealer-demo.in',
  'map_url': 'https://maps.google.com/?q=Hero+MotoCorp+Authorised+Dealer+Koramangala',
  'rating': 4.8,
  'available_advisors': ['Rahul Nair (Sales Consultant)', 'Kavitha Gowda (Premium Motorcycles Specialist)']},
 {'id': 'hero_delhi_lajpat_nagar',
  'brand_id': 'hero_motocorp',
  'name': 'Hero MotoCorp Authorised Dealer – Lajpat Nagar',
  'city': 'Delhi',
  'state': 'Delhi',
  'area': 'Lajpat Nagar',
  'address': 'A-14, Ring Road, Lajpat Nagar IV, New Delhi',
  'pin_code': '110024',
  'phone': '+91 11 4000 2204',
  'email': 'hero.delhi.lajpat.nagar@dealer-demo.in',
  'map_url': 'https://maps.google.com/?q=Hero+MotoCorp+Authorised+Dealer+Lajpat+Nagar',
  'rating': 4.6,
  'available_advisors': ['Amit Sharma (Sales Consultant)', 'Ritu Malhotra (Finance Advisor)']},
 {'id': 'hero_chennai_velachery',
  'brand_id': 'hero_motocorp',
  'name': 'Hero MotoCorp Authorised Dealer – Velachery',
  'city': 'Chennai',
  'state': 'Tamil Nadu',
  'area': 'Velachery',
  'address': 'No. 54, Velachery Main Road, Near Vijayanagar Bus Stand, Velachery, Chennai',
  'pin_code': '600042',
  'phone': '+91 44 4000 2205',
  'email': 'hero.chennai.velachery@dealer-demo.in',
  'map_url': 'https://maps.google.com/?q=Hero+MotoCorp+Authorised+Dealer+Velachery',
  'rating': 4.7,
  'available_advisors': ['Senthil Murugan (Sales Consultant)', 'Keerthana Selvam (Product Specialist)']},
 {'id': 'hero_hyderabad_madhapur',
  'brand_id': 'hero_motocorp',
  'name': 'Hero MotoCorp Authorised Dealer – Madhapur',
  'city': 'Hyderabad',
  'state': 'Telangana',
  'area': 'Madhapur',
  'address': 'Plot 19, Ayyappa Society Main Road, Madhapur, Hyderabad',
  'pin_code': '500081',
  'phone': '+91 40 4000 2206',
  'email': 'hero.hyderabad.madhapur@dealer-demo.in',
  'map_url': 'https://maps.google.com/?q=Hero+MotoCorp+Authorised+Dealer+Madhapur',
  'rating': 4.7,
  'available_advisors': ['Naveen Goud (Sales Consultant)', 'Swathi Reddy (EV Specialist)']}]

# Brand ids of the legacy car-dealership app that must not survive in the two-wheeler DB.
LEGACY_CAR_BRAND_IDS = [
    "mahindra", "bmw", "hyundai", "maruti_suzuki", "cymbal", "cymbal_motors", "apex_hypercars", "audi",
    "genesis", "nexus_motors", "polestar", "tesla", "testcyber", "zenith_motors",
]
BIKE_BRAND_IDS = ["tvs", "hero_motocorp"]

# Tables partitioned by brand_id (slot_configs / public_holidays are brand-agnostic and kept).
BRAND_PARTITIONED_TABLES = [
    "outbound_call_logs", "test_ride_recordings", "interaction_logs", "conversation_sessions",
    "test_drive_slots", "test_drive_bookings", "insurance_claims", "customers", "dealerships",
]
# Tables holding end-user data; the demo DB is shipped with none of it.
USER_DATA_TABLES = [t for t in BRAND_PARTITIONED_TABLES if t != "dealerships"]


async def purge_legacy_rows(wipe_user_data: bool = True):
    """Deletes all rows belonging to legacy car brands (and cymbal* variants).

    When wipe_user_data is True, ALSO deletes every customer / session / booking / recording /
    outbound-call row for every brand, leaving a clean demo DB with no synthetic users.
    """
    async with AsyncSessionLocal() as db:
        existing = {r[0] for r in (await db.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))).all()} \
            if "sqlite" in _db_url else set(BRAND_PARTITIONED_TABLES)
        placeholders = ", ".join(f":b{i}" for i in range(len(LEGACY_CAR_BRAND_IDS)))
        params = {f"b{i}": b for i, b in enumerate(LEGACY_CAR_BRAND_IDS)}
        for table in BRAND_PARTITIONED_TABLES:
            if table not in existing:
                continue
            if wipe_user_data and table in USER_DATA_TABLES:
                await db.execute(text(f"DELETE FROM {table}"))
            else:
                await db.execute(
                    text(f"DELETE FROM {table} WHERE brand_id IN ({placeholders}) OR brand_id LIKE 'cymbal%'"),
                    params,
                )
        # Dealerships not owned by a two-wheeler brand are legacy car showrooms.
        if "dealerships" in existing:
            await db.execute(
                text("DELETE FROM dealerships WHERE brand_id NOT IN ('tvs', 'hero_motocorp')")
            )
        await db.commit()
        logger.info("Legacy car-brand rows purged.")


async def seed_dealerships():
    """Idempotently seeds holidays, slot timings and TVS / Hero MotoCorp demo dealerships."""
    async with AsyncSessionLocal() as db:
        dirty = False
        # 1. Seed Public Holidays
        h_res = await db.execute(select(PublicHoliday))
        existing_holidays = {h.holiday_date: h for h in h_res.scalars().all()}
        for h in PUBLIC_HOLIDAYS_DATA:
            if h["date"] not in existing_holidays:
                db.add(PublicHoliday(holiday_date=h["date"], holiday_name=h["name"], state=h.get("state", "ALL"), is_active=1))
                dirty = True

        # 2. Seed Slot Configs
        s_res = await db.execute(select(SlotConfig))
        existing_slots = {s.slot_time: s for s in s_res.scalars().all()}
        for s in SLOT_CONFIGS_DATA:
            if s["slot_time"] not in existing_slots:
                db.add(SlotConfig(slot_time=s["slot_time"], display_order=s["order"], is_active=1))
                dirty = True

        # 3. Upsert two-wheeler Dealerships
        d_res = await db.execute(select(Dealership))
        existing_dealerships = {d.id: d for d in d_res.scalars().all()}
        fields = ["brand_id", "name", "city", "state", "area", "address", "pin_code", "phone", "email",
                  "map_url", "rating", "available_advisors"]
        for item in DEALERSHIPS_DATA:
            row = existing_dealerships.get(item["id"])
            if row is None:
                db.add(Dealership(id=item["id"], is_active=True, **{f: item[f] for f in fields}))
                dirty = True
            else:
                for f in fields:
                    if getattr(row, f) != item[f]:
                        setattr(row, f, item[f])
                        dirty = True

        if dirty:
            await db.commit()
            logger.info("Two-wheeler dealership, holiday and slot config seed complete.")


async def _main(purge: bool):
    from app.database import engine, Base
    import app.models  # noqa: F401  (register models)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    if purge:
        await purge_legacy_rows(wipe_user_data=True)
    await seed_dealerships()
    if "sqlite" in str(engine.url):
        async with engine.begin() as conn:
            await conn.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))
    await engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_main(purge="--purge" in sys.argv))

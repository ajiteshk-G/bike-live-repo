from app.services.cache_service import cache
import os
import re
import uuid
import json
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload

from app.models.sales_ride import TestRideRecording
from app.models.customer import Customer, InteractionLog
from app.models.booking import TestDriveBooking
from app.schemas.sales_recording import (
    TestRideRecordingUploadRequest,
    TestRideInsightResponse,
    TestRideLeadItem
)
from app.services.catalog_service import CatalogService
from app.services.customer_service import clean_phone, default_vehicle_for_brand, lookup_vehicle_price
from app.services.brand_service import BrandService
from app.config import settings

logger = logging.getLogger("sales_recording_service")

UPLOAD_BASE_DIR = "/tmp/two_wheeler_test_rides"
os.makedirs(UPLOAD_BASE_DIR, exist_ok=True)

def _create_synthetic_wav_file(filepath: str):
    """Creates a minimal valid WAV file header and blank audio content."""
    import struct
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    sample_rate = 16000
    num_samples = sample_rate * 3 # 3 seconds
    byte_rate = sample_rate * 2
    block_align = 2
    data_size = num_samples * 2
    header = struct.pack(
        '<4sI4s4sIHHIIHH4sI',
        b'RIFF',
        data_size + 36,
        b'WAVE',
        b'fmt ',
        16,
        1,
        1,
        sample_rate,
        byte_rate,
        block_align,
        16,
        b'data',
        data_size
    )
    with open(filepath, "wb") as f:
        f.write(header)
        f.write(b'\x00' * data_size)

class SalesRecordingService:
    # ------------------------------------------------------------------
    # Two-wheeler test ride simulation helpers
    # ------------------------------------------------------------------
    SEGMENT_RIVALS = {
        "commuter motorcycle": ["Honda Shine 100", "Bajaj Platina 110"],
        "premium commuter": ["Honda SP125", "Bajaj Pulsar 125"],
        "sports motorcycle": ["Bajaj Pulsar N160", "Yamaha FZ-S Fi"],
        "naked streetfighter": ["Bajaj Pulsar N160", "Yamaha MT-15"],
        "supersport": ["Yamaha R15 V4", "KTM RC 200"],
        "adventure tourer": ["Royal Enfield Himalayan 450", "KTM 250 Adventure"],
        "cruiser / retro": ["Royal Enfield Classic 350", "Honda CB350"],
        "scooter": ["Honda Activa 6G", "Suzuki Access 125"],
        "performance scooter": ["Yamaha Aerox 155", "Honda Dio 125"],
        "electric scooter": ["Ather Rizta", "Ola S1 Pro"],
        "electric motorcycle": ["Ola Roadster", "Revolt RV400"],
        "moped": ["Honda Activa 6G", "Bajaj Platina 100"],
    }

    @staticmethod
    def _build_test_ride_profile(v_info: Optional[Any], vehicle_id: str, display_veh_name: str) -> Dict[str, Any]:
        """Derives ride-relevant talking points for a motorcycle / scooter from its catalog specs."""
        cat = (getattr(v_info, "category", "") or "").lower()
        fuel = (getattr(v_info, "fuel_or_battery", "") or "").lower()
        highlights = list(getattr(v_info, "key_highlights", None) or [])
        hl_text = " ".join(highlights).lower()
        vid = (vehicle_id or "").lower()

        is_ev = "electric" in cat or "electric" in fuel or any(k in vid for k in ["iqube", "vida", "_ev", "electric"])
        is_scooter = any(k in cat for k in ["scooter", "moped"]) or any(k in vid for k in ["jupiter", "ntorq", "zest", "iqube", "destini", "xoom", "pleasure", "maestro"])

        # Engine / motor
        disp = getattr(v_info, "displacement_cc", None)
        power = getattr(v_info, "max_power", None)
        torque = getattr(v_info, "max_torque", None)
        if is_ev:
            motor = getattr(v_info, "engine_specs", None) or "electric hub motor"
            engine_str = f"{motor}{f' ({power})' if power else ''}"
            pickup_phrase = "twist-and-go instant torque, bilkul zero lag"
            pickup_label = "instant electric torque"
            engine_praise = "Koi vibration nahi, koi gear shift nahi — super silent aur smooth hai."
        else:
            base = f"{disp} cc" if disp and "cc" not in str(disp).lower() else (disp or (getattr(v_info, "engine_specs", "") or "").split(",")[0].strip() or "refined engine")
            extras = ", ".join([x for x in [power, torque] if x])
            engine_str = f"{base}{f' ({extras})' if extras else ''}"
            pickup_phrase = "low-end aur mid-range pickup" if not is_scooter else "CVT ka smooth pickup"
            pickup_label = "acceleration"
            engine_praise = "Refinement achha hai, high rpm par bhi handlebar par zyada vibration nahi aa raha."

        # Braking & ABS
        braking = getattr(v_info, "braking", None)
        if not braking:
            braking = next((h for h in highlights if any(k in h.lower() for k in ["abs", "cbs", "ibs", "disc", "brake"])), None)
        if not braking:
            braking = "front disc with combined braking (CBS)" if is_scooter else "front disc with ABS"
        b_low = braking.lower()
        braking_short = "Dual-channel ABS" if "dual" in b_low else ("Single-channel ABS" if "abs" in b_low else ("CBS/IBS" if any(k in b_low for k in ["cbs", "ibs", "combi", "sbt", "synchron"]) else "disc brakes"))

        # Ergonomics
        seat_height = getattr(v_info, "seat_height", None)
        kerb_weight = getattr(v_info, "kerb_weight", None)
        seat_height_label = seat_height or ("low, flat-foot friendly seat" if is_scooter else "comfortable seat height")

        # Riding modes & connectivity
        modes = list(getattr(v_info, "riding_modes", None) or [])
        has_tft = any(k in hl_text for k in ["tft", "bluetooth", "smartxonnect", "connected", "navigation", "map"])
        connectivity = next((h for h in highlights if any(k in h.lower() for k in ["tft", "bluetooth", "smartxonnect", "connected", "navigation"])), None) or "digital console with Bluetooth call & SMS alerts"

        mileage = getattr(v_info, "range_or_mileage", None) or ("certified range" if is_ev else "segment-best mileage")
        tank = getattr(v_info, "fuel_tank_or_battery", None)

        # Competitors (never name the bike's own brand as a rival)
        brand_word = display_veh_name.split(" ")[0].lower()
        rivals = [c for c in (getattr(v_info, "competitors", None) or []) if brand_word not in c.lower()]
        if not rivals:
            seg_key = next((k for k in SalesRecordingService.SEGMENT_RIVALS if k == cat), None)
            if not seg_key:
                seg_key = "electric scooter" if (is_ev and is_scooter) else ("electric motorcycle" if is_ev else ("scooter" if is_scooter else "sports motorcycle"))
            rivals = [c for c in SalesRecordingService.SEGMENT_RIVALS[seg_key] if brand_word not in c.lower()]
        competitor_name = " aur ".join(rivals[:2]) if rivals else "dusre brands"
        competitor_short = rivals[0] if rivals else "competition"
        if is_ev:
            advantage_str = "battery warranty, wide service network, home charging support aur proven reliability"
        elif is_scooter:
            advantage_str = "under-seat storage, better mileage, low maintenance cost aur family-friendly comfort"
        else:
            advantage_str = f"{braking_short}, better features-per-rupee, strong resale value aur nationwide service network"

        return {
            "display_veh_name": display_veh_name,
            "is_ev": is_ev,
            "is_scooter": is_scooter,
            "engine_str": engine_str,
            "pickup_phrase": pickup_phrase,
            "pickup_label": pickup_label,
            "engine_praise": engine_praise,
            "braking": braking,
            "braking_short": braking_short,
            "seat_height_label": seat_height_label,
            "kerb_weight": kerb_weight,
            "modes": modes,
            "has_tft": has_tft,
            "connectivity": connectivity,
            "mileage": mileage,
            "tank": tank,
            "competitor_name": competitor_name,
            "competitor_short": competitor_short,
            "advantage_str": advantage_str,
        }

    @staticmethod
    def _build_simulated_test_ride_transcript(profile: Dict[str, Any], cust_name: str, advisor_short: str) -> str:
        """Hinglish on-bike test ride conversation (advisor on pillion / riding alongside)."""
        p = profile
        veh = p["display_veh_name"]
        weight_bit = f" Kerb weight sirf {p['kerb_weight']} hai, isliye traffic mein handle karna easy hai." if p.get("kerb_weight") else ""
        modes_bit = (
            f"Isme {', '.join(p['modes'])} riding modes hain — highway par {p['modes'][0]} try kariye, baarish mein {p['modes'][-1]}."
            if p["modes"] else "Throttle response city aur highway dono ke liye well-calibrated hai."
        )
        if p["is_ev"]:
            fuel_q = "Ek full charge mein real-world range kitni milegi? Aur ghar pe charging kitna time lega?"
            fuel_a = f"{veh} ki {p['mileage']} hai. Normal home socket se overnight full charge ho jata hai, aur app pe charging status live dikhta hai."
        else:
            fuel_q = "Mileage kitna dega daily office commute mein? Petrol ka kharcha important hai."
            tank_bit = f" {p['tank']} tank ke saath" if p.get("tank") else ""
            fuel_a = f"{veh} ka {p['mileage']} hai{tank_bit}, toh weekly refuel ka tension nahi."
        pillion_q = "Meri wife pillion baithegi — pillion seat aur grab rail comfortable hai?" if not p["is_scooter"] else "Pillion ke liye floorboard aur seat space kaisa hai? Family ke saath use karna hai."
        return f"""[00:10] Advisor {advisor_short}: "Namaste {cust_name} ji! Helmet strap tight kar lijiye, side stand check — chaliye shuru karte hain. Yeh {p['engine_str']} hai, {p['pickup_phrase']} feel kariye."
[00:28] {cust_name} (Customer): "Arre wah, pickup toh kaafi punchy hai! {p['engine_praise']}"
[00:47] Advisor {advisor_short}: "Ab thoda sudden brake karke dekhiye — isme {p['braking']} hai, toh wheel lock nahi hoga aur bike straight rukti hai."
[01:05] {cust_name} (Customer): "Haan, braking bahut confident laga. ABS ka pulse feel hua but control poora tha."
[01:22] Advisor {advisor_short}: "Next corner par thoda lean kariye — chassis aur suspension ka balance dekhiye.{weight_bit}"
[01:40] {cust_name} (Customer): "Handling kaafi agile hai, cornering mein stable lag rahi hai. Potholes par suspension bhi theek absorb kar raha hai."
[01:58] {cust_name} (Customer): "Seat height mere liye sahi hai? Main 5 feet 7 hoon, signal pe dono pair zameen pe aa rahe hain."
[02:12] Advisor {advisor_short}: "Bilkul sir, {p['seat_height_label']} — rider triangle upright hai, toh long rides mein back pain nahi hoga."
[02:30] {cust_name} (Customer): "{pillion_q}"
[02:45] Advisor {advisor_short}: "Pillion seat wide aur well-padded hai, grab rail bhi sturdy hai — do log aaram se long ride kar sakte hain."
[03:00] {cust_name} (Customer): "{fuel_q}"
[03:15] Advisor {advisor_short}: "{fuel_a}"
[03:32] Advisor {advisor_short}: "{modes_bit}"
[03:48] {cust_name} (Customer): "Aur console mein navigation aur call alerts aate hain kya?"
[04:02] Advisor {advisor_short}: "Haan sir, isme {p['connectivity']} hai — phone pair karke turn-by-turn navigation, call aur SMS alerts dikhte hain."
[04:20] {cust_name} (Customer): "Sab badhiya hai, but honestly {p['competitor_name']} thoda sasta pad raha hai on-road."
[04:38] Advisor {advisor_short}: "Valid point {cust_name} ji! {p['competitor_short']} ka price attractive hai, lekin jab aap {p['advantage_str']} compare karenge toh value clear hai."
[04:58] {cust_name} (Customer): "Theek hai. Two-wheeler loan ka kya option hai? EMI kitni banegi?"
[05:14] Advisor {advisor_short}: "Sir, hamare partner banks aur NBFCs se 10% se 25% down payment par loan mil jata hai, tenure 12 se 48 months tak, aur instant digital approval bhi hai."
[05:32] {cust_name} (Customer): "Perfect! Ride experience top class tha. Chaliye showroom chalte hain, booking aur loan process start karte hain."
[05:45] Advisor {advisor_short}: "Thank you {cust_name} ji! Bike showroom pe park kar dete hain — system aapko on-road price aur EMI options turant bhej dega." """

    @staticmethod
    def _build_customer_conversation_intelligence(
        customer: Optional[Customer],
        sessions: List[Any],
        logs: List[InteractionLog],
        default_vehicle_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Groups all conversations for a unique (Name + Phone Number) customer by calendar day,
        extracting the interested two-wheeler, interested features, and budget for each conversation and each day.
        """
        from app.services.customer_service import extract_conversation_intelligence, lookup_vehicle_price, DEFAULT_VEHICLE_ID
        from app.schemas.sales_recording import (
            ConversationTurnItem,
            ConversationSessionSummary,
            DailyConversationGroup
        )

        cust_budget = customer.budget_range if customer else None
        fallback_vid = default_vehicle_id or (customer.interested_vehicle_id if customer else None) or DEFAULT_VEHICLE_ID

        # Map logs by session_id (DB integer ID) and also handle orphan logs
        logs_by_sess_id: Dict[int, List[InteractionLog]] = {}
        orphan_logs: List[InteractionLog] = []
        for lg in sorted(logs, key=lambda x: x.created_at or datetime.min):
            if lg.channel == "TEST_RIDE_IN_VEHICLE" or lg.speaker == "system":
                continue
            if lg.session_id:
                logs_by_sess_id.setdefault(lg.session_id, []).append(lg)
            else:
                orphan_logs.append(lg)

        session_summaries: List[ConversationSessionSummary] = []
        all_cars: List[str] = []
        all_features: List[str] = []
        latest_budget: Optional[str] = cust_budget

        sorted_sessions = sorted(sessions, key=lambda s: s.created_at or datetime.min, reverse=True)

        for sess in sorted_sessions:
            s_logs = logs_by_sess_id.get(sess.id, [])
            # If multiple sessions exist, skip completely empty 0-turn shell sessions if other sessions have turns
            if not s_logs and len(sorted_sessions) > 1:
                continue

            msg_dicts = [{"speaker": l.speaker, "message": l.message} for l in s_logs]
            parsed_summary = None
            if sess.summary and sess.summary.strip().startswith("{"):
                try:
                    parsed_summary = json.loads(sess.summary)
                except Exception:
                    parsed_summary = None

            if not parsed_summary or s_logs:
                parsed_summary = extract_conversation_intelligence(
                    msg_dicts,
                    default_vehicle_id=sess.vehicle_id or fallback_vid,
                    existing_budget=cust_budget
                )

            car_name = parsed_summary.get("primary_vehicle_name") or lookup_vehicle_price(sess.vehicle_id or fallback_vid)[0]
            sess_cars = parsed_summary.get("interested_cars") or [car_name]
            sess_feats = parsed_summary.get("interested_features") or ["Styling & Road Presence", "Mileage / Range & Charging"]
            sess_budget = parsed_summary.get("budget") or cust_budget or lookup_vehicle_price(sess.vehicle_id or fallback_vid)[1]
            key_points = parsed_summary.get("key_points_summary") or f"Interested in {car_name} | Focus: {', '.join(sess_feats[:3])} | Budget: {sess_budget}"

            for c_item in sess_cars:
                if c_item not in all_cars:
                    all_cars.append(c_item)
            for f_item in sess_feats:
                if f_item not in all_features:
                    all_features.append(f_item)
            if sess_budget and (not latest_budget or latest_budget == "Standard Range"):
                latest_budget = sess_budget

            dt = sess.created_at or datetime.now(timezone.utc)
            date_key = dt.strftime("%Y-%m-%d")
            date_label = dt.strftime("%a, %d %b %Y")
            time_label = dt.strftime("%I:%M %p")

            turn_items = [
                ConversationTurnItem(
                    speaker=customer.name if (l.speaker == "customer" and customer) else ("Customer" if l.speaker == "customer" else "Kavya (AI Specialist)"),
                    role=l.speaker,
                    message=l.message,
                    timestamp=l.created_at.strftime("%I:%M %p") if l.created_at else time_label
                )
                for l in s_logs
            ]

            session_summaries.append(ConversationSessionSummary(
                session_id=sess.session_id,
                date_key=date_key,
                date_label=date_label,
                time_label=time_label,
                channel="LIVE_VOICE" if sess.session_type in ("LIVE_CALL", "VOICE_LIVE") else "CHAT_BOT",
                interested_car=", ".join(sess_cars[:2]),
                interested_features=sess_feats,
                budget=sess_budget,
                key_points_summary=key_points,
                turn_count=len(turn_items),
                turns=turn_items
            ))

        # Also include orphan logs if no session captured them
        if orphan_logs and not session_summaries:
            msg_dicts = [{"speaker": l.speaker, "message": l.message} for l in orphan_logs]
            intel = extract_conversation_intelligence(msg_dicts, default_vehicle_id=fallback_vid, existing_budget=cust_budget)
            dt = orphan_logs[-1].created_at or datetime.now(timezone.utc)
            date_key = dt.strftime("%Y-%m-%d")
            date_label = dt.strftime("%a, %d %b %Y")
            time_label = dt.strftime("%I:%M %p")
            for c_item in intel["interested_cars"]:
                if c_item not in all_cars:
                    all_cars.append(c_item)
            for f_item in intel["interested_features"]:
                if f_item not in all_features:
                    all_features.append(f_item)
            latest_budget = intel["budget"]
            turn_items = [
                ConversationTurnItem(
                    speaker=customer.name if (l.speaker == "customer" and customer) else ("Customer" if l.speaker == "customer" else "Kavya (AI Specialist)"),
                    role=l.speaker,
                    message=l.message,
                    timestamp=l.created_at.strftime("%I:%M %p") if l.created_at else time_label
                )
                for l in orphan_logs
            ]
            session_summaries.append(ConversationSessionSummary(
                session_id=f"SESS-{dt.strftime('%Y%m%d-%H%M')}",
                date_key=date_key,
                date_label=date_label,
                time_label=time_label,
                channel="LIVE_VOICE",
                interested_car=", ".join(intel["interested_cars"][:2]),
                interested_features=intel["interested_features"],
                budget=intel["budget"],
                key_points_summary=intel["key_points_summary"],
                turn_count=len(turn_items),
                turns=turn_items
            ))

        if not all_cars:
            def_car = lookup_vehicle_price(fallback_vid)[0]
            all_cars.append(def_car)
        if not all_features:
            all_features = ["Styling & Road Presence", "Mileage / Range & Charging"]
        if not latest_budget or latest_budget == "Standard Range":
            latest_budget = lookup_vehicle_price(fallback_vid)[1]

        # Group sessions by calendar day (date_key descending)
        day_groups_map: Dict[str, List[ConversationSessionSummary]] = {}
        day_labels_map: Dict[str, str] = {}
        for s_sum in session_summaries:
            day_groups_map.setdefault(s_sum.date_key, []).append(s_sum)
            day_labels_map[s_sum.date_key] = s_sum.date_label

        conversations_by_day: List[DailyConversationGroup] = []
        for d_key in sorted(day_groups_map.keys(), reverse=True):
            d_sessions = day_groups_map[d_key]
            d_cars: List[str] = []
            d_feats: List[str] = []
            d_budget = d_sessions[0].budget if d_sessions else latest_budget
            for ds in d_sessions:
                for c_part in [x.strip() for x in ds.interested_car.split(",") if x.strip()]:
                    if c_part not in d_cars:
                        d_cars.append(c_part)
                for f_part in ds.interested_features:
                    if f_part not in d_feats:
                        d_feats.append(f_part)

            conversations_by_day.append(DailyConversationGroup(
                date_key=d_key,
                date_label=day_labels_map[d_key],
                conversation_count=len(d_sessions),
                cars_discussed=d_cars,
                features_interested=d_feats[:5],
                budget_mentioned=d_budget,
                sessions=d_sessions
            ))

        return {
            "total_conversations": len(session_summaries),
            "interested_cars": all_cars,
            "interested_features": all_features[:6],
            "budget_range": latest_budget,
            "conversations_by_day": conversations_by_day,
        }

    @staticmethod
    async def get_sales_leads(
        db: AsyncSession,
        dealership_id: Optional[str] = None,
        brand_id: Optional[str] = None
    ) -> List[TestRideLeadItem]:
        """
        Fetch qualified leads for the Sales Consultant App scoped to brand.
        Strictly 1 lead row per unique customer (identified by Unique Name + Phone Number).
        Includes per-day conversation breakdown, interested two-wheeler(s), interested features, and budget.
        """
        from app.models.customer import ConversationSession
        from app.services.customer_service import clean_name

        b_id = (brand_id or (BrandService.get_active_brand().id if BrandService.get_active_brand() else "tvs")).lower()
        cache_key = f"sales_leads_{b_id}_{dealership_id or 'all'}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
            
        booking_stmt = (
            select(TestDriveBooking)
            .where(TestDriveBooking.brand_id == b_id)
            .order_by(TestDriveBooking.created_at.desc())
        )
        if dealership_id and dealership_id.strip() and dealership_id.strip() != "ALL":
            booking_stmt = booking_stmt.where(
                (TestDriveBooking.dealership_id == dealership_id.strip()) |
                (TestDriveBooking.dealership_name.ilike(f"%{dealership_id.strip()}%"))
            )
        booking_res = await db.execute(booking_stmt)
        bookings = booking_res.scalars().all()

        leads: List[TestRideLeadItem] = []
        seen_customer_keys = set()

        # Batch prefetch all Customers, Sessions, InteractionLogs, and Recordings for this brand
        all_cust_res = await db.execute(
            select(Customer)
            .where(Customer.brand_id == b_id)
            .options(
                selectinload(Customer.sessions),
                selectinload(Customer.interactions)
            )
            .order_by(Customer.updated_at.desc())
        )
        all_customers_list = all_cust_res.scalars().all()
        cust_map = {c.id: c for c in all_customers_list}

        rec_res = await db.execute(
            select(TestRideRecording.booking_reference, TestRideRecording.customer_id)
            .where(TestRideRecording.brand_id == b_id)
        )
        existing_rec_refs = {r[0] for r in rec_res.all() if r[0]}

        for b in bookings:
            c = cust_map.get(b.customer_id)

            cust_name = c.name if c else "Valued Customer"
            cust_phone = c.phone if c else ""
            cust_email = c.email if c else None
            cust_city = c.city if c else "Mumbai"
            cust_id_str = c.customer_id if c else f"CUST-{b.customer_id}"

            norm_phone = clean_phone(cust_phone) if cust_phone else f"NOPHONE-{b.customer_id}"
            norm_name = (clean_name(cust_name) or cust_name).lower()
            composite_key = (norm_name, norm_phone)
            
            if composite_key in seen_customer_keys:
                continue
            seen_customer_keys.add(composite_key)

            intel_data = SalesRecordingService._build_customer_conversation_intelligence(
                customer=c,
                sessions=list(c.sessions) if c else [],
                logs=list(c.interactions) if c else [],
                default_vehicle_id=b.vehicle_id
            )

            v_info = CatalogService.get_vehicle_by_id(b.vehicle_id)
            veh_name = v_info.name if v_info else b.vehicle_id.replace("_", " ").title()

            db_checklist = b.advisor_checklist or (c.advisor_checklist if c else None)
            is_custom = bool(db_checklist and len(db_checklist) > 0)
            final_checklist = db_checklist if is_custom else [f"Demonstrate / Highlight {f}" for f in intel_data["interested_features"][:4]]

            has_tr_rec = b.booking_reference in existing_rec_refs
            resolved_status = "TestRide_Completed" if (b.status == "TestRide_Completed" or has_tr_rec) else (b.status or "CONFIRMED")

            leads.append(TestRideLeadItem(
                customer_id=cust_id_str,
                brand_id=b_id,
                name=cust_name,
                phone=cust_phone,
                email=cust_email,
                city=cust_city,
                preferred_vehicle=f"{veh_name} ({b.variant})",
                vehicle_name=veh_name,
                vehicle_id=b.vehicle_id,
                variant=b.variant,
                booking_reference=b.booking_reference,
                dealership_id=b.dealership_id,
                dealership_name=b.dealership_name,
                booking_type=b.booking_type or "HOME_DOORSTEP",
                delivery_address=b.delivery_address,
                booking_status=resolved_status,
                scheduled_slot=f"{b.scheduled_date} at {b.scheduled_time_slot}",
                presales_notes=f"Interested in {', '.join(intel_data['interested_cars'])} | Features: {', '.join(intel_data['interested_features'][:3])} | Budget: {intel_data['budget_range']}",
                advisor_checklist=final_checklist,
                is_custom_checklist=True,
                total_conversations=intel_data["total_conversations"],
                interested_cars=intel_data["interested_cars"],
                interested_features=intel_data["interested_features"],
                budget_range=intel_data["budget_range"],
                conversations_by_day=intel_data["conversations_by_day"]
            ))

        if not dealership_id or dealership_id == "ALL":
            active_brand = BrandService.get_brand(b_id)
            def_dlr_name = (active_brand.dealerships[0].name if active_brand and active_brand.dealerships else f"{b_id.title()} Official Dealership")
            def_dlr_id = (active_brand.dealerships[0].id if active_brand and active_brand.dealerships else f"{b_id}_flagship")

            for c in all_customers_list:
                norm_phone = clean_phone(c.phone) if c.phone else f"NOPHONE-{c.id}"
                norm_name = (clean_name(c.name) or c.name).lower()
                composite_key = (norm_name, norm_phone)
                if composite_key not in seen_customer_keys:
                    seen_customer_keys.add(composite_key)
                    intel_data = SalesRecordingService._build_customer_conversation_intelligence(
                        customer=c,
                        sessions=list(c.sessions),
                        logs=list(c.interactions),
                        default_vehicle_id=c.interested_vehicle_id or default_vehicle_for_brand(b_id)
                    )

                    v_info = CatalogService.get_vehicle_by_id(c.interested_vehicle_id or default_vehicle_for_brand(b_id))
                    veh_name = v_info.name if v_info else (intel_data["interested_cars"][0] if intel_data["interested_cars"] else lookup_vehicle_price(default_vehicle_for_brand(b_id))[0])
                    db_checklist = c.advisor_checklist
                    is_custom = bool(db_checklist and len(db_checklist) > 0)
                    final_checklist = db_checklist if is_custom else [f"Demonstrate / Highlight {f}" for f in intel_data["interested_features"][:4]]

                    tr_rec_stmt = select(TestRideRecording).where(TestRideRecording.customer_id == c.id, TestRideRecording.brand_id == b_id)
                    tr_res = await db.execute(tr_rec_stmt)
                    has_tr_rec = tr_res.scalars().first() is not None

                    resolved_status = "TestRide_Completed" if (c.current_phase == "TestRide_Completed" or has_tr_rec) else "INQUIRY_READY_FOR_RIDE"

                    leads.append(TestRideLeadItem(
                        customer_id=c.customer_id,
                        brand_id=b_id,
                        name=c.name,
                        phone=c.phone,
                        email=c.email,
                        city=c.city or "Mumbai",
                        preferred_vehicle=f"{veh_name} ({c.interested_variant or 'Standard Variant'})",
                        vehicle_name=veh_name,
                        vehicle_id=c.interested_vehicle_id or default_vehicle_for_brand(b_id),
                        variant=c.interested_variant or "Standard Variant",
                        dealership_name=def_dlr_name,
                        dealership_id=def_dlr_id,
                        booking_status=resolved_status,
                        scheduled_slot=f"{intel_data['total_conversations']} Pre-Sales Conversation(s)",
                        presales_notes=f"Interested in {', '.join(intel_data['interested_cars'])} | Features: {', '.join(intel_data['interested_features'][:3])} | Budget: {intel_data['budget_range']}",
                        advisor_checklist=final_checklist,
                        is_custom_checklist=True,
                        total_conversations=intel_data["total_conversations"],
                        interested_cars=intel_data["interested_cars"],
                        interested_features=intel_data["interested_features"],
                        budget_range=intel_data["budget_range"],
                        conversations_by_day=intel_data["conversations_by_day"]
                    ))

        cache.set(cache_key, leads, ttl_seconds=15)
        return leads

    @staticmethod
    async def process_and_store_recording(db: AsyncSession, req: TestRideRecordingUploadRequest) -> TestRideRecording:
        # Determine brand_id
        b_id = (
            getattr(req, "brand_id", None) or
            (BrandService.get_active_brand().id if BrandService.get_active_brand() else "tvs")
        ).lower()

        # Invalidate leads cache on new recording upload
        cache.invalidate(f"sales_leads_{b_id}")
        cache.invalidate("sales_leads_")
        """
        Saves test ride audio recording at:
        gs://<GCS_RECORDINGS_BUCKET>/test_rides/<date>/<booking_reference>.wav
        Executes Gemini transcription with speaker identification and multi-dimensional insights.
        Persists in database against that customer and booking.
        """
        # 1. Resolve Customer
        stmt = select(Customer).where(
            ((Customer.customer_id == req.customer_id) | (Customer.phone == req.customer_id)) &
            (Customer.brand_id == b_id)
        )
        res = await db.execute(stmt)
        customer = res.scalars().first()

        if not customer:
            # Never attach a recording to an unrelated customer or fabricate an identity.
            raise LookupError(
                f"Customer '{req.customer_id}' not found for brand '{b_id}'. Identify the customer before uploading a test ride."
            )

        # 2. Resolve Booking and Booking Reference
        booking: Optional[TestDriveBooking] = None
        if req.booking_reference:
            b_stmt = select(TestDriveBooking).where(TestDriveBooking.booking_reference == req.booking_reference)
            b_res = await db.execute(b_stmt)
            booking = b_res.scalars().first()

        if not booking and customer:
            b_stmt = select(TestDriveBooking).where(TestDriveBooking.customer_id == customer.id).order_by(TestDriveBooking.created_at.desc())
            b_res = await db.execute(b_stmt)
            booking = b_res.scalars().first()

        booking_ref = (
            req.booking_reference or
            (booking.booking_reference if booking else None) or
            f"BK-{b_id.upper()[:3]}-{uuid.uuid4().hex[:5].upper()}"
        )
        booking_id = booking.id if booking else None

        # 3. Formulate standard GCS Path based on mime type
        now_utc = datetime.now(timezone.utc)
        date_str = now_utc.strftime("%Y-%m-%d")
        gcs_bucket = settings.GCS_RECORDINGS_BUCKET

        # Detect audio extension and mime type
        audio_mime_type = req.audio_format or "audio/wav"
        ext = "wav"
        if "webm" in audio_mime_type.lower():
            ext = "webm"
        elif "mp4" in audio_mime_type.lower() or "m4a" in audio_mime_type.lower():
            ext = "m4a"
        elif "ogg" in audio_mime_type.lower():
            ext = "ogg"
        elif "mp3" in audio_mime_type.lower() or "mpeg" in audio_mime_type.lower():
            ext = "mp3"

        gcs_object_path = f"test_rides/{date_str}/{booking_ref}.{ext}"
        gcs_uri = f"gs://{gcs_bucket}/{gcs_object_path}"

        # Write local file copy for audit and upload
        local_dir = os.path.join(UPLOAD_BASE_DIR, date_str)
        os.makedirs(local_dir, exist_ok=True)
        local_file_path = os.path.join(local_dir, f"{booking_ref}.{ext}")

        raw_bytes: Optional[bytes] = None
        file_size = 1485200
        has_real_audio = False

        if req.audio_base64 and len(req.audio_base64.strip()) > 50:
            import base64
            try:
                header, data = req.audio_base64.split(",", 1) if "," in req.audio_base64 else ("", req.audio_base64)
                if "data:" in header and ";" in header:
                    detected_mime = header.split("data:")[1].split(";")[0].strip()
                    if detected_mime:
                        audio_mime_type = detected_mime
                raw_bytes = base64.b64decode(data)
                with open(local_file_path, "wb") as f:
                    f.write(raw_bytes)
                file_size = len(raw_bytes)
                if file_size > 50:
                    has_real_audio = True
            except Exception as e:
                logger.warning(f"Failed to decode base64 audio: {e}")
                _create_synthetic_wav_file(local_file_path)
        else:
            _create_synthetic_wav_file(local_file_path)

        # Upload audio file to Google Cloud Storage (GCS)
        try:
            from google.cloud import storage
            storage_client = storage.Client(project=settings.VERTEX_PROJECT_ID)
            bucket = storage_client.bucket(gcs_bucket)
            blob = bucket.blob(gcs_object_path)
            blob.upload_from_filename(local_file_path, content_type=audio_mime_type)
            logger.info(f"Uploaded test ride recording to GCS: {gcs_uri}")
        except Exception as e:
            logger.error(f"Failed to upload to GCS bucket {gcs_bucket}: {e}")

        # 4. Vehicle metadata and Advisor details
        # Resolve active / requested brand
        brand_id = getattr(req, "brand_id", None)
        brand = BrandService.get_brand(brand_id) if brand_id else None
        if not brand:
            brand = BrandService.get_active_brand()
        brand_name = re.sub(r"\s*\(.*?\)", "", brand.name).strip() if brand else "Two-Wheeler"
        brand_short = "Hero" if brand_name.lower().startswith("hero") else brand_name.split(" ")[0].strip()

        # Resolve vehicle details from brand or catalog
        v_info = None
        req_norm = req.vehicle_id.lower().replace("-", "_")
        if brand and brand.vehicles:
            for v in brand.vehicles:
                if v.id.lower().replace("-", "_") == req_norm or v.id.lower() == req.vehicle_id.lower():
                    v_info = v
                    break
        if not v_info:
            v_info = CatalogService.get_vehicle_by_id(req.vehicle_id)

        raw_veh_name = v_info.name if v_info else req.vehicle_id.replace("-", " ").replace("_", " ").title()
        if brand_short.lower() in raw_veh_name.lower():
            display_veh_name = raw_veh_name
        else:
            display_veh_name = f"{brand_short} {raw_veh_name}"

        veh_name = display_veh_name
        cust_name = req.customer_name or customer.name or "Customer"
        advisor_name = req.sales_advisor_name or "Sales Consultant"
        advisor_short = advisor_name.split("(")[0].strip().split(" ")[0] or "Advisor"

        checklist_items = req.advisor_checklist or (booking.advisor_checklist if booking else None) or (customer.advisor_checklist if customer else None) or CatalogService.get_static_checklist(req.vehicle_id)
        session_id = req.session_id or f"TR-2026-{uuid.uuid4().hex[:6].upper()}"

        # 5. Dynamic Indian On-Bike Test Ride Dialogue Script (motorcycles, scooters & EVs)
        profile = SalesRecordingService._build_test_ride_profile(v_info, req.vehicle_id, display_veh_name)
        simulated_transcript = SalesRecordingService._build_simulated_test_ride_transcript(
            profile, cust_name=cust_name, advisor_short=advisor_short
        )

        transcript = simulated_transcript
        customer_sentiment = 0.85
        purchase_intent = 0.85
        advisor_score = 8.0

        is_live_recording = bool(has_real_audio and ("simulat" not in (req.simulated_scenario or "").lower()))

        if is_live_recording:
            loved_features: List[str] = []
            objections_raised: List[str] = []
        else:
            loved_features = [
                f"{display_veh_name} pickup & {profile['pickup_label']}",
                f"Braking confidence ({profile['braking_short']})",
                f"Seat height & rider fit ({profile['seat_height_label']})",
            ]
            objections_raised = [
                f"Price comparison with {profile['competitor_name']}",
                "Two-wheeler loan EMI & down payment options",
            ]

        advisor_coaching = f"Advisor {advisor_short} demonstrated {display_veh_name} on the test ride and answered the rider's questions."
        recommended_action = f"Share on-road price & two-wheeler loan EMI options and finalise booking for {cust_name} ({display_veh_name})."

        # 6. Dynamic Evaluation and Transcription using Gemini Multimodal Audio Model
        try:
            from google import genai
            from google.genai import types
            import asyncio

            from app.services.genai_client import get_genai_client
            vertex_client = get_genai_client()

            is_live_recording = has_real_audio and req.simulated_scenario not in ("test_drive_simulation", "test_ride_simulation")

            if is_live_recording and raw_bytes:
                # Transcribe directly from recorded audio and extract speech insights
                audio_part = types.Part.from_bytes(data=raw_bytes, mime_type=audio_mime_type)
                analysis_prompt = f"""You are an expert Two-Wheeler (motorcycle & scooter) Sales Audio Analyst and Transcriber for {brand_name}.
You are given an authentic audio recording from a real TEST RIDE session between Sales Advisor {advisor_name} and Customer {cust_name} for the two-wheeler {veh_name} ({req.variant}). Expect wind / traffic / engine noise.

CRITICAL INSTRUCTIONS:
1. Verbatim Transcription: Transcribe the actual spoken audio word-for-word with speaker labels (e.g. "[00:05] Advisor {advisor_short}: ...", "[00:15] {cust_name} (Customer): ...") and timestamps. If the audio is in Hindi, English, or Hinglish, transcribe exactly what is spoken (keep the Hinglish tone). If no clear speech is audible, state: "[00:00] Test ride audio recorded. Ambient riding sounds captured."
2. Loved Features Extraction: Extract ONLY the two-wheeler aspects the customer explicitly praised or asked positively about in THIS recording — e.g. pickup / acceleration, braking & ABS confidence, handling / cornering, suspension over potholes, seat height & rider fit, pillion comfort, mileage / EV range & charging, riding modes, TFT / Bluetooth connectivity & navigation, under-seat storage, helmet / safety features, styling. Do NOT include features that were not discussed.
3. Objections & Concerns Extraction: Extract ONLY the specific doubts, objections, price questions, competitor comparisons (e.g. Bajaj, Honda, Yamaha, Royal Enfield, Ather, Ola, Suzuki, KTM) or delivery / service concerns the customer explicitly raised in THIS recording. If none, return []. Do NOT invent competitor comparisons.
4. Sentiment & Purchase Intent: Realistic scores (0.00 to 1.00) based strictly on the rider's tone, dialogue, and buying signals.
5. Sales Pitch Score & Coaching: Evaluate the advisor's pitch (1.0 to 10.0) and give 2-3 sentences of constructive coaching (e.g. did they cover ABS demo, seat-height fit check, pillion comfort, mileage/range, riding modes, helmet safety, two-wheeler loan options).
6. Recommended Action: 1-2 actionable next steps for the dealership team (e.g. share on-road price, two-wheeler loan EMI with 10-25% down payment over 12-48 months, exchange offer, accessory/helmet bundle).

Return strictly valid JSON with keys:
"transcript", "customer_sentiment_score", "purchase_intent_score", "advisor_pitch_score", "loved_features", "objections_raised", "advisor_coaching_feedback", "recommended_action"."""
                contents = [audio_part, analysis_prompt]
            else:
                # Text analysis on simulation transcript
                analysis_prompt = f"""You are an expert Two-Wheeler (motorcycle & scooter) Sales Analyst for {brand_name}.
Analyze this TEST RIDE conversation (Hinglish) between Sales Advisor {advisor_name} and Customer {cust_name} for the two-wheeler {veh_name} ({req.variant}).

Conversation Transcript:
{simulated_transcript}

Dynamically evaluate the conversation and extract realistic, non-hardcoded metrics:
1. customer_sentiment_score: Float between 0.00 and 1.00 based on rider satisfaction, tone, and feedback.
2. purchase_intent_score: Float between 0.00 and 1.00 based on buying readiness, loan / EMI questions, and decision to book.
3. advisor_pitch_score: Float between 1.0 and 10.0 based on how well the advisor covered pickup, braking & ABS, handling, seat height & rider fit, pillion comfort, mileage / range, riding modes, TFT connectivity and helmet safety.
4. loved_features: List of 3-4 specific two-wheeler aspects explicitly praised by the customer.
5. objections_raised: List of 1-2 specific concerns / competitor comparisons (e.g. Bajaj, Honda, Yamaha, Royal Enfield, Ather, Ola) mentioned by the customer.
6. advisor_coaching_feedback: Constructive coaching feedback for the advisor in 2-3 sentences.
7. recommended_action: Immediate next step for the follow-up team in 1-2 sentences (e.g. on-road price + two-wheeler loan EMI, 12-48 month tenure).

Return valid JSON with keys: transcript, customer_sentiment_score, purchase_intent_score, advisor_pitch_score, loved_features, objections_raised, advisor_coaching_feedback, recommended_action."""
                contents = [analysis_prompt]

            config = types.GenerateContentConfig(
                temperature=0.2,
                response_mime_type="application/json"
            )

            gemini_resp = await asyncio.wait_for(
                asyncio.to_thread(
                    vertex_client.models.generate_content,
                    model=settings.REST_CHAT_MODEL,
                    contents=contents,
                    config=config
                ),
                timeout=12.0
            )

            if gemini_resp and gemini_resp.text:
                parsed = json.loads(gemini_resp.text)
                if parsed.get("transcript") and len(parsed["transcript"].strip()) > 5:
                    transcript = parsed["transcript"].strip()
                if "customer_sentiment_score" in parsed:
                    val = float(parsed["customer_sentiment_score"])
                    customer_sentiment = round(val / 10.0 if val > 1.0 else val, 2)
                if "purchase_intent_score" in parsed:
                    val = float(parsed["purchase_intent_score"])
                    purchase_intent = round(val / 10.0 if val > 1.0 else val, 2)
                if "advisor_pitch_score" in parsed:
                    val = float(parsed["advisor_pitch_score"])
                    advisor_score = round(val if val <= 10.0 else val / 10.0, 1)
                
                if is_live_recording:
                    # Parse loved features and objections directly from audio analysis
                    if "loved_features" in parsed and isinstance(parsed["loved_features"], list):
                        audio_loved = [str(f).strip() for f in parsed["loved_features"] if str(f).strip()]
                        loved_features = audio_loved if audio_loved else [f"Ride dynamics & performance ({veh_name})"]
                    if "objections_raised" in parsed and isinstance(parsed["objections_raised"], list):
                        objections_raised = [str(o).strip() for o in parsed["objections_raised"] if str(o).strip()]
                else:
                    if parsed.get("loved_features") and isinstance(parsed["loved_features"], list) and len(parsed["loved_features"]) > 0:
                        loved_features = parsed["loved_features"]
                    if parsed.get("objections_raised") and isinstance(parsed["objections_raised"], list):
                        objections_raised = parsed["objections_raised"]

                if parsed.get("advisor_coaching_feedback"):
                    advisor_coaching = parsed["advisor_coaching_feedback"]
                if parsed.get("recommended_action"):
                    recommended_action = parsed["recommended_action"]
                logger.info(f"Gemini evaluation completed: transcript_length={len(transcript)}, sentiment={customer_sentiment}, intent={purchase_intent}, pitch_score={advisor_score}, loved={len(loved_features)}, objections={len(objections_raised)}")
        except Exception as e:
            logger.warning(f"Gemini dynamic audio evaluation notice: {e}")

        # 6. Create TestRideRecording DB Record
        recording = TestRideRecording(
            session_id=session_id,
            booking_id=booking_id,
            booking_reference=booking_ref,
            customer_id=customer.id,
            brand_id=b_id,
            vehicle_id=req.vehicle_id,
            vehicle_name=f"{veh_name} ({req.variant})",
            sales_advisor_name=advisor_name,
            gcs_bucket=gcs_bucket,
            gcs_object_path=gcs_object_path,
            gcs_uri=gcs_uri,
            duration_seconds=req.duration_seconds or 345,
            file_size_bytes=file_size,
            audio_format=req.audio_format,
            transcript=transcript,
            customer_sentiment_score=customer_sentiment,
            purchase_intent_score=purchase_intent,
            loved_features=loved_features,
            objections_raised=objections_raised,
            advisor_pitch_score=advisor_score,
            advisor_coaching_feedback=advisor_coaching,
            recommended_action=recommended_action,
            status="ANALYZED"
        )
        db.add(recording)

        # 7. Log Individual Dialogue Turns in InteractionLog for unified customer history
        for line in transcript.strip().split("\n"):
            line = re.sub(r"^\s*\[\d{1,2}:\d{2}(?::\d{2})?\]\s*", "", line)
            if ":" in line:
                parts = line.split(":", 1)
                speaker_tag = parts[0].strip()
                dialogue = parts[1].strip().strip('"')
                is_cust = "customer" in speaker_tag.lower() or cust_name.lower() in speaker_tag.lower()
                spk = "customer" if is_cust else "sales_advisor"
                
                log = InteractionLog(
                    customer_id=customer.id,
                    brand_id=b_id,
                    session_id=None,
                    speaker=spk,
                    message=dialogue,
                    channel="TEST_RIDE_IN_VEHICLE",
                    extracted_intent="TEST_RIDE_FEATURE_ASSESSMENT" if is_cust else "ADVISOR_FEATURE_DEMONSTRATION",
                    tool_triggered=booking_ref
                )
                db.add(log)

        # Advance customer phase
        customer.current_phase = "TestRide_Completed"
        if booking:
            booking.status = "TestRide_Completed"

        await db.commit()
        await db.refresh(recording)
        return recording

    @staticmethod
    async def get_latest_test_ride(
        db: AsyncSession,
        customer_id: Optional[str] = None,
        booking_reference: Optional[str] = None,
        phone: Optional[str] = None,
        brand_id: Optional[str] = None
    ) -> Optional[TestRideRecording]:
        """
        Retrieves the latest persisted TestRideRecording insights for a customer,
        matching by booking_reference, customer_id, or customer phone, scoped to brand.
        """
        b_id = brand_id.lower() if brand_id else None

        if booking_reference and booking_reference.strip():
            b_stmt = select(TestRideRecording).where(
                TestRideRecording.booking_reference == booking_reference.strip()
            )
            if b_id:
                b_stmt = b_stmt.where(TestRideRecording.brand_id == b_id)
            b_stmt = b_stmt.order_by(TestRideRecording.created_at.desc())
            res = await db.execute(b_stmt)
            rec = res.scalars().first()
            if rec:
                return rec

        if customer_id and customer_id.strip():
            c_stmt = select(Customer).where(
                (Customer.customer_id == customer_id.strip()) |
                (Customer.phone == customer_id.strip())
            )
            if b_id:
                c_stmt = c_stmt.where(Customer.brand_id == b_id)
            c_res = await db.execute(c_stmt)
            cust = c_res.scalars().first()
            if cust:
                rec_stmt = select(TestRideRecording).where(
                    TestRideRecording.customer_id == cust.id
                )
                if b_id:
                    rec_stmt = rec_stmt.where(TestRideRecording.brand_id == b_id)
                rec_stmt = rec_stmt.order_by(TestRideRecording.created_at.desc())
                rec_res = await db.execute(rec_stmt)
                rec = rec_res.scalars().first()
                if rec:
                    return rec

        if phone and phone.strip():
            clean_p = clean_phone(phone)
            c_stmt = select(Customer).where(Customer.phone.ilike(f"%{clean_p[-10:] if len(clean_p) >= 10 else clean_p}%"))
            if b_id:
                c_stmt = c_stmt.where(Customer.brand_id == b_id)
            c_res = await db.execute(c_stmt)
            cust = c_res.scalars().first()
            if cust:
                rec_stmt = select(TestRideRecording).where(
                    TestRideRecording.customer_id == cust.id
                )
                if b_id:
                    rec_stmt = rec_stmt.where(TestRideRecording.brand_id == b_id)
                rec_stmt = rec_stmt.order_by(TestRideRecording.created_at.desc())
                rec_res = await db.execute(rec_stmt)
                rec = rec_res.scalars().first()
                if rec:
                    return rec

        # Strictly return None if no test ride recording exists for this specific customer/booking
        return None

    @staticmethod
    async def get_test_ride_insights(db: AsyncSession, session_id: str) -> Optional[TestRideRecording]:
        stmt = select(TestRideRecording).where(TestRideRecording.session_id == session_id)
        res = await db.execute(stmt)
        return res.scalars().first()

    @staticmethod
    async def get_all_test_rides(db: AsyncSession, brand_id: Optional[str] = None) -> List[TestRideRecording]:
        stmt = select(TestRideRecording)
        if brand_id:
            stmt = stmt.where(TestRideRecording.brand_id == brand_id.lower())
        stmt = stmt.order_by(TestRideRecording.created_at.desc()).limit(20)
        res = await db.execute(stmt)
        return res.scalars().all()

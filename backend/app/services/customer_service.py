import uuid
import re
import json
from datetime import datetime, timezone
from typing import Optional, List, Tuple, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import func
from app.models.customer import Customer, ConversationSession, InteractionLog
from app.services.cache_service import cache

def clean_phone(phone_str: str) -> str:
    """Normalizes phone numbers to standard E.164 / +91 format for consistent identification."""
    raw = re.sub(r"[\s\-\(\)\.]", "", str(phone_str or "").strip())
    if raw.startswith("+91") and len(raw) == 13:
        return raw
    if raw.startswith("91") and len(raw) == 12:
        return "+" + raw
    if raw.startswith("0") and len(raw) == 11:
        return "+91" + raw[1:]
    if len(raw) == 10:
        return "+91" + raw
    if not raw.startswith("+") and len(raw) > 0:
        return "+" + raw
    return raw

def clean_name(name_str: Optional[str]) -> str:
    """Normalizes customer name to clean Title Case for deterministic Name + Phone identification."""
    if not name_str:
        return ""
    cleaned = " ".join(str(name_str).strip().split())
    if cleaned.lower() in ("valued customer", "valued guest", "guest", "there", "customer"):
        return ""
    return cleaned.title()

def make_customer_id(name: str, phone: str, brand_id: str) -> str:
    """Generates a deterministic customer_id combining Brand + Normalized Name + Phone."""
    b_prefix = (brand_id or DEFAULT_BRAND_ID).upper()[:3]
    norm_n = clean_name(name)
    name_slug = re.sub(r"[^A-Z0-9]", "", norm_n.upper())[:12] or "USER"
    digits = re.sub(r"\D", "", str(phone or ""))
    phone_slug = digits[-10:] if len(digits) >= 10 else (digits or uuid.uuid4().hex[:6].upper())
    return f"CUST-{b_prefix}-{name_slug}-{phone_slug}"

from app.services.brand_service import BrandService

DEFAULT_BRAND_ID = "tvs"
# Flagship model per two-wheeler brand, used only as a neutral default interest.
BRAND_DEFAULT_VEHICLE = {
    "tvs": "tvs_apache_rtr_160_4v",
    "hero_motocorp": "hero_motocorp_splendor",
}
DEFAULT_VEHICLE_ID = BRAND_DEFAULT_VEHICLE[DEFAULT_BRAND_ID]
DEFAULT_BUDGET_RANGE = "₹80,000 – ₹1,50,000"

def resolve_brand(brand_id: Optional[str] = None) -> str:
    if brand_id and brand_id.strip():
        return brand_id.strip().lower()
    try:
        active = BrandService.get_active_brand()
        if active and active.id:
            return active.id.lower()
    except Exception:
        pass
    return DEFAULT_BRAND_ID

def default_vehicle_for_brand(brand_id: Optional[str]) -> str:
    """Returns the brand's flagship vehicle id (first catalog vehicle if not in the static map)."""
    b_id = (brand_id or DEFAULT_BRAND_ID).lower()
    if b_id in BRAND_DEFAULT_VEHICLE:
        return BRAND_DEFAULT_VEHICLE[b_id]
    try:
        brand = BrandService.get_brand(b_id)
        if brand and brand.vehicles:
            return brand.vehicles[0].id
    except Exception:
        pass
    return DEFAULT_VEHICLE_ID

# Static fallback (name, ex-showroom price band) for two-wheeler models. Live catalog values
# from BrandService take precedence via lookup_vehicle_price().
VEHICLE_PRICE_MAP = {
    # TVS Motor
    "tvs_apache_rtr_160_4v": ("TVS Apache RTR 160 4V", "₹1,14,390 – ₹1,44,690"),
    "tvs_apache_rtr_200_4v": ("TVS Apache RTR 200 4V", "₹1,48,240 – ₹1,53,290"),
    "tvs_apache_rtr_310": ("TVS Apache RTR 310", "₹2,42,990 – ₹2,63,990"),
    "tvs_apache_rr_310": ("TVS Apache RR 310", "₹2,79,000"),
    "tvs_ronin_225": ("TVS Ronin", "₹1,49,200 – ₹1,72,700"),
    "tvs_raider_125_igo": ("TVS Raider 125 iGO", "₹95,219 – ₹1,02,735"),
    "tvs_radeon": ("TVS Radeon", "₹62,405 – ₹95,954"),
    "tvs_star_city_plus": ("TVS Star City+", "₹69,600 – ₹79,600"),
    "tvs_sport": ("TVS Sport", "₹66,358 – ₹68,516"),
    "tvs_jupiter_disc_smartxonnect": ("TVS Jupiter Disc SmartXonnect", "₹90,441 – ₹91,591"),
    "tvs_jupiter_125_smartxonnect": ("TVS Jupiter 125 SmartXonnect", "₹89,935"),
    "tvs_ntorq": ("TVS Ntorq", "₹84,000 – ₹95,000"),
    "tvs_zest_110": ("TVS Zest 110", "₹65,450 – ₹82,549"),
    "tvs_orbiter": ("TVS Orbiter", "₹1,03,650 – ₹1,06,804"),
    "tvs_iqube": ("TVS iQube", "₹94,434 – ₹1,58,834"),
    "tvs_x": ("TVS X", "₹2,66,141"),
    # Hero MotoCorp
    "hero_motocorp_splendor": ("Hero Splendor+", "₹75,141 – ₹77,988"),
    "hero_motocorp_super_splendor_xtec": ("Hero Super Splendor XTEC", "₹84,448 – ₹85,844"),
    "hero_motocorp_hf_deluxe": ("Hero HF Deluxe", "₹62,002 – ₹68,522"),
    "hero_motocorp_passion_plus": ("Hero Passion Plus", "₹76,941 – ₹78,324"),
    "hero_motocorp_glamour_x": ("Hero Glamour X", "₹87,998 – ₹91,998"),
    "hero_motocorp_xtreme_125r": ("Hero Xtreme 125R", "₹92,500 – ₹1,04,500"),
    "hero_motocorp_xtreme_160r_4v": ("Hero Xtreme 160R 4V", "₹1,27,300 – ₹1,32,800"),
    "hero_motocorp_xpulse_210": ("Hero Xpulse 210", "₹1,40,000"),
    "hero_motocorp_xpulse_200_4v": ("Hero Xpulse 200 4V", "₹1,47,000 – ₹1,54,797"),
    "hero_motocorp_karizma_xmr": ("Hero Karizma XMR", "₹1,84,144 – ₹1,85,757"),
    "hero_motocorp_destini_125": ("Hero Destini 125", "₹75,838 – ₹84,919"),
    "hero_motocorp_pleasure_plus_xtec": ("Hero Pleasure Plus XTEC", "₹69,766 – ₹75,712"),
    "hero_motocorp_xoom": ("Hero Xoom", "₹72,351 – ₹77,283"),
    "hero_motocorp_xoom_125": ("Hero Xoom 125", "₹80,494 – ₹86,025"),
    "hero_motocorp_xoom_160": ("Hero Xoom 160", "₹1,20,000"),
}

def lookup_vehicle_price(vehicle_id: Optional[str]) -> Tuple[str, str]:
    """(display name, price band) for a vehicle id; live brand catalogs first, then static map."""
    vid = (vehicle_id or "").lower()
    try:
        for summary in BrandService.list_brands():
            brand = BrandService.get_brand(summary.id)
            for v in (brand.vehicles if brand else []):
                if v.id.lower() == vid:
                    return (v.name, v.price_range or DEFAULT_BUDGET_RANGE)
    except Exception:
        pass
    if vid in VEHICLE_PRICE_MAP:
        return VEHICLE_PRICE_MAP[vid]
    return (vid.replace("_", " ").title() if vid else "Two-Wheeler", DEFAULT_BUDGET_RANGE)

FEATURE_PATTERNS = [
    (r"\b(abs|dual[\s-]*channel|single[\s-]*channel|disc\s*brake|braking|brakes?|rlp|panic\s*brake)\b", "ABS & Braking Confidence"),
    (r"\b(pickup|pick[\s-]*up|acceleration|0[\s-]*60|torque|bhp|ps\b|power|cc\b|engine|refinement|vibration)\b", "Engine Pickup & Acceleration"),
    (r"\b(handling|cornering|corners?|lean|chassis|agile|traffic|filtering|flickable)\b", "Handling & Cornering"),
    (r"\b(suspension|usd|upside[\s-]*down|mono[\s-]*shock|telescopic|potholes?|ride\s*quality|bumps?)\b", "Suspension & Ride Quality"),
    (r"\b(seat\s*height|height|reach|flat[\s-]*foot|short\s*rider|tall|ergonomic|riding\s*posture|posture|kerb\s*weight|weight|heavy|light)\b", "Seat Height & Rider Fit"),
    (r"\b(pillion|wife|husband|family|back\s*seat|grab\s*rail|two[\s-]*up)\b", "Pillion Comfort"),
    (r"\b(mileage|kmpl|km/l|average|fuel|tank|range|battery|charging|charger|ev|electric)\b", "Mileage / Range & Charging"),
    (r"\b(riding\s*modes?|sport\s*mode|rain\s*mode|urban\s*mode|eco\s*mode|power\s*mode|traction|slipper\s*clutch|quickshifter|cruise)\b", "Riding Modes & Rider Aids"),
    (r"\b(tft|smartxonnect|bluetooth|connected|navigation|turn[\s-]*by[\s-]*turn|map|app|console|cluster|display|call\s*alert)\b", "TFT Display & Bluetooth Connectivity"),
    (r"\b(helmet|safety|visibility|led|headlamp|projector|drl|side[\s-]*stand)\b", "Safety, Helmet & LED Lighting"),
    (r"\b(under[\s-]*seat|storage|boot|usb|charging\s*port|type[\s-]*c|floorboard|practical)\b", "Storage & Practicality"),
    (r"\b(emi|loan|finance|down\s*payment|interest\s*rate|on[\s-]*road|price|cost|discount|exchange|insurance)\b", "On-Road Pricing & Two-Wheeler EMI"),
]

# (vehicle_id, display name, regex) for two-wheeler models commonly discussed in the showroom.
BIKE_PATTERNS = [
    ("tvs_apache_rtr_160_4v", "TVS Apache RTR 160 4V", r"\b(apache\s*rtr\s*160|rtr\s*160|apache\s*160)\b"),
    ("tvs_apache_rtr_200_4v", "TVS Apache RTR 200 4V", r"\b(apache\s*rtr\s*200|rtr\s*200|apache\s*200)\b"),
    ("tvs_apache_rtr_310", "TVS Apache RTR 310", r"\b(apache\s*rtr\s*310|rtr\s*310|rtr310)\b"),
    ("tvs_apache_rr_310", "TVS Apache RR 310", r"\b(apache\s*rr\s*310|rr\s*310|rr310)\b"),
    ("tvs_ronin_225", "TVS Ronin", r"\b(ronin)\b"),
    ("tvs_raider_125_igo", "TVS Raider 125 iGO", r"\b(raider)\b"),
    ("tvs_radeon", "TVS Radeon", r"\b(radeon)\b"),
    ("tvs_star_city_plus", "TVS Star City+", r"\b(star\s*city)\b"),
    ("tvs_jupiter_125_smartxonnect", "TVS Jupiter 125 SmartXonnect", r"\b(jupiter\s*125)\b"),
    ("tvs_jupiter_disc_smartxonnect", "TVS Jupiter Disc SmartXonnect", r"\b(jupiter(?!\s*125))\b"),
    ("tvs_ntorq", "TVS Ntorq", r"\b(ntorq|n\s*torq)\b"),
    ("tvs_orbiter", "TVS Orbiter", r"\b(orbiter)\b"),
    ("tvs_zest_110", "TVS Zest 110", r"\b(zest|scooty)\b"),
    ("tvs_iqube", "TVS iQube", r"\b(iqube|i\s*qube)\b"),
    ("tvs_x", "TVS X", r"\b(tvs\s*x)\b"),
    ("hero_motocorp_super_splendor_xtec", "Hero Super Splendor XTEC", r"\b(super\s*splendor)\b"),
    ("hero_motocorp_splendor", "Hero Splendor+", r"\b(splendor(?!\s*xtec)|splendor\s*plus)\b"),
    ("hero_motocorp_hf_deluxe", "Hero HF Deluxe", r"\b(hf\s*deluxe|hf\s*100)\b"),
    ("hero_motocorp_passion_plus", "Hero Passion Plus", r"\b(passion)\b"),
    ("hero_motocorp_glamour_x", "Hero Glamour X", r"\b(glamour)\b"),
    ("hero_motocorp_xtreme_125r", "Hero Xtreme 125R", r"\b(xtreme\s*125)\b"),
    ("hero_motocorp_xtreme_160r_4v", "Hero Xtreme 160R 4V", r"\b(xtreme\s*160)\b"),
    ("hero_motocorp_xpulse_210", "Hero Xpulse 210", r"\b(x\s*pulse\s*210)\b"),
    ("hero_motocorp_xpulse_200_4v", "Hero Xpulse 200 4V", r"\b(x\s*pulse(?!\s*210))\b"),
    ("hero_motocorp_karizma_xmr", "Hero Karizma XMR", r"\b(karizma|xmr)\b"),
    ("hero_motocorp_destini_125", "Hero Destini 125", r"\b(destini)\b"),
    ("hero_motocorp_pleasure_plus_xtec", "Hero Pleasure Plus XTEC", r"\b(pleasure)\b"),
    ("hero_motocorp_xoom_160", "Hero Xoom 160", r"\b(xoom\s*160)\b"),
    ("hero_motocorp_xoom_125", "Hero Xoom 125", r"\b(xoom\s*125)\b"),
    ("hero_motocorp_xoom", "Hero Xoom", r"\b(xoom(?!\s*1[26]\d))\b"),
]

def _catalog_vehicle_patterns() -> List[Tuple[str, str, str]]:
    """Builds name-matching patterns from the live brand catalogs so crawled ids resolve exactly."""
    patterns: List[Tuple[str, str, str]] = []
    try:
        for summary in BrandService.list_brands():
            brand = BrandService.get_brand(summary.id)
            for v in (brand.vehicles if brand else []):
                short = re.sub(r"^(tvs|hero|hero motocorp)\s+", "", v.name.strip(), flags=re.IGNORECASE)
                short = re.sub(r"\s*\(.*?\)", "", short).strip()
                if len(short) >= 3:
                    patterns.append((v.id, v.name, r"\b" + re.escape(short.lower()).replace("\\ ", r"\s*") + r"\b"))
    except Exception:
        pass
    # Longer names first so "Apache RTR 200 4V" wins over "Apache".
    patterns.sort(key=lambda x: -len(x[2]))
    return patterns

def _parse_rupee_amount(num: str, unit: str) -> Optional[int]:
    """Converts '1.2' + 'lakh' / '85' + 'k' / '85000' + '' into rupees."""
    try:
        val = float(num.replace(",", ""))
    except ValueError:
        return None
    unit = (unit or "").lower()
    if unit.startswith("l"):
        return int(val * 100000)
    if unit in ("k", "thousand", "hazaar", "hazar"):
        return int(val * 1000)
    return int(val) if val >= 1000 else None

def _fmt_inr(amount: int) -> str:
    """Formats rupees in Indian digit grouping, e.g. 125000 -> ₹1,25,000."""
    s = str(int(amount))
    if len(s) <= 3:
        return f"₹{s}"
    last3, rest = s[-3:], s[:-3]
    groups = []
    while len(rest) > 2:
        groups.insert(0, rest[-2:])
        rest = rest[:-2]
    if rest:
        groups.insert(0, rest)
    return "₹" + ",".join(groups + [last3])

_AMOUNT = r"(\d+(?:,\d{2,3})*(?:\.\d+)?)\s*(lakhs?|lacs?|l\b|k\b|thousand|hazaa?r)?"

def extract_budget(text: str) -> Optional[str]:
    """Extracts a two-wheeler budget (typically ₹60k – ₹3L) from free text."""
    t = (text or "").lower()
    m = re.search(r"(?:₹|rs\.?\s*)?" + _AMOUNT + r"\s*(?:to|\-|–|and)\s*(?:₹|rs\.?\s*)?" + _AMOUNT, t)
    if m:
        unit_hi = m.group(4) or m.group(2) or ""
        lo = _parse_rupee_amount(m.group(1), m.group(2) or unit_hi)
        hi = _parse_rupee_amount(m.group(3), unit_hi)
        if lo and hi and 30000 <= lo <= hi <= 1500000:
            return f"{_fmt_inr(lo)} – {_fmt_inr(hi)}"
    m = re.search(r"(?:budget|under|around|upto|up\s*to|within|below|approx|max|₹|rs\.?)\s*(?:is\s*|of\s*|hai\s*)?(?:₹|rs\.?\s*)?" + _AMOUNT, t)
    if m:
        val = _parse_rupee_amount(m.group(1), m.group(2) or "")
        if val and 30000 <= val <= 1500000:
            low = int(val * 0.85 / 1000) * 1000
            high = int(val * 1.1 / 1000) * 1000
            return f"~{_fmt_inr(val)} ({_fmt_inr(low)} – {_fmt_inr(high)} range)"
    return None

def extract_conversation_intelligence(
    messages: List[Dict[str, Any]],
    default_vehicle_id: str = DEFAULT_VEHICLE_ID,
    existing_budget: Optional[str] = None
) -> Dict[str, Any]:
    """
    Analyzes conversation messages (both Customer and AI) to extract:
    - interested_cars: list of two-wheeler model names discussed (field name kept for API compatibility)
    - primary_vehicle_id: resolved vehicle_id
    - interested_features: list of specific features customer showed interest in
    - budget: extracted budget or price range discussed
    - key_points_summary: human-readable summary of the conversation
    """
    full_text = " ".join([str(m.get("text") or m.get("message") or "") for m in messages if m.get("speaker") != "system"])
    customer_text = " ".join([str(m.get("text") or m.get("message") or "") for m in messages if m.get("speaker") == "customer"])
    combined_lower = full_text.lower()
    cust_lower = customer_text.lower()

    # 1. Detect interested two-wheeler(s): live catalog names first, then static patterns
    bike_patterns = _catalog_vehicle_patterns() + BIKE_PATTERNS
    detected: List[Tuple[str, str]] = []
    for text_blob in (cust_lower, combined_lower):
        for vid, vname, pat in bike_patterns:
            if re.search(pat, text_blob, re.IGNORECASE) and all(x[0] != vid and x[1] != vname for x in detected):
                detected.append((vid, vname))

    if not detected:
        fallback_vid = default_vehicle_id or DEFAULT_VEHICLE_ID
        detected.append((fallback_vid, lookup_vehicle_price(fallback_vid)[0]))

    primary_vid, primary_vname = detected[0]
    interested_cars = [c[1] for c in detected]

    # 2. Detect interested features
    features: List[str] = []
    for pat, label in FEATURE_PATTERNS:
        if re.search(pat, cust_lower, re.IGNORECASE):
            if label not in features:
                features.append(label)
    for pat, label in FEATURE_PATTERNS:
        if re.search(pat, combined_lower, re.IGNORECASE):
            if label not in features and len(features) < 5:
                features.append(label)
    if not features:
        features = ["Styling & Road Presence", "Mileage / Range & Charging"]

    # 3. Extract budget from dialogue (customer turns first)
    budget_str = extract_budget(cust_lower) or extract_budget(combined_lower)
    if not budget_str:
        if existing_budget and existing_budget not in ("Standard Range", ""):
            budget_str = existing_budget
        else:
            budget_str = lookup_vehicle_price(primary_vid)[1]

    feat_short = ", ".join(features[:3])
    cars_short = ", ".join(interested_cars[:2])
    summary_text = f"Interested in {cars_short} | Focus: {feat_short} | Budget: {budget_str}"

    return {
        "primary_vehicle_id": primary_vid,
        "primary_vehicle_name": primary_vname,
        "interested_cars": interested_cars,
        "interested_features": features,
        "budget": budget_str,
        "key_points_summary": summary_text,
    }

class CustomerService:
    @staticmethod
    async def get_or_create_customer_by_phone(
        db: AsyncSession,
        phone: str,
        name: Optional[str] = None,
        vehicle_id: Optional[str] = None,
        brand_id: Optional[str] = None
    ) -> Customer:
        """
        Retrieves or creates a unique customer identified by (Name + Phone Number) scoped to brand_id.
        If name is provided, matches (lower(name) == norm_name.lower() AND phone == normalized_phone).
        """
        b_id = resolve_brand(brand_id)
        normalized_phone = clean_phone(phone)
        norm_name = clean_name(name)
        cust_slug = make_customer_id(norm_name or "Valued Customer", normalized_phone, b_id)

        customer = None
        if norm_name:
            stmt = (
                select(Customer)
                .where(
                    (Customer.brand_id == b_id) &
                    (func.lower(Customer.name) == norm_name.lower()) &
                    ((Customer.phone == normalized_phone) | (Customer.phone == phone))
                )
                .options(
                    selectinload(Customer.sessions).selectinload(ConversationSession.transcripts),
                    selectinload(Customer.interactions),
                    selectinload(Customer.bookings),
                    selectinload(Customer.claims),
                )
            )
            res = await db.execute(stmt)
            customer = res.scalars().first()

            if not customer:
                stmt_placeholder = (
                    select(Customer)
                    .where(
                        (Customer.brand_id == b_id) &
                        ((Customer.phone == normalized_phone) | (Customer.phone == phone)) &
                        (func.lower(Customer.name).in_(["valued customer", "valued guest", "guest", "there"]))
                    )
                    .options(
                        selectinload(Customer.sessions).selectinload(ConversationSession.transcripts),
                        selectinload(Customer.interactions),
                        selectinload(Customer.bookings),
                        selectinload(Customer.claims),
                    )
                )
                res_ph = await db.execute(stmt_placeholder)
                placeholder_cust = res_ph.scalars().first()
                if placeholder_cust:
                    placeholder_cust.name = norm_name
                    placeholder_cust.customer_id = cust_slug
                    await db.commit()
                    customer = placeholder_cust
        else:
            stmt = (
                select(Customer)
                .where(
                    (Customer.brand_id == b_id) &
                    ((Customer.phone == normalized_phone) | (Customer.phone == phone) | (Customer.customer_id == cust_slug))
                )
                .order_by(Customer.updated_at.desc())
                .options(
                    selectinload(Customer.sessions).selectinload(ConversationSession.transcripts),
                    selectinload(Customer.interactions),
                    selectinload(Customer.bookings),
                    selectinload(Customer.claims),
                )
            )
            res = await db.execute(stmt)
            customer = res.scalars().first()

        if customer:
            return customer

        v_id = vehicle_id or default_vehicle_for_brand(b_id)
        default_budget = lookup_vehicle_price(v_id)[1]

        customer = Customer(
            customer_id=cust_slug,
            brand_id=b_id,
            name=norm_name if norm_name else "Valued Customer",
            phone=normalized_phone,
            city="Mumbai",
            preferred_language="Hinglish",
            current_phase="PRE_SALES",
            interested_vehicle_id=v_id,
            interested_variant=None,
            budget_range=default_budget,
            kyc_status="PENDING"
        )
        db.add(customer)
        await db.commit()
        await db.refresh(customer)
        return customer

    @staticmethod
    async def get_or_create_default_customer(
        db: AsyncSession,
        phone: Optional[str] = None,
        name: Optional[str] = None,
        brand_id: Optional[str] = None
    ) -> Optional[Customer]:
        """Returns the customer for an entered phone, else the most recent REAL customer of the brand.

        Never fabricates identities / PII: when no phone is supplied and the brand has no
        customers yet, returns None and callers must respond with 404 / empty payloads.
        """
        b_id = resolve_brand(brand_id)
        if phone:
            return await CustomerService.get_or_create_customer_by_phone(db, phone=phone, name=name, brand_id=b_id)

        stmt = (
            select(Customer)
            .where(Customer.brand_id == b_id)
            .order_by(Customer.updated_at.desc(), Customer.id.desc())
            .options(
                selectinload(Customer.sessions).selectinload(ConversationSession.transcripts),
                selectinload(Customer.interactions),
                selectinload(Customer.bookings),
                selectinload(Customer.claims),
            )
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def identify_or_register_customer(
        db: AsyncSession,
        name: str,
        phone: str,
        session_type: str = "LIVE_CALL",
        vehicle_id: Optional[str] = None,
        brand_id: Optional[str] = None
    ) -> Tuple[Customer, ConversationSession, bool, int]:
        """
        Uniquely identifies a customer by Normalized (Name + Phone Number) and brand_id:
        - If returning customer (same Name + Phone): reuses single Customer entry, creates a NEW ConversationSession row.
        - If new customer (distinct Name + Phone): creates new Customer entry, creates a NEW ConversationSession row.
        Returns (Customer, ConversationSession, is_returning, total_session_count).
        """
        b_id = resolve_brand(brand_id)
        normalized_phone = clean_phone(phone)
        norm_name = clean_name(name) or "Valued Customer"
        cust_id_slug = make_customer_id(norm_name, normalized_phone, b_id)

        stmt = (
            select(Customer)
            .where(
                (Customer.brand_id == b_id) &
                (func.lower(Customer.name) == norm_name.lower()) &
                (Customer.phone == normalized_phone)
            )
            .options(
                selectinload(Customer.sessions),
                selectinload(Customer.interactions)
            )
        )
        result = await db.execute(stmt)
        customer = result.scalars().first()

        is_returning = False
        if customer:
            is_returning = True
            if vehicle_id:
                customer.interested_vehicle_id = vehicle_id
            customer.updated_at = datetime.now(timezone.utc)
            await db.commit()
        else:
            v_id = vehicle_id or default_vehicle_for_brand(b_id)
            default_budget = lookup_vehicle_price(v_id)[1]
            customer = Customer(
                customer_id=cust_id_slug,
                brand_id=b_id,
                name=norm_name,
                phone=normalized_phone,
                city="Mumbai",
                preferred_language="Hinglish",
                current_phase="PRE_SALES",
                interested_vehicle_id=v_id,
                interested_variant=None,
                budget_range=default_budget
            )
            db.add(customer)
            await db.commit()
            await db.refresh(customer)

        # Always create a NEW ConversationSession (1:Many relationship against this Customer's Name + Phone)
        session_code = f"SESS-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        init_intel = extract_conversation_intelligence(
            [],
            default_vehicle_id=vehicle_id or customer.interested_vehicle_id or default_vehicle_for_brand(b_id),
            existing_budget=customer.budget_range
        )
        new_session = ConversationSession(
            session_id=session_code,
            brand_id=b_id,
            customer_id=customer.id,
            session_type=session_type,
            vehicle_id=vehicle_id or customer.interested_vehicle_id or default_vehicle_for_brand(b_id),
            summary=json.dumps(init_intel)
        )
        db.add(new_session)
        await db.commit()
        await db.refresh(new_session)
        cache.invalidate("sales_leads_")

        # Count total sessions for customer
        count_stmt = select(func.count(ConversationSession.id)).where(ConversationSession.customer_id == customer.id)
        count_res = await db.execute(count_stmt)
        total_sessions = count_res.scalar() or 1

        # Re-fetch customer with eager loads
        stmt_reload = (
            select(Customer)
            .where(Customer.id == customer.id)
            .options(
                selectinload(Customer.sessions).selectinload(ConversationSession.transcripts),
                selectinload(Customer.interactions)
            )
        )
        res_reload = await db.execute(stmt_reload)
        customer = res_reload.scalars().first()

        return customer, new_session, is_returning, total_sessions

    @staticmethod
    async def get_customer_by_id(db: AsyncSession, customer_id: str, brand_id: Optional[str] = None) -> Optional[Customer]:
        stmt = (
            select(Customer)
            .where(Customer.customer_id == customer_id)
            .options(
                selectinload(Customer.sessions).selectinload(ConversationSession.transcripts),
                selectinload(Customer.interactions),
                selectinload(Customer.bookings),
                selectinload(Customer.claims),
            )
        )
        if brand_id:
            stmt = stmt.where(Customer.brand_id == resolve_brand(brand_id))
        result = await db.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def get_customer_by_phone(
        db: AsyncSession,
        phone: str,
        brand_id: Optional[str] = None,
        name: Optional[str] = None
    ) -> Optional[Customer]:
        normalized = clean_phone(phone)
        norm_name = clean_name(name)
        b_id = resolve_brand(brand_id)
        if norm_name:
            stmt = (
                select(Customer)
                .where(
                    (Customer.phone == normalized) &
                    (func.lower(Customer.name) == norm_name.lower()) &
                    (Customer.brand_id == b_id)
                )
                .options(
                    selectinload(Customer.sessions).selectinload(ConversationSession.transcripts),
                    selectinload(Customer.interactions),
                    selectinload(Customer.bookings),
                    selectinload(Customer.claims),
                )
            )
            result = await db.execute(stmt)
            cust = result.scalars().first()
            if cust:
                return cust

        stmt = (
            select(Customer)
            .where((Customer.phone == normalized) & (Customer.brand_id == b_id))
            .order_by(Customer.updated_at.desc())
            .options(
                selectinload(Customer.sessions).selectinload(ConversationSession.transcripts),
                selectinload(Customer.interactions),
                selectinload(Customer.bookings),
                selectinload(Customer.claims),
            )
        )
        result = await db.execute(stmt)
        cust = result.scalars().first()
        if not cust:
            stmt_any = (
                select(Customer)
                .where(Customer.phone == normalized)
                .order_by(Customer.updated_at.desc())
                .options(
                    selectinload(Customer.sessions).selectinload(ConversationSession.transcripts),
                    selectinload(Customer.interactions),
                    selectinload(Customer.bookings),
                    selectinload(Customer.claims),
                )
            )
            r_any = await db.execute(stmt_any)
            cust = r_any.scalars().first()
        return cust

    @staticmethod
    async def log_interaction(
        db: AsyncSession,
        customer_id_str: str,
        speaker: str,
        message: str,
        channel: str = "VOICE_LIVE",
        session_id_str: Optional[str] = None,
        intent: Optional[str] = None,
        tool: Optional[str] = None,
        brand_id: Optional[str] = None
    ) -> Optional[InteractionLog]:
        b_id = resolve_brand(brand_id)
        customer = None
        if customer_id_str and customer_id_str != "GUEST-TRANSIENT":
            customer = await CustomerService.get_customer_by_id(db, customer_id_str, brand_id=b_id)
            if not customer:
                customer = await CustomerService.get_customer_by_phone(db, customer_id_str, brand_id=b_id)
        if not customer:
            stmt_latest = select(Customer).where(Customer.brand_id == b_id).order_by(Customer.updated_at.desc())
            res_latest = await db.execute(stmt_latest)
            customer = res_latest.scalars().first()
        if not customer:
            return InteractionLog(
                id=0,
                brand_id=b_id,
                session_id=None,
                customer_id=0,
                channel=channel,
                speaker=speaker,
                message=message,
                extracted_intent=intent,
                tool_triggered=tool
            )
        
        session_db_id = None
        sess = None
        if session_id_str:
            stmt = select(ConversationSession).where(ConversationSession.session_id == session_id_str)
            res = await db.execute(stmt)
            sess = res.scalars().first()
            if not sess:
                sess = ConversationSession(
                    session_id=session_id_str,
                    brand_id=b_id,
                    customer_id=customer.id,
                    session_type="LIVE_CALL" if channel == "VOICE_LIVE" else "CHAT_BOT",
                    vehicle_id=customer.interested_vehicle_id or default_vehicle_for_brand(b_id),
                    summary=f"Virtual Showroom Consultation for {customer.name}"
                )
                db.add(sess)
                await db.commit()
                await db.refresh(sess)
            session_db_id = sess.id

        log = InteractionLog(
            brand_id=b_id,
            session_id=session_db_id,
            customer_id=customer.id,
            channel=channel,
            speaker=speaker,
            message=message,
            extracted_intent=intent,
            tool_triggered=tool
        )
        db.add(log)
        await db.flush()

        # Continuously update conversation intelligence (two-wheeler, features, budget) on each turn
        if sess:
            logs_res = await db.execute(
                select(InteractionLog)
                .where(InteractionLog.session_id == sess.id)
                .order_by(InteractionLog.created_at.asc())
            )
            sess_logs = logs_res.scalars().all()
            msg_list = [{"speaker": l.speaker, "message": l.message} for l in sess_logs]
            intel = extract_conversation_intelligence(
                msg_list,
                default_vehicle_id=sess.vehicle_id or customer.interested_vehicle_id or default_vehicle_for_brand(b_id),
                existing_budget=customer.budget_range
            )
            sess.vehicle_id = intel["primary_vehicle_id"]
            sess.summary = json.dumps(intel)
            customer.interested_vehicle_id = intel["primary_vehicle_id"]
            customer.budget_range = intel["budget"]
            customer.updated_at = datetime.now(timezone.utc)

        await db.commit()
        await db.refresh(log)
        cache.invalidate("sales_leads_")
        return log

    @staticmethod
    async def get_customer_sessions(db: AsyncSession, customer_id_str: str, brand_id: Optional[str] = None) -> List[ConversationSession]:
        b_id = resolve_brand(brand_id)
        customer = await CustomerService.get_customer_by_id(db, customer_id_str, brand_id=b_id)
        if not customer:
            customer = await CustomerService.get_customer_by_phone(db, customer_id_str, brand_id=b_id)
        if not customer:
            return []
        stmt = (
            select(ConversationSession)
            .where(ConversationSession.customer_id == customer.id)
            .options(selectinload(ConversationSession.transcripts))
            .order_by(ConversationSession.created_at.desc())
        )
        if brand_id:
            stmt = stmt.where(ConversationSession.brand_id == b_id)
        res = await db.execute(stmt)
        return res.scalars().all()

    @staticmethod
    async def save_full_session_transcript(
        db: AsyncSession,
        session_id_str: str,
        customer_id_str: Optional[str] = None,
        customer_name: Optional[str] = None,
        customer_phone: Optional[str] = None,
        vehicle_id: Optional[str] = None,
        channel: str = "VOICE_LIVE",
        messages: List[dict] = [],
        brand_id: Optional[str] = None
    ) -> ConversationSession:
        """
        Guarantees full persistence of conversation session and all its transcript turns upon End Call,
        and extracts Interested Two-Wheeler, Features, and Budget for the Sales Consultant.
        """
        b_id = resolve_brand(brand_id)
        customer = None
        if customer_phone and customer_phone.strip():
            customer = await CustomerService.get_or_create_customer_by_phone(
                db,
                phone=customer_phone,
                name=customer_name or "Valued Customer",
                vehicle_id=vehicle_id or default_vehicle_for_brand(b_id),
                brand_id=b_id
            )
        elif customer_id_str and customer_id_str != "GUEST-TRANSIENT":
            customer = await CustomerService.get_customer_by_id(db, customer_id_str, brand_id=b_id)
            
        if not customer:
            stmt_latest = select(Customer).where(Customer.brand_id == b_id).order_by(Customer.updated_at.desc())
            res_latest = await db.execute(stmt_latest)
            customer = res_latest.scalars().first()
            if not customer:
                return ConversationSession(
                    id=0,
                    session_id=session_id_str,
                    brand_id=b_id,
                    customer_id=0,
                    session_type="LIVE_CALL" if channel == "VOICE_LIVE" else "CHAT_BOT",
                    vehicle_id=vehicle_id or default_vehicle_for_brand(b_id)
                )

        stmt = select(ConversationSession).where(ConversationSession.session_id == session_id_str)
        res = await db.execute(stmt)
        sess = res.scalars().first()
        if not sess:
            sess = ConversationSession(
                session_id=session_id_str,
                brand_id=b_id,
                customer_id=customer.id,
                session_type="LIVE_CALL" if channel == "VOICE_LIVE" else "CHAT_BOT",
                vehicle_id=vehicle_id or customer.interested_vehicle_id or default_vehicle_for_brand(b_id),
                summary=f"Virtual Showroom Consultation for {customer.name}"
            )
            db.add(sess)
            await db.commit()
            await db.refresh(sess)
        elif sess.customer_id != customer.id:
            sess.customer_id = customer.id

        # Query existing messages for deduplication
        existing_stmt = select(InteractionLog).where(InteractionLog.session_id == sess.id).order_by(InteractionLog.created_at.asc())
        e_res = await db.execute(existing_stmt)
        existing_logs = list(e_res.scalars().all())
        existing_texts = {(l.speaker, l.message.strip()) for l in existing_logs}

        for m in messages:
            spk = m.get("speaker", "customer")
            if spk == "system":
                continue
            text = m.get("text", "").strip()
            if not text or (spk, text) in existing_texts:
                continue

            log = InteractionLog(
                brand_id=b_id,
                session_id=sess.id,
                customer_id=customer.id,
                channel=channel or "VOICE_LIVE",
                speaker=spk,
                message=text,
                extracted_intent=m.get("toolCall"),
                tool_triggered=m.get("toolCall")
            )
            db.add(log)
            existing_logs.append(log)
            existing_texts.add((spk, text))

        sess.ended_at = datetime.now(timezone.utc)
        
        # Extract Two-Wheeler, Features, and Budget intelligence from the complete session dialogue
        all_turn_dicts = [{"speaker": l.speaker, "message": l.message} for l in existing_logs]
        intel = extract_conversation_intelligence(
            all_turn_dicts,
            default_vehicle_id=vehicle_id or sess.vehicle_id or customer.interested_vehicle_id or default_vehicle_for_brand(b_id),
            existing_budget=customer.budget_range
        )
        sess.vehicle_id = intel["primary_vehicle_id"]
        sess.summary = json.dumps(intel)
        db.add(sess)

        # Update Customer profile with latest interested two-wheeler, budget, and checklist
        from app.services.checklist_service import ChecklistService
        from app.models.booking import TestDriveBooking
        from sqlalchemy.orm.attributes import flag_modified

        veh_id = intel["primary_vehicle_id"]
        customer.interested_vehicle_id = veh_id
        customer.budget_range = intel["budget"]
        customer.updated_at = datetime.now(timezone.utc)

        customer_dialogues = " ".join([d["message"] for d in all_turn_dicts if d.get("speaker") == "customer"])
        extracted_checklist = ChecklistService.extract_checklist_items(customer_dialogues, vehicle_id=veh_id)
        if not extracted_checklist:
            extracted_checklist = [f"Demonstrate / Discuss {feat}" for feat in intel["interested_features"]]
        if not extracted_checklist:
            extracted_checklist = ChecklistService.get_static_checklist(veh_id)

        # Merge with any previous conversation checklist items so multiple conversations accumulate asks
        prev_checklist = list(customer.advisor_checklist or [])
        merged_checklist = list(dict.fromkeys(list(extracted_checklist) + prev_checklist))[:6]
        customer.advisor_checklist = merged_checklist
        flag_modified(customer, "advisor_checklist")
        db.add(customer)

        # Update any active test-ride bookings for this customer
        booking_stmt = select(TestDriveBooking).where(TestDriveBooking.customer_id == customer.id)
        b_res = await db.execute(booking_stmt)
        for b in b_res.scalars().all():
            b.advisor_checklist = merged_checklist
            flag_modified(b, "advisor_checklist")
            db.add(b)

        await db.commit()
        await db.refresh(sess)
        cache.invalidate("sales_leads_")
        return sess

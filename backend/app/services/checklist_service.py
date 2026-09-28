import re
import logging
from typing import List, Optional, Dict, Any, Callable
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.models.customer import Customer
from app.models.booking import TestDriveBooking
from app.services.catalog_service import CatalogService

logger = logging.getLogger("checklist_service")

# ---------------------------------------------------------------------------
# Two-wheeler (motorcycle + scooter) Sales Consultant demo checklist.
#
# The checklist is built from the customer's stated interests and is filled
# with REAL specs of the vehicle from the active brand catalog
# (backend/data/brands/<brand>.json) whenever they are available, so it works
# for any two-wheeler brand (TVS Motor, Hero MotoCorp, ...) without per-model
# hardcoding.
# ---------------------------------------------------------------------------

# Optional hand-curated overrides keyed by vehicle id. Catalog-derived
# checklists are used for every vehicle not listed here.
STATIC_VEHICLE_CHECKLISTS: Dict[str, List[str]] = {}

DEFAULT_CHECKLIST = [
    "Demonstrate Engine Pickup, Throttle Response & Braking Feel (ABS / CBS) on the test ride",
    "Showcase Instrument Cluster, Bluetooth Connectivity & Navigation Features",
    "Check Rider Fit: Seat Height, Kerb Weight, Riding Posture & Pillion Comfort",
]

HELMET_SAFETY_ITEM = "Keep Helmet & Riding Gear ready and verify Riding Licence before the test ride"


def _v(vehicle: Any, attr: str) -> str:
    """Returns a cleaned string value for an (optional) vehicle attribute."""
    if vehicle is None:
        return ""
    val = getattr(vehicle, attr, None)
    if val is None:
        return ""
    if isinstance(val, (list, tuple)):
        return ", ".join(str(x).strip() for x in val if str(x).strip())
    return str(val).strip()


def _join(*parts: str, sep: str = " / ") -> str:
    return sep.join(p for p in parts if p)


def _is_ev(vehicle: Any) -> bool:
    fuel = (_v(vehicle, "fuel_or_battery") + " " + _v(vehicle, "category")).lower()
    return "electric" in fuel or "kwh" in fuel


def _is_scooter(vehicle: Any) -> bool:
    return "scooter" in _v(vehicle, "category").lower() or "moped" in _v(vehicle, "category").lower()


def _highlight_matching(vehicle: Any, words: List[str]) -> str:
    """First catalog highlight / variant feature that mentions any of `words`."""
    if vehicle is None:
        return ""
    pool: List[str] = list(getattr(vehicle, "key_highlights", None) or [])
    for var in getattr(vehicle, "variants", None) or []:
        pool.extend(getattr(var, "key_features", None) or [])
    for h in pool:
        low = str(h).lower()
        if any(w in low for w in words):
            return str(h).strip()
    return ""


# ---- Item builders: (vehicle or None) -> checklist item text ----------------

def _engine_item(v: Any) -> str:
    if _is_ev(v):
        spec = _join(_v(v, "max_power"), _v(v, "max_torque"))
        return f"Demonstrate Instant Electric Pickup{f' ({spec})' if spec else ''} & Riding Modes on the test ride"
    cc = _v(v, "displacement_cc")
    if cc and "cc" not in cc.lower():
        cc = f"{cc}cc"
    spec = _join(cc, _v(v, "max_power"), _v(v, "max_torque"))
    if not spec:
        spec = _v(v, "engine_specs")
    return f"Showcase Engine Performance{f' ({spec})' if spec else ''}: Pickup, Refinement & Gear Shifts"


def _mileage_item(v: Any) -> str:
    if _is_ev(v):
        return _range_item(v)
    mil = _v(v, "range_or_mileage")
    tank = _v(v, "fuel_tank_or_battery")
    detail = _join(mil, f"{tank} tank" if tank else "", sep=", ")
    return f"Walk through Fuel Efficiency{f' ({detail})' if detail else ''} & Running-Cost per km"


def _range_item(v: Any) -> str:
    rng = _v(v, "range_or_mileage")
    batt = _v(v, "fuel_tank_or_battery") or _v(v, "fuel_or_battery")
    detail = _join(rng, batt, sep=", ")
    return f"Demonstrate EV Range{f' ({detail})' if detail else ''}, Home Charging Time & Charger Options"


def _braking_item(v: Any) -> str:
    brk = _v(v, "braking") or _highlight_matching(v, ["abs", "disc", "cbs", "sbt", "brake"])
    return f"Demonstrate Braking Confidence{f' ({brk})' if brk else ' (ABS / CBS, Disc vs Drum)'} in a safe zone"


def _modes_item(v: Any) -> str:
    modes = _v(v, "riding_modes")
    tc = _highlight_matching(v, ["traction", "slipper"])
    detail = _join(f"Modes: {modes}" if modes else "", tc, sep="; ")
    return f"Showcase Riding Modes & Rider Aids{f' ({detail})' if detail else ''}"


def _connectivity_item(v: Any) -> str:
    feat = _highlight_matching(v, ["tft", "bluetooth", "smartxonnect", "connect", "navigation", "map", "cluster", "lcd"])
    return f"Demonstrate {feat or 'Digital Cluster, Bluetooth Connectivity & Turn-by-Turn Navigation'} (pair customer's phone)"


def _suspension_item(v: Any) -> str:
    feat = _highlight_matching(v, ["usd", "upside", "monoshock", "suspension", "fork", "shock"])
    return f"Demonstrate Ride Quality over Speed-Breakers & Potholes{f' ({feat})' if feat else ' (Front Forks / Rear Monoshock)'}"


def _rider_fit_item(v: Any) -> str:
    detail = _join(
        f"Seat Height {_v(v, 'seat_height')}" if _v(v, "seat_height") else "",
        f"Kerb Weight {_v(v, 'kerb_weight')}" if _v(v, "kerb_weight") else "",
        sep=", ",
    )
    return f"Check Rider Fit{f' ({detail})' if detail else ''}: Flat-Footing, Handling & Riding Posture"


def _storage_item(v: Any) -> str:
    feat = _highlight_matching(v, ["storage", "under-seat", "under seat", "boot", "litre", "helmet"])
    if feat:
        return f"Showcase Practicality: {feat}"
    if _is_scooter(v) or v is None:
        return "Showcase Under-Seat Storage (Helmet Fit), Front Glovebox & USB Charging"
    return "Showcase Practicality: Luggage Mounting Options & USB Charging"


def _pillion_item(v: Any) -> str:
    return "Highlight Pillion Comfort: Seat Length, Grab Rail & Footrest Position (Two-Up Ride)"


def _top_speed_item(v: Any) -> str:
    ts = _v(v, "top_speed")
    return f"Demonstrate Highway Stability & Top-End Performance{f' (Top Speed {ts})' if ts else ''}"


def _lighting_item(v: Any) -> str:
    feat = _highlight_matching(v, ["led", "projector", "headlamp", "drl", "lamp"])
    return f"Showcase {feat or 'LED Headlamp, DRLs & Night-Time Visibility'}"


def _colors_item(v: Any) -> str:
    cols = _v(v, "colors")
    return f"Show Colour Options{f' ({cols})' if cols else ''} & Accessory Packs"


def _price_item(v: Any) -> str:
    price = _v(v, "price_range")
    return f"Walk through Ex-Showroom Pricing{f' ({price})' if price else ''}, Variant Differences, EMI & Exchange Offers"


def _helmet_item(v: Any) -> str:
    return HELMET_SAFETY_ITEM


FEATURE_KEYWORDS: List[Dict[str, Any]] = [
    {"keywords": ["engine", "power", "torque", "cc", "bhp", "ps", "pickup", "pick-up", "acceleration", "performance", "gear", "refinement", "motor"], "builder": _engine_item},
    {"keywords": ["mileage", "kmpl", "fuel efficiency", "average", "petrol cost", "fuel tank", "tank"], "builder": _mileage_item},
    {"keywords": ["range", "charging", "charge", "charger", "battery", "kwh", "ev", "electric", "home charging"], "builder": _range_item},
    {"keywords": ["abs", "brake", "braking", "disc", "drum", "cbs", "sbt", "safety", "skid"], "builder": _braking_item},
    {"keywords": ["riding mode", "ride mode", "modes", "sport mode", "rain mode", "traction", "slipper"], "builder": _modes_item},
    {"keywords": ["bluetooth", "tft", "lcd", "cluster", "display", "screen", "navigation", "map", "connect", "smartxonnect", "app", "call alert", "music"], "builder": _connectivity_item},
    {"keywords": ["suspension", "usd", "upside", "monoshock", "fork", "pothole", "speed breaker", "bump", "comfort", "ride quality"], "builder": _suspension_item},
    {"keywords": ["seat height", "height", "tall", "short", "weight", "heavy", "light", "first bike", "beginner", "new rider", "flat foot", "posture", "handling"], "builder": _rider_fit_item},
    {"keywords": ["storage", "under-seat", "under seat", "boot", "luggage", "helmet space", "glovebox", "usb"], "builder": _storage_item},
    {"keywords": ["pillion", "wife", "family", "two-up", "two up", "passenger", "back seat"], "builder": _pillion_item},
    {"keywords": ["top speed", "highway", "touring", "long ride", "long distance", "cruising"], "builder": _top_speed_item},
    {"keywords": ["headlamp", "headlight", "led", "projector", "night", "drl"], "builder": _lighting_item},
    {"keywords": ["colour", "color", "paint", "shade", "accessor"], "builder": _colors_item},
    {"keywords": ["price", "cost", "emi", "loan", "finance", "offer", "discount", "exchange", "on-road", "on road", "budget", "lakh"], "builder": _price_item},
    {"keywords": ["helmet", "riding gear", "licence", "license", "test ride", "test drive"], "builder": _helmet_item},
]


def _kw_match(kw: str, text: str) -> bool:
    """Keyword match with a left word boundary (and a right one for short tokens like 'ev', 'abs', 'cc')."""
    pattern = r"(?<![a-z])" + re.escape(kw)
    if len(kw) <= 3:
        pattern += r"(?![a-z])"
    return re.search(pattern, text) is not None


def _find_vehicle(vehicle_id: Optional[str]) -> Any:
    """Looks up a vehicle by id in the active brand first, then all brand catalogs."""
    if not vehicle_id:
        return None
    vid = vehicle_id.strip().lower()
    try:
        from app.services.brand_service import BrandService
        brands = []
        try:
            brands.append(BrandService.get_active_brand())
        except Exception:
            pass
        brands.extend(getattr(BrandService, "_brands", {}).values())
        for b in brands:
            for v in (getattr(b, "vehicles", None) or []):
                if str(v.id).lower() == vid:
                    return v
    except Exception as e:
        logger.debug(f"Vehicle lookup notice for {vehicle_id}: {e}")
    return None


class ChecklistService:
    @staticmethod
    def get_static_checklist(vehicle_id: Optional[str] = None) -> List[str]:
        """Returns a default demo checklist for the two-wheeler, built from its catalog specs."""
        if not vehicle_id:
            return list(DEFAULT_CHECKLIST)
        normalized = vehicle_id.strip().lower()
        if normalized in STATIC_VEHICLE_CHECKLISTS:
            return list(STATIC_VEHICLE_CHECKLISTS[normalized])
        vehicle = _find_vehicle(normalized)
        if vehicle is None:
            return list(DEFAULT_CHECKLIST)
        items = [
            _engine_item(vehicle),
            _braking_item(vehicle),
            _rider_fit_item(vehicle),
        ]
        if _is_ev(vehicle):
            items.append(_range_item(vehicle))
        elif _is_scooter(vehicle):
            items.append(_storage_item(vehicle))
        else:
            items.append(_connectivity_item(vehicle))
        return items

    @staticmethod
    def extract_checklist_items(
        customer_text: str,
        vehicle_id: str = "",
        existing_items: Optional[List[str]] = None
    ) -> List[str]:
        """
        Identifies the customer's asks/interests from conversation and generates
        actionable test-ride demonstration items for the Sales Consultant, filled
        with the vehicle's real catalog specs when available.
        """
        lower_text = f" {(customer_text or '').lower()} "
        items = list(existing_items or [])
        vehicle = _find_vehicle(vehicle_id)

        for entry in FEATURE_KEYWORDS:
            if any(_kw_match(kw, lower_text) for kw in entry["keywords"]):
                builder: Callable[[Any], str] = entry["builder"]
                try:
                    matched_item = builder(vehicle)
                except Exception as e:
                    logger.debug(f"Checklist builder notice: {e}")
                    matched_item = ""
                if matched_item and matched_item not in items:
                    items.append(matched_item)

        # Cap at 5 key checklist items
        if len(items) > 5:
            items = items[:5]

        return items

    @staticmethod
    async def update_customer_and_booking_checklist(
        db: AsyncSession,
        customer_id_str: str,
        vehicle_id: str,
        new_items: List[str]
    ) -> List[str]:
        """Persists updated checklist items to the Customer and active TestDriveBooking records in DB."""
        if not new_items:
            return []

        stmt = select(Customer).where(
            (Customer.customer_id == customer_id_str) | (Customer.phone == customer_id_str)
        ).options(selectinload(Customer.bookings))
        res = await db.execute(stmt)
        customer = res.scalars().first()

        if not customer:
            return new_items

        # Merge existing checklist
        current_list = list(customer.advisor_checklist or [])
        for item in new_items:
            if item not in current_list:
                current_list.append(item)
        current_list = current_list[:5]

        from sqlalchemy.orm.attributes import flag_modified
        customer.advisor_checklist = list(current_list)
        flag_modified(customer, "advisor_checklist")

        # Also update any active bookings for this customer
        for b in customer.bookings:
            if b.status in ["CONFIRMED", "PENDING", "RESERVED"]:
                b.advisor_checklist = list(current_list)
                flag_modified(b, "advisor_checklist")

        db.add(customer)
        await db.commit()
        return current_list

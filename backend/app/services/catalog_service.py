"""
Two-wheeler (motorcycle + scooter) catalog helpers.

The live source of truth is the crawled brand catalog managed by BrandService
(`data/brands/tvs.json`, `data/brands/hero_motocorp.json`). The small FALLBACK
catalog below is only used if no brand JSON can be loaded (e.g. a fresh checkout
before the crawler has run) so the API never crashes or returns an empty showroom.
"""
import re
from typing import Any, Dict, List, Optional

from app.schemas.catalog import VehicleItem, VehicleVariant, DealershipItem

PLACEHOLDER_BIKE_IMAGE = "/assets/placeholder-bike.svg"

# Ordered list of spec rows used for side-by-side two-wheeler comparisons.
# (row label, VehicleItem attribute)
COMPARISON_SPEC_ROWS = [
    ("Segment", "category"),
    ("Ex-Showroom Price", "price_range"),
    ("Engine / Motor", "engine_specs"),
    ("Displacement", "displacement_cc"),
    ("Max Power", "max_power"),
    ("Max Torque", "max_torque"),
    ("Top Speed", "top_speed"),
    ("Mileage / Range", "range_or_mileage"),
    ("Fuel Tank / Battery", "fuel_tank_or_battery"),
    ("Fuel / Power Source", "fuel_or_battery"),
    ("Kerb Weight", "kerb_weight"),
    ("Seat Height", "seat_height"),
    ("Braking & ABS", "braking"),
    ("Riding Modes", "riding_modes"),
    ("Seating", "seating_capacity"),
    ("Colours", "colors"),
    ("Key Rivals", "competitors"),
]

ELECTRIC_CATEGORIES = {"electric scooter", "electric motorcycle"}
SCOOTER_CATEGORIES = {"scooter", "performance scooter", "electric scooter", "moped"}


FALLBACK_VEHICLES: List[VehicleItem] = [
    VehicleItem(
        id="tvs_apache_rtr_160_4v",
        name="TVS Apache RTR 160 4V",
        tagline="Race-Bred Street Performance",
        category="Naked Streetfighter",
        price_range="₹1,14,390 - ₹1,44,690 (Ex-Showroom)",
        hero_image="/uploads/tvs/vehicles/tvs_apache_rtr_160_4v.png",
        engine_specs="159.7cc Single-Cylinder, 4-Valve, Oil-Cooled, Fuel Injection",
        seating_capacity="Rider + Pillion",
        fuel_or_battery="Petrol",
        range_or_mileage="~45 kmpl (claimed)",
        key_highlights=[
            "Three Riding Modes: Sport, Urban, Rain",
            "Dual-Channel ABS with Rear-Lift Protection (top variant)",
            "Race-Tuned Slipper Clutch",
            "SmartXonnect Bluetooth Connectivity",
        ],
        usp="Race-derived 4-valve engine with riding modes and slipper clutch in the 160cc street segment.",
        variants=[
            VehicleVariant(
                name="Single-Channel ABS",
                price_ex_showroom="₹1,14,390",
                engine_or_battery="159.7cc, 4V, Oil-Cooled",
                transmission="5-Speed Manual",
                key_features=["Single-Channel ABS", "LED Headlamp", "Riding Modes"],
            ),
            VehicleVariant(
                name="Dual-Channel ABS",
                price_ex_showroom="₹1,44,690",
                engine_or_battery="159.7cc, 4V, Oil-Cooled",
                transmission="5-Speed Manual",
                key_features=["Dual-Channel ABS with RLP", "USD Forks", "TFT Cluster"],
            ),
        ],
        displacement_cc="159.7 cc",
        max_power="17.55 PS @ 9250 rpm",
        max_torque="14.73 Nm @ 7500 rpm",
        braking="Front & Rear Disc, Single / Dual-Channel ABS",
        riding_modes=["Sport", "Urban", "Rain"],
        competitors=["Bajaj Pulsar N160", "Yamaha FZ-S Fi", "Honda SP160", "Hero Xtreme 160R 4V"],
    ),
    VehicleItem(
        id="tvs_iqube",
        name="TVS iQube",
        tagline="Smart Electric Commuting",
        category="Electric Scooter",
        price_range="₹94,434 - ₹1,58,834 (Ex-Showroom)",
        hero_image="/uploads/tvs/vehicles/tvs_iqube.webp",
        engine_specs="BLDC Hub Motor",
        seating_capacity="Rider + Pillion",
        fuel_or_battery="Electric",
        range_or_mileage="Up to ~145 km IDC range (battery-pack dependent)",
        key_highlights=[
            "TFT Display with Turn-by-Turn Navigation",
            "Multiple Battery Pack Options",
            "Large Under-Seat Storage",
            "Eco & Power Riding Modes",
        ],
        usp="Practical family electric scooter with connected features and multiple battery options.",
        variants=[
            VehicleVariant(
                name="iQube (Base Battery)",
                price_ex_showroom="₹94,434",
                engine_or_battery="BLDC Hub Motor / Li-ion Battery",
                transmission="Automatic (Single-Speed)",
                key_features=["Connected App", "Reverse Assist", "USB Charging"],
            ),
        ],
        riding_modes=["Eco", "Power"],
        competitors=["Ather Rizta", "Ola S1 X", "Bajaj Chetak", "Vida V2"],
    ),
    VehicleItem(
        id="hero_motocorp_splendor",
        name="Hero Splendor+",
        tagline="India's Trusted Everyday Commuter",
        category="Commuter Motorcycle",
        price_range="₹77,000 - ₹80,000 (Ex-Showroom, approx.)",
        hero_image=PLACEHOLDER_BIKE_IMAGE,
        engine_specs="97.2cc Single-Cylinder, Air-Cooled, Fuel Injection",
        seating_capacity="Rider + Pillion",
        fuel_or_battery="Petrol",
        range_or_mileage="~70 kmpl (claimed)",
        key_highlights=[
            "i3S Idle Stop-Start System",
            "Integrated Braking System (IBS)",
            "Low Maintenance & Wide Service Network",
        ],
        usp="Proven frugal commuter with class-leading mileage and low running costs.",
        variants=[
            VehicleVariant(
                name="Drum Brake",
                price_ex_showroom="₹77,000",
                engine_or_battery="97.2cc, Air-Cooled",
                transmission="4-Speed Manual",
                key_features=["i3S", "IBS", "Alloy Wheels"],
            ),
        ],
        displacement_cc="97.2 cc",
        braking="Front & Rear Drum with IBS",
        competitors=["Honda Shine 100", "Bajaj Platina 100", "TVS Radeon"],
    ),
    VehicleItem(
        id="hero_motocorp_xpulse_200_4v",
        name="Hero XPulse 200 4V",
        tagline="Go Anywhere Adventure",
        category="Adventure Tourer",
        price_range="₹1,51,000 - ₹1,65,000 (Ex-Showroom, approx.)",
        hero_image=PLACEHOLDER_BIKE_IMAGE,
        engine_specs="199.6cc Single-Cylinder, 4-Valve, Oil-Cooled, Fuel Injection",
        seating_capacity="Rider + Pillion",
        fuel_or_battery="Petrol",
        range_or_mileage="~40 kmpl (approx.)",
        key_highlights=[
            "Long-Travel Suspension for Off-Road Trails",
            "ABS Modes (Road / Off-Road / Rally)",
            "21-inch Front Wheel",
        ],
        usp="Accessible, trail-ready dual-sport motorcycle with ABS modes and long-travel suspension.",
        variants=[
            VehicleVariant(
                name="Standard",
                price_ex_showroom="₹1,51,000",
                engine_or_battery="199.6cc, 4V, Oil-Cooled",
                transmission="5-Speed Manual",
                key_features=["Single-Channel ABS", "Digital Console", "Navigation"],
            ),
        ],
        displacement_cc="199.6 cc",
        braking="Front & Rear Disc, Single-Channel ABS with modes",
        competitors=["Royal Enfield Himalayan 450", "KTM 250 Adventure", "Suzuki V-Strom SX"],
    ),
]

FALLBACK_DEALERSHIPS: List[DealershipItem] = [
    DealershipItem(
        id="tvs_mumbai_andheri",
        name="TVS Motor Authorised Dealer – Andheri West",
        address="Shop 4-6, Veera Desai Road, Andheri West, Mumbai 400053",
        city="Mumbai",
        phone="+91 22 4000 1101",
        rating=4.7,
        available_advisors=["Rahul Nair (Sales Consultant)", "Sneha Kulkarni (EV Specialist)"],
        has_test_drive_home_pickup=True,
    ),
    DealershipItem(
        id="hero_bengaluru_koramangala",
        name="Hero MotoCorp Authorised Dealer – Koramangala",
        address="No. 88, 80 Feet Road, 4th Block, Koramangala, Bengaluru 560034",
        city="Bengaluru",
        phone="+91 80 4000 2203",
        rating=4.8,
        available_advisors=["Rahul Nair (Sales Consultant)", "Kavitha Gowda (Premium Motorcycles Specialist)"],
        has_test_drive_home_pickup=True,
    ),
]


def _fmt_value(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        vals = [str(v).strip() for v in value if str(v).strip()]
        return ", ".join(vals) if vals else None
    text = str(value).strip()
    return text or None


def parse_price_floor(price_range: Optional[str]) -> Optional[int]:
    """Returns the lowest rupee amount found in a price string ('₹1,14,390 - ₹1,44,690' -> 114390)."""
    if not price_range:
        return None
    amounts = []
    for num, unit in re.findall(r"(\d[\d,]*(?:\.\d+)?)\s*(lakh|lac|l\b)?", price_range, re.IGNORECASE):
        try:
            val = float(num.replace(",", ""))
        except ValueError:
            continue
        if unit:
            val *= 100000
        if val >= 10000:
            amounts.append(int(val))
    return min(amounts) if amounts else None


class CatalogService:
    @staticmethod
    def _active_brand():
        try:
            from app.services.brand_service import BrandService
            return BrandService.get_active_brand()
        except Exception:
            return None

    @staticmethod
    def _all_brands():
        try:
            from app.services.brand_service import BrandService
            return [BrandService.get_brand(s.id) for s in BrandService.list_brands()]
        except Exception:
            return []

    @staticmethod
    def get_all_vehicles() -> List[VehicleItem]:
        brand = CatalogService._active_brand()
        if brand and brand.vehicles:
            return brand.vehicles
        return FALLBACK_VEHICLES

    @staticmethod
    def get_vehicle_by_id(vehicle_id: Optional[str]) -> Optional[VehicleItem]:
        """Looks up a vehicle in the active brand, then every loaded brand, then the fallback list."""
        if not vehicle_id:
            return None
        vid = vehicle_id.lower()
        brand = CatalogService._active_brand()
        if brand and brand.vehicles:
            for v in brand.vehicles:
                if v.id.lower() == vid:
                    return v
        for b in CatalogService._all_brands():
            for v in (b.vehicles if b else []):
                if v.id.lower() == vid:
                    return v
        for v in FALLBACK_VEHICLES:
            if v.id.lower() == vid:
                return v
        return None

    @staticmethod
    def compare_vehicles(vehicle_ids: List[str]) -> List[VehicleItem]:
        results = []
        for vid in vehicle_ids:
            item = CatalogService.get_vehicle_by_id(vid)
            if item:
                results.append(item)
        return results

    @staticmethod
    def is_electric(vehicle: VehicleItem) -> bool:
        cat = (vehicle.category or "").lower()
        return cat in ELECTRIC_CATEGORIES or "electric" in (vehicle.fuel_or_battery or "").lower()

    @staticmethod
    def is_scooter(vehicle: VehicleItem) -> bool:
        return (vehicle.category or "").lower() in SCOOTER_CATEGORIES

    @staticmethod
    def get_spec_rows(vehicle: VehicleItem) -> List[Dict[str, str]]:
        """Returns the populated two-wheeler spec rows for a vehicle (missing specs are skipped)."""
        rows = []
        for label, attr in COMPARISON_SPEC_ROWS:
            val = _fmt_value(getattr(vehicle, attr, None))
            if val:
                rows.append({"label": label, "value": val})
        return rows

    @staticmethod
    def format_spec_sheet(vehicle: VehicleItem) -> str:
        """Compact, prompt-friendly spec sheet for a motorcycle / scooter."""
        lines = [f"{vehicle.name} — {vehicle.tagline}".strip(" —")]
        for row in CatalogService.get_spec_rows(vehicle):
            lines.append(f"- {row['label']}: {row['value']}")
        if vehicle.key_highlights:
            lines.append("- Highlights: " + "; ".join(vehicle.key_highlights[:6]))
        if vehicle.usp:
            lines.append(f"- USP: {vehicle.usp}")
        return "\n".join(lines)

    @staticmethod
    def build_comparison_table(vehicle_ids: List[str]) -> Dict[str, Any]:
        """Side-by-side comparison matrix for two-wheelers using the 2W spec fields."""
        vehicles = CatalogService.compare_vehicles(vehicle_ids)
        rows = []
        for label, attr in COMPARISON_SPEC_ROWS:
            values = [_fmt_value(getattr(v, attr, None)) for v in vehicles]
            if any(values):
                rows.append({"label": label, "values": [val or "—" for val in values]})
        return {
            "vehicles": [{"id": v.id, "name": v.name} for v in vehicles],
            "rows": rows,
        }

    @staticmethod
    def get_competitors(vehicle_id: str) -> List[str]:
        v = CatalogService.get_vehicle_by_id(vehicle_id)
        return list(v.competitors or []) if v else []

    @staticmethod
    def get_dealerships() -> List[DealershipItem]:
        brand = CatalogService._active_brand()
        if brand and brand.dealerships:
            return brand.dealerships
        return FALLBACK_DEALERSHIPS

    @staticmethod
    def get_static_checklist(vehicle_id: Optional[str] = None) -> List[str]:
        from app.services.checklist_service import ChecklistService
        return ChecklistService.get_static_checklist(vehicle_id)

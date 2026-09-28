from typing import List, Optional, Dict, Any
from pydantic import BaseModel

class VehicleVariant(BaseModel):
    name: str
    price_ex_showroom: str
    engine_or_battery: str
    transmission: str
    key_features: List[str]

class VehicleItem(BaseModel):
    id: str
    name: str
    tagline: str
    category: str # Two-wheeler segment: "Commuter Motorcycle", "Premium Motorcycle", "Sports Motorcycle", "Adventure", "Cruiser", "Scooter", "Maxi Scooter", "Electric Scooter", "Electric Motorcycle", "Moped"
    price_range: str
    hero_image: str
    engine_specs: str # e.g. "159.7cc Single-Cylinder Oil-Cooled, 17.55 PS, 14.73 Nm" or "4.4 kW Hub Motor"
    seating_capacity: str # Legacy field kept for compatibility; for two-wheelers use "Rider + Pillion" / "Single Seat"
    fuel_or_battery: str # "Petrol" / "Electric (3.4 kWh)" / "Petrol + CNG"
    range_or_mileage: str # "55 kmpl" or "145 km IDC Range"
    key_highlights: List[str]
    usp: str
    variants: List[VehicleVariant]
    is_custom_source_of_truth: bool = False
    uploaded_image_url: Optional[str] = None
    # ---- Two-wheeler specifications (optional; populated by the 2W crawler) ----
    source_url: Optional[str] = None # Official model page the specs were crawled from
    displacement_cc: Optional[str] = None # "159.7 cc" (empty for EVs)
    max_power: Optional[str] = None # "17.55 PS @ 9250 rpm" / "4.4 kW"
    max_torque: Optional[str] = None # "14.73 Nm @ 7250 rpm"
    kerb_weight: Optional[str] = None # "144 kg"
    seat_height: Optional[str] = None # "800 mm"
    fuel_tank_or_battery: Optional[str] = None # "12 L" / "3.4 kWh"
    top_speed: Optional[str] = None # "114 km/h"
    braking: Optional[str] = None # "Front Disc / Rear Drum, Single-Channel ABS" / "CBS"
    riding_modes: Optional[List[str]] = None # ["Urban", "Sport", "Rain"]
    colors: Optional[List[str]] = None # ["Racing Red", "Matte Black"]
    competitors: Optional[List[str]] = None # Real segment rivals, e.g. ["Bajaj Pulsar N160", "Honda SP160"]

class VehicleComparisonRequest(BaseModel):
    vehicle_ids: List[str]

class DealershipItem(BaseModel):
    id: str
    name: str
    address: str
    city: str
    phone: str
    rating: float
    available_advisors: List[str]
    has_test_drive_home_pickup: bool

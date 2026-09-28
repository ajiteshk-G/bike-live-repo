"""
Two-wheeler loan / EMI helper.

Typical Indian two-wheeler financing: 10-25% down payment, 12-48 month tenure,
~9.5%-16% p.a. interest (bank vs NBFC, credit profile, EV subvention offers).
"""
from typing import Dict, List, Optional

from app.services.catalog_service import parse_price_floor

MIN_TENURE_MONTHS = 12
MAX_TENURE_MONTHS = 48
DEFAULT_TENURE_MONTHS = 36
MIN_DOWN_PAYMENT_PCT = 10.0
MAX_DOWN_PAYMENT_PCT = 25.0
DEFAULT_DOWN_PAYMENT_PCT = 15.0
DEFAULT_ANNUAL_RATE_PCT = 10.49
RATE_BAND_PCT = (9.5, 16.0)
TENURE_OPTIONS = [12, 18, 24, 36, 48]


def _clamp(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, val))


def monthly_emi(principal: float, annual_rate_pct: float, tenure_months: int) -> int:
    """Standard reducing-balance EMI, rounded to the nearest rupee."""
    if principal <= 0:
        return 0
    r = annual_rate_pct / 12.0 / 100.0
    if r == 0:
        return round(principal / tenure_months)
    factor = (1 + r) ** tenure_months
    return round(principal * r * factor / (factor - 1))


def estimate_two_wheeler_emi(
    price: float,
    down_payment_pct: float = DEFAULT_DOWN_PAYMENT_PCT,
    tenure_months: int = DEFAULT_TENURE_MONTHS,
    annual_rate_pct: float = DEFAULT_ANNUAL_RATE_PCT,
) -> Dict[str, object]:
    """EMI quote for a motorcycle / scooter, clamped to typical two-wheeler loan bounds."""
    dp_pct = _clamp(down_payment_pct, MIN_DOWN_PAYMENT_PCT, MAX_DOWN_PAYMENT_PCT)
    tenure = int(_clamp(tenure_months, MIN_TENURE_MONTHS, MAX_TENURE_MONTHS))
    rate = _clamp(annual_rate_pct, *RATE_BAND_PCT)
    down_payment = round(price * dp_pct / 100.0)
    principal = max(0, round(price - down_payment))
    emi = monthly_emi(principal, rate, tenure)
    return {
        "vehicle_price": round(price),
        "down_payment_pct": dp_pct,
        "down_payment": down_payment,
        "loan_amount": principal,
        "tenure_months": tenure,
        "annual_interest_rate_pct": rate,
        "monthly_emi": emi,
        "total_interest": max(0, emi * tenure - principal),
        "tenure_options": [
            {"tenure_months": t, "monthly_emi": monthly_emi(principal, rate, t)} for t in TENURE_OPTIONS
        ],
    }


def estimate_emi_for_price_range(price_range: Optional[str], **kwargs) -> Optional[Dict[str, object]]:
    """EMI quote using the lowest ex-showroom price found in a catalog price string."""
    price = parse_price_floor(price_range)
    if not price:
        return None
    return estimate_two_wheeler_emi(price, **kwargs)

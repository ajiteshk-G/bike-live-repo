import { VehicleItem } from "@/types";
import { isElectricVehicle, isScooterVehicle } from "@/lib/vehicleCategory";

/** Parse the lowest rupee amount out of a price string like "₹1,14,390 - ₹1,44,690" or "₹1.2 Lakh". */
export function parseStartingPrice(price?: string | null): number | null {
  if (!price) return null;
  const lakh = price.match(/([\d.]+)\s*(lakh|l\b)/i);
  if (lakh) return Math.round(parseFloat(lakh[1]) * 100000);
  const m = price.replace(/,/g, "").match(/(\d{4,})/);
  return m ? parseInt(m[1], 10) : null;
}

/**
 * Pick the most sensible comparison peer for a two-wheeler:
 * 1. Same exact category (e.g. "Commuter Motorcycle"), closest starting price.
 * 2. Same body type & powertrain (scooter vs motorcycle, electric vs ICE), closest price.
 * 3. Any other vehicle, closest price.
 */
export function getSmartPeerVehicle(current: VehicleItem, all: VehicleItem[]): VehicleItem {
  if (!all || all.length === 0) return current;
  const others = all.filter((v) => v.id !== current.id);
  if (others.length === 0) return current;

  const basePrice = parseStartingPrice(current.price_range);
  const byPriceProximity = (list: VehicleItem[]) =>
    [...list].sort((a, b) => {
      if (basePrice === null) return 0;
      const pa = parseStartingPrice(a.price_range);
      const pb = parseStartingPrice(b.price_range);
      const da = pa === null ? Number.MAX_SAFE_INTEGER : Math.abs(pa - basePrice);
      const db = pb === null ? Number.MAX_SAFE_INTEGER : Math.abs(pb - basePrice);
      return da - db;
    });

  const sameCategory = others.filter((v) => v.category === current.category);
  if (sameCategory.length > 0) return byPriceProximity(sameCategory)[0];

  const sameType = others.filter(
    (v) => isScooterVehicle(v) === isScooterVehicle(current) && isElectricVehicle(v) === isElectricVehicle(current)
  );
  if (sameType.length > 0) return byPriceProximity(sameType)[0];

  return byPriceProximity(others)[0];
}

function firstMatch(text: string | undefined | null, re: RegExp): string | null {
  if (!text) return null;
  const m = text.match(re);
  return m ? m[0].trim() : null;
}

function display(value: string | null | undefined): string {
  const v = (value || "").toString().trim();
  return v.length > 0 ? v : "—";
}

export interface CompareRow {
  key: string;
  label: string;
  v1: string;
  v2: string;
}

function engineCc(v: VehicleItem): string {
  if (v.displacement_cc) {
    const raw = String(v.displacement_cc).trim();
    return /cc/i.test(raw) ? raw : `${raw} cc`;
  }
  if (isElectricVehicle(v)) return "Electric motor";
  return display(firstMatch(v.engine_specs, /\d{2,4}(\.\d+)?\s?cc/i));
}

function power(v: VehicleItem): string {
  return display(v.max_power || firstMatch(v.engine_specs, /\d+(\.\d+)?\s?(PS|bhp|hp|kW)\b[^,;]*/i));
}

function torque(v: VehicleItem): string {
  return display(v.max_torque || firstMatch(v.engine_specs, /\d+(\.\d+)?\s?Nm\b[^,;]*/i));
}

function listDisplay(list?: string[] | null): string {
  return list && list.length > 0 ? list.join(", ") : "—";
}

/** Two-wheeler spec rows for the side-by-side comparison matrix. */
export function buildCompareRows(v1: VehicleItem, v2: VehicleItem): CompareRow[] {
  const row = (key: string, label: string, fn: (v: VehicleItem) => string): CompareRow => ({
    key,
    label,
    v1: fn(v1),
    v2: fn(v2)
  });

  return [
    row("engine_cc", "Engine (cc)", engineCc),
    row("power", "Max Power", power),
    row("torque", "Max Torque", torque),
    row("mileage", "Mileage / Range", (v) => display(v.range_or_mileage)),
    row("kerb_weight", "Kerb Weight", (v) => display(v.kerb_weight)),
    row("seat_height", "Seat Height", (v) => display(v.seat_height)),
    row("fuel_tank", "Fuel Tank / Battery", (v) => display(v.fuel_tank_or_battery || v.fuel_or_battery)),
    row("top_speed", "Top Speed", (v) => display(v.top_speed)),
    row("braking", "Braking / ABS", (v) => display(v.braking)),
    row("riding_modes", "Riding Modes", (v) => listDisplay(v.riding_modes)),
    row("price", "Price (Ex-Showroom)", (v) => display(v.price_range))
  ];
}

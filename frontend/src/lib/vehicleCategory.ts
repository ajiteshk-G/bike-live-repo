import { VehicleItem } from "@/types";

/**
 * Two-wheeler category helpers shared across showroom / carousel components.
 *
 * Backend categories: "Commuter Motorcycle", "Premium Commuter", "Sports Motorcycle",
 * "Naked Streetfighter", "Supersport", "Adventure Tourer", "Cruiser / Retro",
 * "Scooter", "Performance Scooter", "Electric Scooter", "Electric Motorcycle", "Moped".
 */

export type CategoryFilterId = "ALL" | "MOTORCYCLE" | "SCOOTER" | "ELECTRIC";

export const CATEGORY_FILTERS: { id: CategoryFilterId; label: string }[] = [
  { id: "ALL", label: "All" },
  { id: "MOTORCYCLE", label: "Motorcycles" },
  { id: "SCOOTER", label: "Scooters" },
  { id: "ELECTRIC", label: "Electric" }
];

type VehicleLike = Pick<VehicleItem, "category"> & Partial<Pick<VehicleItem, "fuel_or_battery">>;

export function isElectricVehicle(v: VehicleLike | null | undefined): boolean {
  if (!v) return false;
  const cat = (v.category || "").toLowerCase();
  const fuel = (v.fuel_or_battery || "").toLowerCase();
  return cat.includes("electric") || cat.includes(" ev") || fuel.includes("electric") || fuel.includes("battery") || fuel.includes("kwh");
}

export function isScooterVehicle(v: VehicleLike | null | undefined): boolean {
  if (!v) return false;
  const cat = (v.category || "").toLowerCase();
  return cat.includes("scooter") || cat.includes("moped");
}

export function isMotorcycleVehicle(v: VehicleLike | null | undefined): boolean {
  if (!v) return false;
  return !isScooterVehicle(v);
}

export function matchesCategoryFilter(v: VehicleLike, filter: CategoryFilterId | string): boolean {
  switch (filter) {
    case "MOTORCYCLE":
      return isMotorcycleVehicle(v);
    case "SCOOTER":
      return isScooterVehicle(v);
    case "ELECTRIC":
      return isElectricVehicle(v);
    case "ALL":
      return true;
    default:
      // Allow filtering by an exact backend category string as well.
      return v.category === filter;
  }
}

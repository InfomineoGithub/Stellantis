import type { Source } from "@/core/sources/types";

export type VehicleClass = "compact" | "midsize" | "full_size" | "luxury" | "economy";
export type BodyType     = "sedan" | "suv" | "hatchback" | "coupe" | "convertible" | "pickup" | "van";
export type Transmission = "manual" | "automatic" | "cvt";
export type FuelType     = "gasoline" | "diesel" | "electric" | "hybrid" | "phev" | "bev";

export interface Vehicle {
  id:            string;
  manufacturer:  string;
  model_name:    string;
  vehicle_class: VehicleClass;
  year:          number;
  body_type:     BodyType;
  transmission:  Transmission;
  fuel_type:     FuelType;
  thumbnail_url: string | null;
  notes:         string | null;
  created_at:    string;
  updated_at:    string;
  sources?:      Source[];
}

export interface CreateVehicleInput {
  manufacturer:  string;
  model_name:    string;
  vehicle_class: VehicleClass;
  year:          number;
  body_type:     BodyType;
  transmission:  Transmission;
  fuel_type:     FuelType;
  thumbnail_url?: string;
  notes?:        string;
}

export type UpdateVehicleInput = Partial<CreateVehicleInput>;

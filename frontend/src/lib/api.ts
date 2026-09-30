const BASE = "/api";

async function request<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) {
    throw new Error(`API ${path} failed: ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export interface Camera {
  code: string;
  name: string;
  lat: number;
  lng: number;
  road: string;
  zone: string;
  direction_deg: number;
  status: string;
}

export interface CitySummary {
  city_name: string;
  zones: number;
  roads: number;
  intersections: number;
  cameras: number;
  topology_edges: number;
}

export const api = {
  health: () => request<{ status: string }>("/health"),
  healthDetailed: () => request<Record<string, unknown>>("/health/detailed"),
  cameras: () => request<{ count: number; cameras: Camera[] }>("/cameras"),
  citySummary: () => request<CitySummary>("/city/summary"),
  systemMetrics: () => request<Record<string, unknown>>("/system/metrics"),
};

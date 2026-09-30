import { useState } from "react";

type JourneyResponse = {
  vehicle?: {
    id: string;
    plate_best?: string;
    plate_conf?: number;
    vehicle_type?: string;
    color?: string;
  };
  observations?: Array<{
    id: string;
    camera_code?: string;
    ts?: string;
    plate_text?: string;
    vehicle_type?: string;
    color?: string;
  }>;
  transitions?: Array<{
    id: string;
    from_camera_code?: string;
    to_camera_code?: string;
    travel_time_s?: number;
    est_speed_kmh?: number;
    confidence?: number;
    status?: string;
  }>;
  journey?: {
    start_ts?: string;
    end_ts?: string;
    distance_est_m?: number;
    duration_s?: number;
    avg_speed_kmh?: number;
    stop_count?: number;
    camera_count?: number;
  };
};

export default function VehicleJourney() {
  const [plate, setPlate] = useState("");
  const [data, setData] = useState<JourneyResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function searchVehicle(e: React.FormEvent) {
    e.preventDefault();

    if (!plate.trim()) return;

    setLoading(true);
    setError("");
    setData(null);

    try {
      const searchRes = await fetch(
        `/api/vehicles/search?plate=${encodeURIComponent(plate.trim())}`
      );

      if (!searchRes.ok) {
        throw new Error("Vehicle search failed");
      }

      const search = await searchRes.json();

      if (!search.items?.length) {
        throw new Error("Vehicle not found");
      }

      // SIH demo vehicle: the vehicle with the full 8-observation journey.
      const demoVehicleId =
        "d3f7e0b6-8fd4-4586-9ef2-4d151c075d11";

      const vehicle =
        search.items.find(
          (item: { id: string }) => item.id === demoVehicleId
        ) ?? search.items[0];

      const journeyRes = await fetch(
        `/api/vehicles/${vehicle.id}/journey`
      );

      if (!journeyRes.ok) {
        throw new Error("Journey could not be loaded");
      }

      const journey = await journeyRes.json();

      setData({
        ...journey,
        vehicle,
      });
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Something went wrong"
      );
    } finally {
      setLoading(false);
    }
  }

  const journey = data?.journey;
  const observations = data?.observations ?? [];
  const transitions = data?.transitions ?? [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="text-xs uppercase tracking-[0.2em] text-cyan-400">
          Part 4 · Trajectory Intelligence
        </div>

        <h1 className="mt-2 text-3xl font-bold text-white">
          Vehicle Journey
        </h1>

        <p className="mt-2 text-sm text-slate-400">
          Search a vehicle and inspect its observed cross-camera journey.
        </p>
      </div>

      {/* Search */}
      <form
        onSubmit={searchVehicle}
        className="flex gap-3 rounded-xl border border-slate-800 bg-slate-900/70 p-4"
      >
        <input
          value={plate}
          onChange={(e) => setPlate(e.target.value)}
          placeholder="Enter plate e.g. BDB4668"
          className="flex-1 rounded-lg border border-slate-700 bg-slate-950 px-4 py-3 text-white outline-none focus:border-cyan-500"
        />

        <button
          type="submit"
          disabled={loading}
          className="rounded-lg bg-cyan-500 px-6 py-3 font-semibold text-slate-950 disabled:opacity-50"
        >
          {loading ? "Searching..." : "Search"}
        </button>
      </form>

      {/* Error */}
      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-300">
          {error}
        </div>
      )}

      {/* Demo shortcut */}
      {!data && !loading && (
        <div className="rounded-xl border border-cyan-500/20 bg-cyan-500/5 p-5">
          <div className="text-sm font-semibold text-cyan-300">
            Demo vehicle available
          </div>

          <div className="mt-2 text-sm text-slate-400">
            Try:
          </div>

          <button
            type="button"
            onClick={() => setPlate("BDB4668")}
            className="mt-2 rounded-lg border border-cyan-500/30 px-4 py-2 text-sm text-cyan-300 hover:bg-cyan-500/10"
          >
            BDB4668
          </button>
        </div>
      )}

      {data && (
        <>
          {/* Vehicle identity */}
          <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
            <Metric
              label="Vehicle"
              value={data.vehicle?.plate_best ?? plate}
            />

            <Metric
              label="Type"
              value={data.vehicle?.vehicle_type ?? "—"}
            />

            <Metric
              label="Color"
              value={data.vehicle?.color ?? "—"}
            />

            <Metric
              label="Confidence"
              value={
                data.vehicle?.plate_conf
                  ? `${(data.vehicle.plate_conf * 100).toFixed(0)}%`
                  : "—"
              }
            />
          </div>

          {/* Journey metrics */}
          <div className="grid grid-cols-2 gap-4 md:grid-cols-5">
            <Metric
              label="Cameras"
              value={String(
                journey?.camera_count ?? observations.length
              )}
            />

            <Metric
              label="Distance"
              value={
                journey?.distance_est_m != null
                  ? `${Math.round(journey.distance_est_m)} m`
                  : "—"
              }
            />

            <Metric
              label="Duration"
              value={
                journey?.duration_s != null
                  ? `${Math.round(journey.duration_s)} s`
                  : "—"
              }
            />

            <Metric
              label="Avg speed"
              value={
                journey?.avg_speed_kmh != null
                  ? `${journey.avg_speed_kmh.toFixed(1)} km/h`
                  : "—"
              }
            />

            <Metric
              label="Stops"
              value={String(journey?.stop_count ?? 0)}
            />
          </div>

          {/* Timeline */}
          <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
            <div className="mb-5 flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-white">
                  Camera Timeline
                </h2>

                <p className="text-xs text-slate-500">
                  Observed camera detections
                </p>
              </div>

              <span className="rounded-full bg-cyan-500/10 px-3 py-1 text-xs text-cyan-300">
                {observations.length} observations
              </span>
            </div>

            {observations.length === 0 ? (
              <div className="py-8 text-center text-sm text-slate-500">
                No observations available.
              </div>
            ) : (
              <div className="space-y-3">
                {observations.map((obs, index) => (
                  <div
                    key={obs.id}
                    className="flex items-center gap-4 rounded-lg border border-slate-800 bg-slate-950/60 p-4"
                  >
                    <div className="flex h-9 w-9 items-center justify-center rounded-full bg-cyan-500/10 text-sm font-bold text-cyan-300">
                      {index + 1}
                    </div>

                    <div className="flex-1">
                      <div className="font-semibold text-white">
                        {obs.camera_code ?? `Camera ${index + 1}`}
                      </div>

                      <div className="mt-1 text-xs text-slate-500">
                        {obs.ts
                          ? new Date(obs.ts).toLocaleString()
                          : "Timestamp unavailable"}
                      </div>
                    </div>

                    <div className="text-right text-xs text-slate-400">
                      <div>{obs.vehicle_type ?? "vehicle"}</div>
                      <div>{obs.color ?? "unknown color"}</div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Transitions */}
          <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
            <h2 className="text-lg font-semibold text-white">
              Cross-Camera Transitions
            </h2>

            <p className="mt-1 text-xs text-slate-500">
              Fusion decisions produced by the trajectory engine.
            </p>

            <div className="mt-4 space-y-3">
              {transitions.length === 0 ? (
                <div className="py-6 text-sm text-slate-500">
                  No transitions available.
                </div>
              ) : (
                transitions.map((transition) => (
                  <div
                    key={transition.id}
                    className="flex flex-wrap items-center gap-4 rounded-lg border border-slate-800 bg-slate-950/60 p-4"
                  >
                    <div className="font-semibold text-white">
                      {transition.from_camera_code ?? "Camera"} →{" "}
                      {transition.to_camera_code ?? "Camera"}
                    </div>

                    <span className="text-xs text-slate-400">
                      {transition.travel_time_s != null
                        ? `${transition.travel_time_s.toFixed(1)}s`
                        : "time —"}
                    </span>

                    <span className="text-xs text-slate-400">
                      {transition.est_speed_kmh != null
                        ? `${transition.est_speed_kmh.toFixed(1)} km/h`
                        : "speed —"}
                    </span>

                    <span className="ml-auto rounded-full bg-emerald-500/10 px-3 py-1 text-xs text-emerald-300">
                      {transition.status ?? "linked"}
                    </span>

                    {transition.confidence != null && (
                      <span className="text-xs text-cyan-300">
                        {(transition.confidence * 100).toFixed(0)}%
                        confidence
                      </span>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function Metric({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-4">
      <div className="text-xs uppercase tracking-wider text-slate-500">
        {label}
      </div>

      <div className="mt-2 text-xl font-bold text-white">
        {value}
      </div>
    </div>
  );
}
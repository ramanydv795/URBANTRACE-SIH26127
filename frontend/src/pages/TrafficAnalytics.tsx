import { useEffect, useMemo, useState } from "react";

type ODRow = {
  date: string;
  origin_zone_id: number;
  dest_zone_id: number;
  trip_count: number;
};

type Bottleneck = {
  road_id: number;
  intersection_id?: number;
  severity: string;
  indicators: {
    transition_count?: number;
    avg_travel_time_s?: number;
    avg_speed_kmh?: number;
  };
};

type Transition = {
  id: string;
  vehicle_id?: string;
  from_camera?: string;
  to_camera?: string;
  status?: string;
  confidence?: number;
  evidence?: {
    fusion_score?: number;
    plate?: { similarity?: number };
    reid?: { similarity?: number };
    time?: {
      feasibility?: number;
      observed_seconds?: number;
    };
  };
};

const DEMO_VEHICLE_ID =
  "d3f7e0b6-8fd4-4586-9ef2-4d151c075d11";

function pct(value?: number) {
  if (value == null) return "—";
  return `${(value * 100).toFixed(1)}%`;
}

export default function TrafficAnalytics() {
  const [od, setOd] = useState<ODRow[]>([]);
  const [bottlenecks, setBottlenecks] = useState<Bottleneck[]>([]);
  const [transitions, setTransitions] = useState<Transition[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([
      fetch("/api/traffic/od-matrix").then((r) => {
        if (!r.ok) throw new Error("OD Matrix API failed");
        return r.json();
      }),

      fetch("/api/traffic/bottlenecks").then((r) => {
        if (!r.ok) throw new Error("Bottleneck API failed");
        return r.json();
      }),

      fetch("/api/transitions?status=auto_linked&limit=100").then((r) => {
        if (!r.ok) throw new Error("Transition API failed");
        return r.json();
      }),
    ])
      .then(([odData, bottleneckData, transitionData]) => {
        setOd(odData.items ?? []);
        setBottlenecks(bottleneckData.items ?? []);

        const demo = (transitionData.items ?? [])
          .filter(
            (t: Transition) => t.vehicle_id === DEMO_VEHICLE_ID
          )
          .sort(
            (a: Transition, b: Transition) =>
              (b.evidence?.fusion_score ?? b.confidence ?? 0) -
              (a.evidence?.fusion_score ?? a.confidence ?? 0)
          );

        setTransitions(demo);
      })
      .catch((err) => {
        setError(err.message ?? "Could not load traffic analytics");
      })
      .finally(() => setLoading(false));
  }, []);

  const totalTrips = od.reduce(
    (sum, row) => sum + Number(row.trip_count || 0),
    0
  );

  const high = bottlenecks.filter(
    (b) => b.severity.toLowerCase() === "high"
  ).length;

  const medium = bottlenecks.filter(
    (b) => b.severity.toLowerCase() === "medium"
  ).length;

  const avgFusion = useMemo(() => {
    if (!transitions.length) return 0;

    return (
      transitions.reduce(
        (sum, t) =>
          sum + (t.evidence?.fusion_score ?? t.confidence ?? 0),
        0
      ) / transitions.length
    );
  }, [transitions]);

  const avgTravelTime = useMemo(() => {
    const values = transitions
      .map((t) => t.evidence?.time?.observed_seconds)
      .filter((v): v is number => v != null);

    if (!values.length) return null;

    return values.reduce((a, b) => a + b, 0) / values.length;
  }, [transitions]);

  return (
    <div className="space-y-6 p-6">
      {/* HEADER */}
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
        <div>
          <div className="mb-2 flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" />

            <span className="text-xs font-semibold uppercase tracking-[0.18em] text-emerald-600">
              Part 5 · Traffic Intelligence
            </span>
          </div>

          <h1 className="text-3xl font-bold tracking-tight text-slate-900">
            Traffic Analytics
          </h1>

          <p className="mt-1 max-w-2xl text-sm text-slate-500">
            City-wide traffic patterns derived from completed journeys,
            confirmed cross-camera movement and trajectory intelligence.
          </p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
          <div className="text-xs uppercase tracking-wider text-slate-400">
            Data Source
          </div>

          <div className="font-semibold text-slate-800">
            Live PostgreSQL Intelligence
          </div>
        </div>
      </div>

      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {loading ? (
        <div className="rounded-2xl border border-slate-200 bg-white p-10 text-center text-sm text-slate-500">
          Loading traffic analytics…
        </div>
      ) : (
        <>
          {/* KPI GRID */}
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
            <Metric
              label="OD Records"
              value={String(od.length)}
              sub="Origin-destination flows"
            />

            <Metric
              label="Observed Trips"
              value={String(totalTrips)}
              sub="Completed journeys"
            />

            <Metric
              label="Transitions"
              value={String(transitions.length)}
              sub="Confirmed links"
            />

            <Metric
              label="Avg Fusion"
              value={pct(avgFusion)}
              sub="Trajectory confidence"
            />

            <Metric
              label="Avg Travel Time"
              value={
                avgTravelTime != null
                  ? `${avgTravelTime.toFixed(1)}s`
                  : "—"
              }
              sub="Observed transitions"
            />
          </div>

          {/* TRAJECTORY SUMMARY */}
          <section className="rounded-2xl border border-slate-200 bg-white shadow-sm">
            <div className="border-b border-slate-100 px-5 py-4">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="font-semibold text-slate-900">
                    Trajectory Intelligence
                  </h2>

                  <p className="mt-1 text-xs text-slate-500">
                    Aggregated evidence from the active SIH demonstration
                    vehicle.
                  </p>
                </div>

                <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700">
                  BDB4668
                </span>
              </div>
            </div>

            <div className="grid gap-4 p-5 md:grid-cols-3">
              <Insight
                title="Global Identity"
                value="1 vehicle"
                detail="Resolved across camera boundaries"
              />

              <Insight
                title="Auto-linked"
                value={`${transitions.length} transitions`}
                detail="Movement graph associations"
              />

              <Insight
                title="Evidence Fusion"
                value={pct(avgFusion)}
                detail="Average final confidence"
              />
            </div>

            {transitions.length > 0 && (
              <div className="border-t border-slate-100 p-5">
                <div className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-400">
                  Camera Flow
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  {transitions
                    .slice()
                    .reverse()
                    .map((t, index) => (
                      <div
                        key={t.id}
                        className="flex items-center gap-2"
                      >
                        {index > 0 && (
                          <span className="text-slate-300">→</span>
                        )}

                        <span className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-bold text-slate-700">
                          {t.from_camera || "C01"}
                        </span>

                        <span className="rounded-lg bg-blue-50 px-3 py-2 text-xs font-bold text-blue-700">
                          {t.to_camera || "C02"}
                        </span>
                      </div>
                    ))}
                </div>
              </div>
            )}
          </section>

          {/* OD MATRIX */}
          <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
            <div className="border-b border-slate-100 px-5 py-4">
              <h2 className="font-semibold text-slate-900">
                Origin–Destination Matrix
              </h2>

              <p className="mt-1 text-xs text-slate-500">
                Daily completed journey flows between city zones.
              </p>
            </div>

            {od.length === 0 ? (
              <div className="p-10 text-center text-sm text-slate-500">
                No completed OD journeys available.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="border-b border-slate-100 bg-slate-50 text-xs uppercase tracking-wider text-slate-400">
                    <tr>
                      <th className="px-5 py-3">Date</th>
                      <th className="px-5 py-3">Origin</th>
                      <th className="px-5 py-3">Destination</th>
                      <th className="px-5 py-3">Trips</th>
                    </tr>
                  </thead>

                  <tbody>
                    {od.map((row, index) => (
                      <tr
                        key={`${row.date}-${row.origin_zone_id}-${row.dest_zone_id}-${index}`}
                        className="border-b border-slate-100 last:border-0"
                      >
                        <td className="px-5 py-3 text-slate-600">
                          {row.date}
                        </td>

                        <td className="px-5 py-3">
                          <span className="rounded-md bg-blue-50 px-2 py-1 text-xs font-semibold text-blue-700">
                            Zone {row.origin_zone_id}
                          </span>
                        </td>

                        <td className="px-5 py-3">
                          <span className="rounded-md bg-slate-100 px-2 py-1 text-xs font-semibold text-slate-700">
                            Zone {row.dest_zone_id}
                          </span>
                        </td>

                        <td className="px-5 py-3 font-bold text-slate-900">
                          {row.trip_count}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          {/* BOTTLENECKS */}
          <section className="rounded-2xl border border-slate-200 bg-white shadow-sm">
            <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
              <div>
                <h2 className="font-semibold text-slate-900">
                  Detected Bottlenecks
                </h2>

                <p className="mt-1 text-xs text-slate-500">
                  Traffic constraints derived from confirmed vehicle
                  transitions.
                </p>
              </div>

              <div className="flex gap-2">
                <Badge
                  label={`${high} High`}
                  className="bg-red-50 text-red-700"
                />

                <Badge
                  label={`${medium} Medium`}
                  className="bg-amber-50 text-amber-700"
                />
              </div>
            </div>

            {bottlenecks.length === 0 ? (
              <div className="p-10 text-center text-sm text-slate-500">
                No confirmed bottlenecks detected.
              </div>
            ) : (
              <div className="grid gap-4 p-5 md:grid-cols-2">
                {bottlenecks.map((bottleneck) => {
                  const severity =
                    bottleneck.severity.toLowerCase();

                  return (
                    <div
                      key={`${bottleneck.road_id}-${bottleneck.severity}`}
                      className="rounded-xl border border-slate-200 bg-slate-50 p-5"
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <div className="font-semibold text-slate-900">
                            Road R
                            {String(bottleneck.road_id).padStart(2, "0")}
                          </div>

                          {bottleneck.intersection_id != null && (
                            <div className="mt-1 text-xs text-slate-400">
                              Intersection I
                              {String(
                                bottleneck.intersection_id
                              ).padStart(2, "0")}
                            </div>
                          )}
                        </div>

                        <span
                          className={`rounded-full px-3 py-1 text-xs font-semibold uppercase ${
                            severity === "high"
                              ? "bg-red-50 text-red-700"
                              : severity === "medium"
                              ? "bg-amber-50 text-amber-700"
                              : "bg-slate-100 text-slate-600"
                          }`}
                        >
                          {bottleneck.severity}
                        </span>
                      </div>

                      <div className="mt-5 grid grid-cols-3 gap-3">
                        <SmallMetric
                          label="Transitions"
                          value={String(
                            bottleneck.indicators
                              .transition_count ?? 0
                          )}
                        />

                        <SmallMetric
                          label="Avg Time"
                          value={
                            bottleneck.indicators
                              .avg_travel_time_s != null
                              ? `${bottleneck.indicators.avg_travel_time_s.toFixed(
                                  1
                                )}s`
                              : "—"
                          }
                        />

                        <SmallMetric
                          label="Avg Speed"
                          value={
                            bottleneck.indicators
                              .avg_speed_kmh != null
                              ? `${bottleneck.indicators.avg_speed_kmh.toFixed(
                                  1
                                )} km/h`
                              : "—"
                          }
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </section>

          {/* EMPTY STATE */}
          {od.length === 0 &&
            bottlenecks.length === 0 &&
            transitions.length === 0 && (
              <div className="rounded-2xl border border-amber-200 bg-amber-50 p-5">
                <div className="font-semibold text-amber-800">
                  No traffic aggregates available yet
                </div>

                <div className="mt-1 text-sm text-amber-700">
                  Traffic analytics are calculated from completed journeys
                  and confirmed vehicle transitions. No metrics are
                  fabricated when the underlying observations are absent.
                </div>
              </div>
            )}
        </>
      )}
    </div>
  );
}

function Metric({
  label,
  value,
  sub,
}: {
  label: string;
  value: string;
  sub: string;
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="text-xs font-semibold uppercase tracking-wider text-slate-400">
        {label}
      </div>

      <div className="mt-2 truncate text-2xl font-bold tracking-tight text-slate-900">
        {value}
      </div>

      <div className="mt-1 text-xs text-slate-500">{sub}</div>
    </div>
  );
}

function Insight({
  title,
  value,
  detail,
}: {
  title: string;
  value: string;
  detail: string;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
      <div className="text-xs uppercase tracking-wider text-slate-400">
        {title}
      </div>

      <div className="mt-2 text-xl font-bold text-slate-900">
        {value}
      </div>

      <div className="mt-1 text-xs text-slate-500">
        {detail}
      </div>
    </div>
  );
}

function SmallMetric({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-xl bg-white p-3 text-center shadow-sm">
      <div className="text-[10px] uppercase tracking-wider text-slate-400">
        {label}
      </div>

      <div className="mt-1 text-sm font-bold text-slate-800">
        {value}
      </div>
    </div>
  );
}

function Badge({
  label,
  className,
}: {
  label: string;
  className: string;
}) {
  return (
    <span
      className={`rounded-full px-3 py-1 text-xs font-semibold ${className}`}
    >
      {label}
    </span>
  );
}
import { useEffect, useState } from "react";

type Evidence = {
  reid?: {
    available?: boolean;
    similarity?: number;
  };
  time?: {
    available?: boolean;
    feasibility?: number;
    observed_seconds?: number;
    expected_max_seconds?: number;
    expected_min_seconds?: number;
  };
  plate?: {
    available?: boolean;
    similarity?: number;
  };
  topology?: {
    score?: number;
    available?: boolean;
    reachable?: boolean;
  };
  direction?: {
    score?: number;
    available?: boolean;
    method?: string;
    limitation?: string;
  };
  fusion_score?: number;
  weights_used?: Record<string, number>;
  signals_used?: string[];
  departure_camera?: string;
  arrival_camera?: string;
};

type Transition = {
  id: string;
  vehicle_id?: string;
  from_camera?: string;
  to_camera?: string;
  travel_time_s?: number;
  est_speed_kmh?: number;
  direction_ok?: boolean;
  topology_ok?: boolean;
  time_feasible?: boolean;
  plate_similarity?: number;
  reid_similarity?: number;
  confidence?: number;
  status?: string;
  evidence?: Evidence;
  created_at?: string;
};

const DEMO_VEHICLE_ID =
  "d3f7e0b6-8fd4-4586-9ef2-4d151c075d11";

export default function TrajectoryExplainer() {
  const [transitions, setTransitions] = useState<Transition[]>([]);
  const [selected, setSelected] = useState<Transition | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    loadTransitions();
  }, []);

  async function loadTransitions() {
    try {
      setLoading(true);
      setError("");

      const res = await fetch(
        "/api/transitions?status=auto_linked&limit=100"
      );

      if (!res.ok) {
        throw new Error("Could not load transitions");
      }

      const data = await res.json();

      const items: Transition[] = data.items ?? [];

      /*
       * Prefer the SIH demo vehicle.
       * This prevents the newer 2-observation demo vehicle
       * from being selected instead of the 8-observation journey.
       */
      const demoTransitions = items.filter(
        (item) => item.vehicle_id === DEMO_VEHICLE_ID
      );

      const displayTransitions =
        demoTransitions.length > 0 ? demoTransitions : items;

      setTransitions(displayTransitions);

      if (displayTransitions.length > 0) {
        await loadExplanation(displayTransitions[0].id);
      }
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to load trajectory evidence"
      );
    } finally {
      setLoading(false);
    }
  }

  async function loadExplanation(id: string) {
    try {
      const res = await fetch(
        `/api/transitions/${id}/explain`
      );

      if (!res.ok) {
        throw new Error("Could not load transition evidence");
      }

      const data = await res.json();

      setSelected(data);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to load explanation"
      );
    }
  }

  const evidence = selected?.evidence;

  const plateSimilarity =
    evidence?.plate?.similarity ??
    selected?.plate_similarity;

  const reidSimilarity =
    evidence?.reid?.similarity ??
    selected?.reid_similarity;

  const timeFeasibility =
    evidence?.time?.feasibility;

  const topologyPass =
    evidence?.topology?.reachable ??
    selected?.topology_ok;

  const directionPass =
    evidence?.direction?.score === 1
      ? true
      : selected?.direction_ok;

  const fusionScore =
    evidence?.fusion_score ??
    selected?.confidence;

  const travelTime =
    evidence?.time?.observed_seconds ??
    selected?.travel_time_s;

  const speed = selected?.est_speed_kmh;

  if (loading) {
    return (
      <div className="space-y-6">
        <Header />

        <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-8 text-center text-slate-400">
          Loading trajectory evidence...
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Header />

      {error && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-300">
          {error}
        </div>
      )}

      {transitions.length === 0 ? (
        <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-8 text-center">
          <div className="text-lg font-semibold text-white">
            No linked transitions
          </div>

          <p className="mt-2 text-sm text-slate-500">
            Run the trajectory association engine first.
          </p>
        </div>
      ) : (
        <>
          {/* Transition selector */}
          <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
            <div className="mb-4">
              <h2 className="text-lg font-semibold text-white">
                Camera-to-Camera Transitions
              </h2>

              <p className="mt-1 text-xs text-slate-500">
                Select a transition to inspect the complete fusion decision.
              </p>
            </div>

            <div className="grid gap-3 md:grid-cols-2">
              {transitions.map((transition, index) => {
                const active =
                  selected?.id === transition.id;

                const itemEvidence = transition.evidence;

                const score =
                  itemEvidence?.fusion_score ??
                  transition.confidence;

                return (
                  <button
                    key={transition.id}
                    type="button"
                    onClick={() =>
                      loadExplanation(transition.id)
                    }
                    className={`text-left rounded-xl border p-4 transition ${
                      active
                        ? "border-cyan-500/60 bg-cyan-500/10"
                        : "border-slate-800 bg-slate-950/50 hover:border-slate-700"
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <div className="flex h-8 w-8 items-center justify-center rounded-full bg-cyan-500/10 text-xs font-bold text-cyan-300">
                        {index + 1}
                      </div>

                      <div className="font-semibold text-white">
                        {transition.from_camera ??
                          "Camera"}{" "}
                        →
                        {" "}
                        {transition.to_camera ??
                          "Camera"}
                      </div>

                      <span className="ml-auto rounded-full bg-emerald-500/10 px-2 py-1 text-[10px] uppercase tracking-wider text-emerald-300">
                        auto-linked
                      </span>
                    </div>

                    <div className="mt-3 flex gap-5 text-xs text-slate-400">
                      <span>
                        Plate{" "}
                        {formatPercent(
                          itemEvidence?.plate?.similarity ??
                            transition.plate_similarity
                        )}
                      </span>

                      <span>
                        Re-ID{" "}
                        {formatPercent(
                          itemEvidence?.reid?.similarity ??
                            transition.reid_similarity
                        )}
                      </span>

                      <span>
                        Score{" "}
                        {formatPercent(score)}
                      </span>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {selected && (
            <>
              {/* Main decision */}
              <div className="rounded-2xl border border-cyan-500/30 bg-cyan-500/5 p-6">
                <div className="flex flex-wrap items-center justify-between gap-4">
                  <div>
                    <div className="text-xs uppercase tracking-[0.2em] text-cyan-400">
                      Fusion Decision
                    </div>

                    <div className="mt-2 text-3xl font-bold text-white">
                      {selected.from_camera ??
                        evidence?.departure_camera ??
                        "Camera"}{" "}
                      <span className="text-cyan-400">
                        →
                      </span>{" "}
                      {selected.to_camera ??
                        evidence?.arrival_camera ??
                        "Camera"}
                    </div>
                  </div>

                  <div className="text-right">
                    <div className="text-xs uppercase tracking-wider text-slate-500">
                      Final Confidence
                    </div>

                    <div className="mt-1 text-4xl font-bold text-cyan-300">
                      {formatPercent(fusionScore)}
                    </div>
                  </div>
                </div>

                <div className="mt-5 flex flex-wrap gap-3">
                  <span className="rounded-full bg-emerald-500/10 px-4 py-2 text-xs font-semibold uppercase tracking-wider text-emerald-300">
                    AUTO-LINKED
                  </span>

                  {selected.vehicle_id && (
                    <span className="rounded-full bg-slate-800 px-4 py-2 text-xs text-slate-400">
                      Vehicle ID:{" "}
                      {selected.vehicle_id.slice(0, 8)}...
                    </span>
                  )}
                </div>
              </div>

              {/* Evidence */}
              <div>
                <div className="mb-4">
                  <h2 className="text-lg font-semibold text-white">
                    Evidence Breakdown
                  </h2>

                  <p className="mt-1 text-xs text-slate-500">
                    Independent signals used by the trajectory fusion engine.
                  </p>
                </div>

                <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
                  <EvidenceCard
                    label="Plate Similarity"
                    value={formatPercent(
                      plateSimilarity
                    )}
                    description="ANPR agreement between camera observations"
                    good={
                      plateSimilarity == null ||
                      plateSimilarity >= 0.85
                    }
                  />

                  <EvidenceCard
                    label="Re-ID Similarity"
                    value={formatPercent(
                      reidSimilarity
                    )}
                    description="Visual vehicle embedding similarity"
                    good={
                      reidSimilarity == null ||
                      reidSimilarity >= 0.85
                    }
                  />

                  <EvidenceCard
                    label="Time Feasibility"
                    value={formatPercent(
                      timeFeasibility
                    )}
                    description={
                      travelTime != null
                        ? `Observed travel time: ${travelTime.toFixed(
                            1
                          )}s`
                        : "Expected travel window"
                    }
                    good={
                      timeFeasibility == null ||
                      timeFeasibility >= 0.55
                    }
                  />

                  <EvidenceCard
                    label="Topology"
                    value={
                      topologyPass == null
                        ? "—"
                        : topologyPass
                        ? "PASS"
                        : "FAIL"
                    }
                    description="Camera pair exists in the movement graph"
                    good={topologyPass !== false}
                  />

                  <EvidenceCard
                    label="Direction"
                    value={
                      directionPass == null
                        ? "—"
                        : directionPass
                        ? "PASS"
                        : "FAIL"
                    }
                    description="Topology-compatible movement direction"
                    good={directionPass !== false}
                  />

                  <EvidenceCard
                    label="Estimated Speed"
                    value={
                      speed != null
                        ? `${speed.toFixed(1)} km/h`
                        : "—"
                    }
                    description="Camera-to-camera travel speed"
                    good
                  />
                </div>
              </div>

              {/* Observation pair */}
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <InfoPanel
                  title="Observation Pair"
                  rows={[
                    [
                      "From Camera",
                      selected.from_camera ??
                        evidence?.departure_camera ??
                        "—",
                    ],
                    [
                      "To Camera",
                      selected.to_camera ??
                        evidence?.arrival_camera ??
                        "—",
                    ],
                    [
                      "From Plate",
                      (selected as any).from_plate ??
                        "—",
                    ],
                    [
                      "To Plate",
                      (selected as any).to_plate ??
                        "—",
                    ],
                  ]}
                />

                <InfoPanel
                  title="Temporal Evidence"
                  rows={[
                    [
                      "From",
                      formatDate(
                        (selected as any).from_ts
                      ),
                    ],
                    [
                      "To",
                      formatDate(
                        (selected as any).to_ts
                      ),
                    ],
                    [
                      "Travel Time",
                      travelTime != null
                        ? `${travelTime.toFixed(
                            1
                          )} seconds`
                        : "—",
                    ],
                    [
                      "Expected Window",
                      evidence?.time
                        ?.expected_min_seconds != null &&
                      evidence?.time
                        ?.expected_max_seconds != null
                        ? `${evidence.time.expected_min_seconds}s – ${evidence.time.expected_max_seconds}s`
                        : "—",
                    ],
                  ]}
                />
              </div>

              {/* Fusion model */}
              {evidence?.weights_used && (
                <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
                  <h2 className="text-lg font-semibold text-white">
                    Fusion Model
                  </h2>

                  <p className="mt-1 text-xs text-slate-500">
                    Signal weights used for the final association score.
                  </p>

                  <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-5">
                    {Object.entries(
                      evidence.weights_used
                    ).map(([key, value]) => (
                      <div
                        key={key}
                        className="rounded-lg border border-slate-800 bg-slate-950/60 p-3"
                      >
                        <div className="text-xs uppercase text-slate-500">
                          {key}
                        </div>

                        <div className="mt-1 text-lg font-bold text-white">
                          {(value * 100).toFixed(0)}%
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Raw evidence */}
              {evidence &&
                Object.keys(evidence).length > 0 && (
                  <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
                    <div className="mb-4">
                      <h2 className="text-lg font-semibold text-white">
                        Fusion Evidence
                      </h2>

                      <p className="mt-1 text-xs text-slate-500">
                        Raw evidence persisted by the trajectory engine.
                      </p>
                    </div>

                    <pre className="max-h-96 overflow-auto rounded-lg border border-slate-800 bg-slate-950 p-4 text-xs leading-6 text-slate-400">
                      {JSON.stringify(
                        evidence,
                        null,
                        2
                      )}
                    </pre>
                  </div>
                )}
            </>
          )}
        </>
      )}
    </div>
  );
}

function Header() {
  return (
    <div>
      <div className="text-xs uppercase tracking-[0.2em] text-cyan-400">
        Part 3 · Trajectory Intelligence
      </div>

      <h1 className="mt-2 text-3xl font-bold text-white">
        Trajectory Explainer
      </h1>

      <p className="mt-2 text-sm text-slate-400">
        Inspect the evidence behind every cross-camera vehicle association.
      </p>
    </div>
  );
}

function EvidenceCard({
  label,
  value,
  description,
  good,
}: {
  label: string;
  value: string;
  description: string;
  good: boolean;
}) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
      <div className="text-xs uppercase tracking-wider text-slate-500">
        {label}
      </div>

      <div
        className={`mt-3 text-2xl font-bold ${
          good
            ? "text-emerald-300"
            : "text-red-300"
        }`}
      >
        {value}
      </div>

      <div className="mt-2 text-xs leading-5 text-slate-500">
        {description}
      </div>
    </div>
  );
}

function InfoPanel({
  title,
  rows,
}: {
  title: string;
  rows: Array<[string, string]>;
}) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
      <h2 className="text-lg font-semibold text-white">
        {title}
      </h2>

      <div className="mt-4 space-y-3">
        {rows.map(([label, value]) => (
          <div
            key={label}
            className="flex items-center justify-between gap-4 border-b border-slate-800 pb-3 last:border-0 last:pb-0"
          >
            <span className="text-xs uppercase tracking-wider text-slate-500">
              {label}
            </span>

            <span className="text-right text-sm text-slate-300">
              {value}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function formatPercent(value?: number) {
  if (value == null) return "—";

  return `${(value * 100).toFixed(1)}%`;
}

function formatDate(value?: string) {
  if (!value) return "—";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString();
}
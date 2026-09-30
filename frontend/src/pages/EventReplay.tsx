import { useEffect, useMemo, useState } from "react";

type Transition = {
  id: string;
  vehicle_id?: string;
  from_camera?: string;
  to_camera?: string;
  status?: string;
  confidence?: number;
  created_at?: string;
  evidence?: any;
};

const DEMO_VEHICLE_ID =
  "d3f7e0b6-8fd4-4586-9ef2-4d151c075d11";

export default function EventReplay() {
  const [transitions, setTransitions] = useState<Transition[]>([]);
  const [selected, setSelected] = useState<Transition | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    loadTransitions();
  }, []);

  async function loadTransitions() {
    setLoading(true);
    setError("");

    try {
      const response = await fetch(
        "/api/transitions?status=auto_linked&limit=100"
      );

      if (!response.ok) {
        throw new Error(`Replay API returned ${response.status}`);
      }

      const data = await response.json();

      const all = (data.items ?? []) as Transition[];

      const demo = all.filter(
        (transition) => transition.vehicle_id === DEMO_VEHICLE_ID
      );

      const usable = demo.length > 0 ? demo : all;

      setTransitions(usable);

      if (usable.length > 0) {
        setSelected(usable[0]);
      }
    } catch (err: any) {
      setError(err.message || "Unable to load event replay");
    } finally {
      setLoading(false);
    }
  }

  const selectedEvidence = selected?.evidence ?? {};

  const plateSimilarity = Number(
    selectedEvidence?.plate?.similarity ?? 0
  );

  const reidSimilarity = Number(
    selectedEvidence?.reid?.similarity ?? 0
  );

  const timeFeasibility = Number(
    selectedEvidence?.time?.feasibility ?? 0
  );

  const fusionScore = Number(
    selectedEvidence?.fusion_score ??
      selectedEvidence?.score ??
      selected?.confidence ??
      0
  );

  const travelTime = Number(
    selectedEvidence?.time?.observed_seconds ?? 0
  );

  const cameraFlow = useMemo(
    () =>
      transitions
        .map(
          (item) =>
            `${item.from_camera ?? "?"} → ${item.to_camera ?? "?"}`
        )
        .join("  •  "),
    [transitions]
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-cyan-400">
            Part 6 · Investigation
          </div>

          <h1 className="mt-2 text-3xl font-bold text-white">
            Event Replay
          </h1>

          <p className="mt-2 max-w-3xl text-sm text-slate-400">
            Reconstruct confirmed cross-camera movement and inspect the
            evidence behind each trajectory association.
          </p>
        </div>

        <button
          onClick={loadTransitions}
          disabled={loading}
          className="rounded-lg border border-slate-700 bg-slate-900 px-4 py-2 text-sm font-medium text-slate-300 transition hover:border-cyan-500/50 hover:text-white disabled:opacity-50"
        >
          {loading ? "Loading..." : "Refresh Replay"}
        </button>
      </div>

      {/* Replay status */}
      <div className="rounded-xl border border-cyan-500/20 bg-cyan-500/5 p-5">
        <div className="flex items-center gap-4">
          <div className="h-3 w-3 rounded-full bg-cyan-400" />

          <div>
            <div className="font-semibold text-cyan-300">
              Evidence Replay Ready
            </div>

            <div className="mt-1 text-sm text-slate-400">
              Replaying confirmed trajectory associations from the current
              demonstration dataset.
            </div>
          </div>
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Metric label="Events" value={transitions.length} />
        <Metric
          label="Vehicle"
          value={transitions.length > 0 ? "BDB4668" : "—"}
        />
        <Metric
          label="Transitions"
          value={transitions.length}
        />
        <Metric
          label="Replay State"
          value={transitions.length > 0 ? "READY" : "EMPTY"}
        />
      </div>

      {error && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-5">
          <div className="text-xs uppercase tracking-wider text-red-400">
            Replay Service Error
          </div>

          <div className="mt-2 text-sm text-red-300">{error}</div>
        </div>
      )}

      {loading ? (
        <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-10 text-center text-sm text-slate-400">
          Loading trajectory events...
        </div>
      ) : transitions.length === 0 ? (
        <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-10 text-center">
          <div className="font-semibold text-slate-300">
            No replay events available
          </div>

          <div className="mt-2 text-sm text-slate-500">
            Confirmed cross-camera transitions will appear here once
            available.
          </div>
        </div>
      ) : (
        <>
          {/* Timeline */}
          <section className="rounded-xl border border-slate-800 bg-slate-900/70">
            <div className="border-b border-slate-800 p-6">
              <div className="text-xs uppercase tracking-wider text-slate-500">
                Trajectory Timeline
              </div>

              <h2 className="mt-1 text-lg font-semibold text-white">
                Cross-Camera Movement
              </h2>

              <p className="mt-1 text-xs text-slate-500">
                Select an event to inspect its underlying fusion evidence.
              </p>
            </div>

            <div className="overflow-x-auto p-5">
              <div className="flex min-w-max items-center gap-3">
                {transitions.map((transition, index) => {
                  const score = Number(
                    transition.evidence?.fusion_score ??
                      transition.evidence?.score ??
                      transition.confidence ??
                      0
                  );

                  const active = selected?.id === transition.id;

                  return (
                    <div key={transition.id} className="flex items-center">
                      <button
                        onClick={() => setSelected(transition)}
                        className={`min-w-[145px] rounded-xl border p-4 text-left transition ${
                          active
                            ? "border-cyan-500/50 bg-cyan-500/10"
                            : "border-slate-800 bg-slate-950 hover:border-slate-700"
                        }`}
                      >
                        <div className="text-[10px] uppercase tracking-wider text-slate-500">
                          Event {index + 1}
                        </div>

                        <div className="mt-2 font-semibold text-white">
                          {transition.from_camera ?? "?"}
                          <span className="mx-2 text-cyan-400">→</span>
                          {transition.to_camera ?? "?"}
                        </div>

                        <div className="mt-2 text-xs text-slate-500">
                          Fusion
                        </div>

                        <div className="text-sm font-bold text-cyan-300">
                          {formatPercent(score)}
                        </div>
                      </button>

                      {index < transitions.length - 1 && (
                        <div className="mx-2 text-slate-700">→</div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          </section>

          {/* Selected event */}
          {selected && (
            <section className="grid gap-6 lg:grid-cols-[0.8fr_1.2fr]">
              {/* Event identity */}
              <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-6">
                <div className="text-xs uppercase tracking-wider text-slate-500">
                  Selected Event
                </div>

                <div className="mt-3 text-2xl font-bold text-white">
                  {selected.from_camera ?? "?"}
                  <span className="mx-3 text-cyan-400">→</span>
                  {selected.to_camera ?? "?"}
                </div>

                <div className="mt-2 text-sm text-cyan-300">
                  Vehicle BDB4668
                </div>

                <div className="mt-6 grid grid-cols-2 gap-3">
                  <EvidenceMetric
                    label="Fusion"
                    value={formatPercent(fusionScore)}
                  />

                  <EvidenceMetric
                    label="Travel"
                    value={
                      travelTime > 0
                        ? `${travelTime.toFixed(1)}s`
                        : "—"
                    }
                  />
                </div>

                <div className="mt-4 rounded-lg border border-slate-800 bg-slate-950 p-4">
                  <div className="text-xs uppercase text-slate-500">
                    Status
                  </div>

                  <div className="mt-1 font-semibold text-emerald-300">
                    {selected.status ?? "auto_linked"}
                  </div>
                </div>
              </div>

              {/* Evidence */}
              <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-6">
                <div className="text-xs uppercase tracking-wider text-slate-500">
                  Fusion Evidence
                </div>

                <h2 className="mt-1 text-lg font-semibold text-white">
                  Why this transition was accepted
                </h2>

                <div className="mt-5 space-y-4">
                  <EvidenceBar
                    label="Plate Similarity"
                    value={plateSimilarity}
                  />

                  <EvidenceBar
                    label="Re-ID Similarity"
                    value={reidSimilarity}
                  />

                  <EvidenceBar
                    label="Time Feasibility"
                    value={timeFeasibility}
                  />

                  <EvidenceBar
                    label="Final Fusion Score"
                    value={fusionScore}
                  />
                </div>

                <div className="mt-6 rounded-lg border border-slate-800 bg-slate-950 p-4">
                  <div className="text-xs uppercase tracking-wider text-slate-500">
                    Camera Flow
                  </div>

                  <div className="mt-2 text-sm leading-6 text-slate-300">
                    {cameraFlow}
                  </div>
                </div>

                <details className="mt-4 rounded-lg border border-slate-800 bg-slate-950">
                  <summary className="cursor-pointer px-4 py-3 text-xs uppercase tracking-wider text-slate-500 hover:text-slate-300">
                    Raw Evidence
                  </summary>

                  <pre className="max-h-72 overflow-auto border-t border-slate-800 p-4 text-[11px] leading-5 text-slate-400">
                    {JSON.stringify(selectedEvidence, null, 2)}
                  </pre>
                </details>
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}

function EvidenceBar({
  label,
  value,
}: {
  label: string;
  value: number;
}) {
  const percent = Math.max(
    0,
    Math.min(100, (Number(value) || 0) * 100)
  );

  return (
    <div>
      <div className="flex justify-between text-xs">
        <span className="text-slate-400">{label}</span>

        <span className="font-semibold text-cyan-300">
          {percent.toFixed(1)}%
        </span>
      </div>

      <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-800">
        <div
          className="h-full rounded-full bg-cyan-500 transition-all"
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
}

function EvidenceMetric({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-950 p-4">
      <div className="text-[10px] uppercase text-slate-500">
        {label}
      </div>

      <div className="mt-2 text-xl font-bold text-white">
        {value}
      </div>
    </div>
  );
}

function Metric({
  label,
  value,
}: {
  label: string;
  value: string | number;
}) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
      <div className="text-xs uppercase tracking-wider text-slate-500">
        {label}
      </div>

      <div className="mt-2 text-2xl font-bold text-white">{value}</div>
    </div>
  );
}

function formatPercent(value: number) {
  const n = Number(value) || 0;
  return `${(n <= 1 ? n * 100 : n).toFixed(1)}%`;
}
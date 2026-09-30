import { useState } from "react";

type Metrics = {
  observed_trip_count?: number;
  trip_count?: number;
  total_trips?: number;
  estimated_delay_factor?: number;
  [key: string]: any;
};

export default function WhatIfSimulator() {
  const [name, setName] = useState("Demo Road Closure");
  const [scenarioType, setScenarioType] = useState("road_closure");
  const [roads, setRoads] = useState("1,2");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState("");

  async function runSimulation() {
    setLoading(true);
    setError("");
    setResult(null);

    try {
      const affected_road_ids = roads
        .split(",")
        .map((x) => Number(x.trim()))
        .filter((x) => Number.isFinite(x));

      if (affected_road_ids.length === 0) {
        throw new Error("Enter at least one valid road ID.");
      }

      const response = await fetch("/api/simulation", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          name,
          scenario_type: scenarioType,
          affected_road_ids,
          created_by: "SIH Demo",
        }),
      });

      if (!response.ok) {
        const body = await response.text();
        throw new Error(
          body || `Simulation failed with status ${response.status}`
        );
      }

      setResult(await response.json());
    } catch (err: any) {
      setError(err.message || "Simulation failed");
    } finally {
      setLoading(false);
    }
  }

  const before: Metrics = result?.before_metrics ?? {};
  const after: Metrics = result?.after_metrics ?? {};

  const beforeTrips = getTrips(before);
  const afterTrips = getTrips(after);

  const beforeDelay = getDelay(before);
  const afterDelay = getDelay(after);

  const tripDelta = afterTrips - beforeTrips;
  const delayDelta = afterDelay - beforeDelay;

  const affectedRoads = roads
    .split(",")
    .map((x) => x.trim())
    .filter(Boolean);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="text-xs uppercase tracking-[0.2em] text-cyan-400">
          Part 5 · Decision Support
        </div>

        <h1 className="mt-2 text-3xl font-bold text-white">
          What-If Simulator
        </h1>

        <p className="mt-2 max-w-3xl text-sm text-slate-400">
          Evaluate hypothetical network disruptions against the current
          traffic state without modifying real-world observations.
        </p>
      </div>

      {/* Status banner */}
      <div className="flex items-start gap-4 rounded-xl border border-amber-500/30 bg-amber-500/5 p-5">
        <div className="mt-1 h-2.5 w-2.5 shrink-0 rounded-full bg-amber-400 shadow-[0_0_12px_rgba(251,191,36,0.7)]" />

        <div>
          <div className="font-semibold text-amber-300">
            SIMULATION MODE · ISOLATED
          </div>

          <div className="mt-1 text-sm text-slate-400">
            Hypothetical scenarios are evaluated independently. Production
            vehicle observations and trajectory records are not modified.
          </div>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
        {/* Configuration */}
        <section className="rounded-xl border border-slate-800 bg-slate-900/70">
          <div className="border-b border-slate-800 p-6">
            <div className="text-xs uppercase tracking-wider text-slate-500">
              Scenario Builder
            </div>

            <h2 className="mt-1 text-lg font-semibold text-white">
              Network Scenario
            </h2>

            <p className="mt-1 text-xs text-slate-500">
              Define the hypothetical disruption to evaluate.
            </p>
          </div>

          <div className="space-y-5 p-6">
            {/* Scenario name */}
            <div>
              <label className="text-xs uppercase tracking-wider text-slate-500">
                Scenario name
              </label>

              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-950 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-500"
              />
            </div>

            {/* Scenario type */}
            <div>
              <label className="text-xs uppercase tracking-wider text-slate-500">
                Scenario type
              </label>

              <select
                value={scenarioType}
                onChange={(e) => setScenarioType(e.target.value)}
                className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-950 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-500"
              >
                <option value="road_closure">Road Closure</option>
                <option value="lane_reduction">Lane Reduction</option>
                <option value="incident">Traffic Incident</option>
                <option value="construction">Construction</option>
              </select>
            </div>

            {/* Roads */}
            <div>
              <label className="text-xs uppercase tracking-wider text-slate-500">
                Affected road IDs
              </label>

              <input
                value={roads}
                onChange={(e) => setRoads(e.target.value)}
                placeholder="1,2,3"
                className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-950 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-500"
              />

              <div className="mt-2 flex flex-wrap gap-2">
                {affectedRoads.map((road) => (
                  <span
                    key={road}
                    className="rounded-full border border-cyan-500/20 bg-cyan-500/10 px-3 py-1 text-xs text-cyan-300"
                  >
                    Road R{road.padStart(2, "0")}
                  </span>
                ))}
              </div>
            </div>

            {/* Run */}
            <button
              onClick={runSimulation}
              disabled={loading}
              className="w-full rounded-lg bg-cyan-500 px-4 py-3 font-semibold text-slate-950 transition hover:bg-cyan-400 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-950/30 border-t-slate-950" />
                  Evaluating Network...
                </span>
              ) : (
                "Run Network Simulation"
              )}
            </button>
          </div>
        </section>

        {/* Results */}
        <section className="rounded-xl border border-slate-800 bg-slate-900/70">
          <div className="border-b border-slate-800 p-6">
            <div className="text-xs uppercase tracking-wider text-slate-500">
              Simulation Output
            </div>

            <h2 className="mt-1 text-lg font-semibold text-white">
              Network Impact
            </h2>
          </div>

          {!result && !error && (
            <div className="flex min-h-[380px] flex-col items-center justify-center px-8 text-center">
              <div className="rounded-full border border-cyan-500/20 bg-cyan-500/5 px-4 py-2 text-xs uppercase tracking-wider text-cyan-400">
                Awaiting Scenario
              </div>

              <div className="mt-4 text-sm font-medium text-slate-300">
                Configure a disruption and run the simulation.
              </div>

              <div className="mt-2 max-w-sm text-xs leading-5 text-slate-500">
                URBANTRACE will compare the simulated network state with the
                current baseline metrics.
              </div>
            </div>
          )}

          {error && (
            <div className="p-6">
              <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-4">
                <div className="text-xs uppercase tracking-wider text-red-400">
                  Simulation Error
                </div>

                <div className="mt-2 text-sm text-red-300">{error}</div>
              </div>
            </div>
          )}

          {result && (
            <div className="space-y-5 p-6">
              {/* Scenario identity */}
              <div className="rounded-lg border border-slate-800 bg-slate-950 p-4">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="text-xs uppercase tracking-wider text-slate-500">
                      Active Scenario
                    </div>

                    <div className="mt-1 font-semibold text-white">
                      {result.name ?? name}
                    </div>

                    <div className="mt-1 text-xs text-cyan-400">
                      {formatScenario(result.scenario_type ?? scenarioType)}
                    </div>
                  </div>

                  <div className="rounded-full border border-cyan-500/20 bg-cyan-500/10 px-3 py-1 text-xs text-cyan-300">
                    SIMULATED
                  </div>
                </div>
              </div>

              {/* KPI comparison */}
              <div className="grid grid-cols-2 gap-4">
                <ComparisonMetric
                  label="Baseline Trips"
                  value={formatNumber(beforeTrips)}
                />

                <ComparisonMetric
                  label="Simulated Trips"
                  value={formatNumber(afterTrips)}
                  delta={tripDelta}
                  suffix=""
                />

                <ComparisonMetric
                  label="Baseline Delay"
                  value={`${beforeDelay.toFixed(2)}x`}
                />

                <ComparisonMetric
                  label="Simulated Delay"
                  value={`${afterDelay.toFixed(2)}x`}
                  delta={delayDelta}
                  suffix="x"
                />
              </div>

              {/* Impact summary */}
              <div className="rounded-lg border border-cyan-500/20 bg-cyan-500/5 p-5">
                <div className="text-xs uppercase tracking-wider text-cyan-400">
                  Decision Support
                </div>

                <div className="mt-3 text-sm leading-6 text-slate-300">
                  The scenario was evaluated against the current network
                  state. The simulation is isolated from production
                  observations.
                </div>

                <div className="mt-4 grid grid-cols-2 gap-3">
                  <div className="rounded-lg bg-slate-950/70 p-3">
                    <div className="text-[10px] uppercase text-slate-500">
                      Affected Roads
                    </div>

                    <div className="mt-1 text-lg font-bold text-white">
                      {affectedRoads.length}
                    </div>
                  </div>

                  <div className="rounded-lg bg-slate-950/70 p-3">
                    <div className="text-[10px] uppercase text-slate-500">
                      Network State
                    </div>

                    <div className="mt-1 text-sm font-semibold text-cyan-300">
                      Simulated
                    </div>
                  </div>
                </div>
              </div>

              {/* Raw response for transparency */}
              <details className="rounded-lg border border-slate-800 bg-slate-950">
                <summary className="cursor-pointer px-4 py-3 text-xs uppercase tracking-wider text-slate-500 hover:text-slate-300">
                  Simulation Evidence
                </summary>

                <pre className="max-h-64 overflow-auto border-t border-slate-800 p-4 text-[11px] leading-5 text-slate-400">
                  {JSON.stringify(result, null, 2)}
                </pre>
              </details>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

function ComparisonMetric({
  label,
  value,
  delta,
  suffix = "",
}: {
  label: string;
  value: string;
  delta?: number;
  suffix?: string;
}) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-950 p-4">
      <div className="text-xs uppercase tracking-wider text-slate-500">
        {label}
      </div>

      <div className="mt-2 text-2xl font-bold text-white">{value}</div>

      {delta !== undefined && (
        <div className="mt-1 text-xs text-slate-500">
          Δ {delta > 0 ? "+" : ""}
          {delta.toFixed(2)}
          {suffix}
        </div>
      )}
    </div>
  );
}

function getTrips(metrics: Metrics) {
  return Number(
    metrics.observed_trip_count ??
      metrics.trip_count ??
      metrics.total_trips ??
      0
  );
}

function getDelay(metrics: Metrics) {
  return Number(metrics.estimated_delay_factor ?? 1);
}

function formatNumber(value: number) {
  return Number.isFinite(value) ? value.toLocaleString() : "0";
}

function formatScenario(value: string) {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}
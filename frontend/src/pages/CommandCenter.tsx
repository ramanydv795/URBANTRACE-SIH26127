import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";

const DEMO_VEHICLE_ID =
  "d3f7e0b6-8fd4-4586-9ef2-4d151c075d11";

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
    time?: { feasibility?: number };
  };
};

type Vehicle = {
  id: string;
  plate_best?: string;
  vehicle_type?: string;
  color?: string;
  first_seen?: string;
  last_seen?: string;
};

function pct(value?: number) {
  if (value == null) return "—";
  return `${(value * 100).toFixed(1)}%`;
}

function shortTime(value?: string) {
  if (!value) return "—";
  return new Date(value).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export default function CommandCenter() {
  const [summary, setSummary] = useState<any>(null);
  const [cameras, setCameras] = useState<any[]>([]);
  const [transitions, setTransitions] = useState<Transition[]>([]);
  const [vehicle, setVehicle] = useState<Vehicle | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [city, cams, transitionData, vehicles] = await Promise.all([
          api.citySummary(),
          api.cameras(),
          fetch("/api/transitions?status=auto_linked&limit=100").then((r) =>
            r.json()
          ),
          fetch("/api/vehicles/search?plate=BDB4668").then((r) => r.json()),
        ]);

        setSummary(city);
        setCameras(cams.cameras || []);

        const demoTransitions = (transitionData.items || [])
          .filter(
            (t: Transition) => t.vehicle_id === DEMO_VEHICLE_ID
          )
          .sort(
            (a: Transition, b: Transition) =>
              (b.evidence?.fusion_score ?? b.confidence ?? 0) -
              (a.evidence?.fusion_score ?? a.confidence ?? 0)
          );

        setTransitions(demoTransitions);

        const found =
          (vehicles.items || []).find(
            (v: Vehicle) => v.id === DEMO_VEHICLE_ID
          ) || null;

        setVehicle(found);
      } catch (err) {
        console.error("Command Center load failed:", err);
      } finally {
        setLoading(false);
      }
    }

    load();
  }, []);

  const avgConfidence = useMemo(() => {
    if (!transitions.length) return 0;

    return (
      transitions.reduce(
        (sum, t) =>
          sum + (t.evidence?.fusion_score ?? t.confidence ?? 0),
        0
      ) / transitions.length
    );
  }, [transitions]);

  const latest = transitions.slice(0, 5);

  if (loading) {
    return (
      <div className="p-8">
        <div className="rounded-2xl border border-slate-200 bg-white p-8 text-slate-500">
          Loading command center…
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      {/* HEADER */}
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
        <div>
          <div className="mb-2 flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" />
            <span className="text-xs font-semibold uppercase tracking-[0.18em] text-emerald-600">
              System Operational
            </span>
          </div>

          <h1 className="text-3xl font-bold tracking-tight text-slate-900">
            Command Center
          </h1>

          <p className="mt-1 text-sm text-slate-500">
            City-wide vehicle intelligence and trajectory monitoring
          </p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-right shadow-sm">
          <div className="text-xs uppercase tracking-wider text-slate-400">
            Deployment
          </div>
          <div className="font-semibold text-slate-800">
            Demo City · SIH26127
          </div>
        </div>
      </div>

      {/* KPI GRID */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Metric
          label="Cameras"
          value={summary?.cameras ?? cameras.length}
          sub="Network coverage"
        />

        <Metric
          label="Active Vehicles"
          value={vehicle ? 1 : 0}
          sub="Tracked globally"
        />

        <Metric
          label="Transitions"
          value={transitions.length}
          sub="Auto-linked"
        />

        <Metric
          label="Fusion Confidence"
          value={pct(avgConfidence)}
          sub="Trajectory intelligence"
        />
      </div>

      {/* MAIN GRID */}
      <div className="grid gap-6 lg:grid-cols-[1.5fr_1fr]">
        {/* CITY NETWORK */}
        <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
            <div>
              <h2 className="font-semibold text-slate-900">
                Live City Network
              </h2>
              <p className="text-xs text-slate-500">
                Camera topology and vehicle movement
              </p>
            </div>

            <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700">
              LIVE
            </span>
          </div>

          <div className="relative min-h-[340px] overflow-hidden bg-slate-50">
            {/* roads */}
            <div className="absolute left-[12%] right-[12%] top-1/2 h-3 -translate-y-1/2 rounded-full bg-slate-300" />
            <div className="absolute bottom-[15%] left-1/2 top-[15%] w-3 -translate-x-1/2 rounded-full bg-slate-300" />
            <div className="absolute left-[18%] right-[18%] top-[25%] h-2 rotate-[18deg] rounded-full bg-slate-200" />

            {/* C01 */}
            <CameraNode
              code="C01"
              name="North Junction"
              left="18%"
              top="50%"
              active
            />

            {/* C02 */}
            <CameraNode
              code="C02"
              name="Central Road"
              left="50%"
              top="50%"
              active
            />

            {/* C03 */}
            <CameraNode
              code="C03"
              name="South Junction"
              left="50%"
              top="80%"
            />

            {/* C04 */}
            <CameraNode
              code="C04"
              name="East Corridor"
              left="82%"
              top="50%"
            />

            {/* movement line */}
            <div className="absolute left-[25%] right-[50%] top-1/2 h-0.5 -translate-y-1/2 bg-blue-500">
              <div className="absolute right-0 top-1/2 -translate-y-1/2 border-y-[6px] border-l-[9px] border-y-transparent border-l-blue-500" />
            </div>

            {/* vehicle */}
            <div className="absolute left-[37%] top-[calc(50%-12px)] rounded-lg border border-blue-200 bg-white px-2 py-1 text-[10px] font-bold text-blue-700 shadow">
              BDB4668
            </div>

            <div className="absolute bottom-4 left-4 rounded-xl border border-slate-200 bg-white/90 px-3 py-2 text-xs text-slate-500 backdrop-blur">
              <div className="font-medium text-slate-700">
                Movement Graph
              </div>
              <div>C01 → C02</div>
            </div>
          </div>
        </section>

        {/* VEHICLE INTELLIGENCE */}
        <section className="rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div className="border-b border-slate-100 px-5 py-4">
            <h2 className="font-semibold text-slate-900">
              Vehicle Intelligence
            </h2>
            <p className="text-xs text-slate-500">
              Global identity currently under observation
            </p>
          </div>

          <div className="p-5">
            {vehicle ? (
              <>
                <div className="flex items-center justify-between">
                  <div>
                    <div className="font-mono text-2xl font-bold tracking-wider text-slate-900">
                      {vehicle.plate_best || "BDB4668"}
                    </div>
                    <div className="mt-1 text-sm text-slate-500">
                      {vehicle.vehicle_type || "CAR"} ·{" "}
                      {vehicle.color || "Black"}
                    </div>
                  </div>

                  <div className="rounded-xl bg-blue-50 px-4 py-3 text-center">
                    <div className="text-xl font-bold text-blue-700">
                      {pct(avgConfidence)}
                    </div>
                    <div className="text-[10px] uppercase tracking-wider text-blue-500">
                      Fusion
                    </div>
                  </div>
                </div>

                <div className="mt-6 grid grid-cols-2 gap-3">
                  <Info label="First Seen" value={shortTime(vehicle.first_seen)} />
                  <Info label="Last Seen" value={shortTime(vehicle.last_seen)} />
                  <Info label="Transitions" value={`${transitions.length}`} />
                  <Info label="Identity" value="Global" />
                </div>

                <div className="mt-5 rounded-xl bg-slate-50 p-4">
                  <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
                    Journey
                  </div>

                  <div className="flex items-center gap-2">
                    <span className="rounded-lg bg-white px-3 py-2 text-sm font-bold text-slate-700 shadow-sm">
                      C01
                    </span>
                    <span className="text-slate-400">→</span>
                    <span className="rounded-lg bg-white px-3 py-2 text-sm font-bold text-slate-700 shadow-sm">
                      C02
                    </span>
                    <span className="text-slate-400">→</span>
                    <span className="rounded-lg bg-white px-3 py-2 text-sm font-bold text-slate-700 shadow-sm">
                      C01
                    </span>
                    <span className="text-xs text-slate-400">
                      +{Math.max(0, transitions.length - 2)}
                    </span>
                  </div>
                </div>
              </>
            ) : (
              <div className="py-10 text-center text-sm text-slate-400">
                No active vehicle detected.
              </div>
            )}
          </div>
        </section>
      </div>

      {/* RECENT TRANSITIONS */}
      <section className="rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
          <div>
            <h2 className="font-semibold text-slate-900">
              Recent Trajectory Intelligence
            </h2>
            <p className="text-xs text-slate-500">
              Cross-camera associations produced by the fusion engine
            </p>
          </div>

          <a
            href="/explainer"
            className="text-xs font-semibold text-blue-600 hover:text-blue-700"
          >
            Inspect Evidence →
          </a>
        </div>

        <div className="divide-y divide-slate-100">
          {latest.map((transition) => {
            const score =
              transition.evidence?.fusion_score ??
              transition.confidence ??
              0;

            const plate = transition.evidence?.plate?.similarity;
            const reid = transition.evidence?.reid?.similarity;

            return (
              <div
                key={transition.id}
                className="grid gap-3 px-5 py-4 md:grid-cols-[1.2fr_1fr_1fr_auto] md:items-center"
              >
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-slate-800">
                      {transition.from_camera || "C01"}
                    </span>
                    <span className="text-slate-400">→</span>
                    <span className="font-semibold text-slate-800">
                      {transition.to_camera || "C02"}
                    </span>
                  </div>

                  <div className="mt-1 font-mono text-xs text-slate-400">
                    {vehicle?.plate_best || "BDB4668"}
                  </div>
                </div>

                <Signal
                  label="Plate"
                  value={pct(plate)}
                />

                <Signal
                  label="Re-ID"
                  value={pct(reid)}
                />

                <div className="flex items-center gap-3">
                  <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700">
                    AUTO-LINKED
                  </span>

                  <span className="font-bold text-slate-900">
                    {pct(score)}
                  </span>
                </div>
              </div>
            );
          })}

          {!latest.length && (
            <div className="px-5 py-10 text-center text-sm text-slate-400">
              No trajectory transitions available.
            </div>
          )}
        </div>
      </section>

      {/* ENGINE STATUS */}
      <section>
        <div className="mb-3">
          <h2 className="font-semibold text-slate-900">Intelligence Stack</h2>
          <p className="text-xs text-slate-500">
            Current URBANTRACE processing pipeline
          </p>
        </div>

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <Status name="Detection" detail="YOLO + ByteTrack" />
          <Status name="ANPR" detail="PaddleOCR" />
          <Status name="Re-ID" detail="144-d embedding" />
          <Status name="Movement Graph" detail="Topology engine" />
          <Status name="Trajectory Fusion" detail="Multi-signal" />
        </div>
      </section>
    </div>
  );
}

function Metric({
  label,
  value,
  sub,
}: {
  label: string;
  value: string | number;
  sub: string;
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="text-xs font-semibold uppercase tracking-wider text-slate-400">
        {label}
      </div>
      <div className="mt-2 text-3xl font-bold tracking-tight text-slate-900">
        {value}
      </div>
      <div className="mt-1 text-xs text-slate-500">{sub}</div>
    </div>
  );
}

function CameraNode({
  code,
  name,
  left,
  top,
  active = false,
}: {
  code: string;
  name: string;
  left: string;
  top: string;
  active?: boolean;
}) {
  return (
    <div
      className="absolute -translate-x-1/2 -translate-y-1/2"
      style={{ left, top }}
    >
      <div
        className={`flex h-12 w-12 items-center justify-center rounded-full border-4 bg-white text-xs font-bold shadow-lg ${
          active
            ? "border-blue-500 text-blue-700"
            : "border-slate-300 text-slate-500"
        }`}
      >
        {code}
      </div>

      <div className="mt-2 whitespace-nowrap rounded-md bg-white px-2 py-1 text-center text-[10px] font-medium text-slate-600 shadow-sm">
        {name}
      </div>
    </div>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-100 bg-slate-50 p-3">
      <div className="text-[10px] uppercase tracking-wider text-slate-400">
        {label}
      </div>
      <div className="mt-1 text-sm font-semibold text-slate-700">
        {value}
      </div>
    </div>
  );
}

function Signal({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wider text-slate-400">
        {label}
      </div>
      <div className="mt-1 text-sm font-semibold text-slate-700">
        {value}
      </div>
    </div>
  );
}

function Status({ name, detail }: { name: string; detail: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-center gap-2">
        <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" />
        <span className="text-sm font-semibold text-slate-800">{name}</span>
      </div>
      <div className="mt-2 text-xs text-slate-500">{detail}</div>
      <div className="mt-3 text-[10px] font-semibold uppercase tracking-wider text-emerald-600">
        Operational
      </div>
    </div>
  );
}

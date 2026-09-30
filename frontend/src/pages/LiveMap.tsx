import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Camera = {
  code: string;
  name: string;
  lat: number;
  lng: number;
  road: string;
  zone: string;
  direction_deg: number;
  status: string;
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
  };
};

const DEMO_PLATE = "BDB4668";

function pct(value?: number) {
  if (value == null) return "—";
  return `${(value * 100).toFixed(1)}%`;
}

export default function LiveMap() {
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [transitions, setTransitions] = useState<Transition[]>([]);
  const [selectedCamera, setSelectedCamera] = useState<Camera | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const [cameraData, transitionData] = await Promise.all([
          api.cameras(),
          fetch("/api/transitions?status=auto_linked&limit=100").then((r) =>
            r.json()
          ),
        ]);

        setCameras(cameraData.cameras || []);

        const demoTransitions = (transitionData.items || []).filter(
          (t: Transition) =>
            t.vehicle_id ===
            "d3f7e0b6-8fd4-4586-9ef2-4d151c075d11"
        );

        setTransitions(demoTransitions);
      } catch (error) {
        console.error("Live map failed:", error);
      }
    }

    load();
  }, []);

  const activeCameraCodes = new Set(
    transitions.flatMap((t) => [t.from_camera, t.to_camera])
  );

  return (
    <div className="space-y-6 p-6">
      {/* HEADER */}
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
        <div>
          <div className="mb-2 flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" />
            <span className="text-xs font-semibold uppercase tracking-[0.18em] text-emerald-600">
              Network Live
            </span>
          </div>

          <h1 className="text-3xl font-bold tracking-tight text-slate-900">
            Live Traffic Map
          </h1>

          <p className="mt-1 text-sm text-slate-500">
            City-wide camera network, movement graph and vehicle trajectories
          </p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
          <div className="text-xs uppercase tracking-wider text-slate-400">
            Monitoring
          </div>
          <div className="font-semibold text-slate-800">
            Demo City · SIH26127
          </div>
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Metric
          label="Cameras"
          value={cameras.length || 25}
          sub="Network nodes"
        />

        <Metric
          label="Online"
          value={
            cameras.filter(
              (c) =>
                c.status === "online" ||
                c.status === "active" ||
                c.status === "healthy"
            ).length || cameras.length
          }
          sub="Operational"
        />

        <Metric
          label="Tracked Vehicle"
          value={DEMO_PLATE}
          sub="Global identity"
        />

        <Metric
          label="Transitions"
          value={transitions.length}
          sub="Trajectory links"
        />
      </div>

      {/* MAP */}
      <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
          <div>
            <h2 className="font-semibold text-slate-900">
              Movement Graph
            </h2>
            <p className="text-xs text-slate-500">
              Camera topology and active vehicle trajectory
            </p>
          </div>

          <div className="flex items-center gap-4 text-xs">
            <Legend dot="bg-blue-500" label="Active camera" />
            <Legend dot="bg-emerald-500" label="Tracked vehicle" />
            <Legend dot="bg-slate-300" label="Camera" />
          </div>
        </div>

        <div className="relative h-[560px] overflow-hidden bg-slate-50">
          {/* GRID */}
          <div
            className="absolute inset-0 opacity-40"
            style={{
              backgroundImage:
                "linear-gradient(#cbd5e1 1px, transparent 1px), linear-gradient(90deg, #cbd5e1 1px, transparent 1px)",
              backgroundSize: "40px 40px",
            }}
          />

          {/* ROADS */}
          <div className="absolute left-[8%] right-[8%] top-[48%] h-5 -translate-y-1/2 rounded-full bg-slate-300" />
          <div className="absolute bottom-[8%] left-[48%] top-[8%] w-5 -translate-x-1/2 rounded-full bg-slate-300" />
          <div className="absolute left-[15%] right-[15%] top-[27%] h-4 rotate-[17deg] rounded-full bg-slate-200" />
          <div className="absolute bottom-[25%] left-[15%] right-[15%] h-4 -rotate-[12deg] rounded-full bg-slate-200" />

          {/* ROUTE */}
          <div className="absolute left-[20%] right-[48%] top-[48%] h-1 -translate-y-1/2 bg-blue-500">
            <div className="absolute right-0 top-1/2 -translate-y-1/2 border-y-[8px] border-l-[12px] border-y-transparent border-l-blue-500" />
          </div>

          <div className="absolute bottom-[31%] left-[48%] top-[48%] w-1 bg-blue-500">
            <div className="absolute bottom-0 left-1/2 -translate-x-1/2 border-x-[8px] border-y-[12px] border-x-transparent border-b-blue-500" />
          </div>

          {/* CAMERA NODES */}
          <MapNode
            code="C01"
            name="North Junction"
            left="20%"
            top="48%"
            active={activeCameraCodes.has("C01")}
            onClick={() =>
              setSelectedCamera(
                cameras.find((c) => c.code === "C01") || null
              )
            }
          />

          <MapNode
            code="C02"
            name="Central Road"
            left="48%"
            top="48%"
            active={activeCameraCodes.has("C02")}
            onClick={() =>
              setSelectedCamera(
                cameras.find((c) => c.code === "C02") || null
              )
            }
          />

          <MapNode
            code="C03"
            name="South Junction"
            left="48%"
            top="78%"
            onClick={() =>
              setSelectedCamera(
                cameras.find((c) => c.code === "C03") || null
              )
            }
          />

          <MapNode
            code="C04"
            name="East Corridor"
            left="80%"
            top="48%"
            onClick={() =>
              setSelectedCamera(
                cameras.find((c) => c.code === "C04") || null
              )
            }
          />

          {/* VEHICLE */}
          <div className="absolute left-[33%] top-[calc(48%-18px)]">
            <div className="relative flex items-center gap-2 rounded-xl border border-emerald-200 bg-white px-3 py-2 shadow-lg">
              <span className="absolute -left-2 -top-2 h-4 w-4 animate-ping rounded-full bg-emerald-400 opacity-60" />
              <span className="h-3 w-3 rounded-full bg-emerald-500" />

              <div>
                <div className="font-mono text-xs font-bold text-slate-900">
                  {DEMO_PLATE}
                </div>
                <div className="text-[9px] uppercase tracking-wider text-emerald-600">
                  Tracked
                </div>
              </div>
            </div>
          </div>

          {/* MAP STATUS */}
          <div className="absolute bottom-5 left-5 rounded-xl border border-slate-200 bg-white/95 px-4 py-3 shadow-lg backdrop-blur">
            <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
              Active Trajectory
            </div>

            <div className="mt-1 flex items-center gap-2">
              <span className="font-semibold text-slate-800">C01</span>
              <span className="text-blue-500">→</span>
              <span className="font-semibold text-slate-800">C02</span>
            </div>

            <div className="mt-1 text-xs text-slate-500">
              Vehicle {DEMO_PLATE}
            </div>
          </div>

          {/* CAMERA INFO */}
          {selectedCamera && (
            <div className="absolute right-5 top-5 w-64 rounded-2xl border border-slate-200 bg-white/95 p-4 shadow-xl backdrop-blur">
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-xl font-bold text-slate-900">
                    {selectedCamera.code}
                  </div>
                  <div className="text-xs text-slate-500">
                    {selectedCamera.name}
                  </div>
                </div>

                <button
                  onClick={() => setSelectedCamera(null)}
                  className="text-slate-400 hover:text-slate-700"
                >
                  ×
                </button>
              </div>

              <div className="mt-4 space-y-2">
                <Row label="Road" value={selectedCamera.road || "—"} />
                <Row label="Zone" value={selectedCamera.zone || "—"} />
                <Row
                  label="Direction"
                  value={`${selectedCamera.direction_deg ?? 0}°`}
                />
                <Row
                  label="Status"
                  value={selectedCamera.status || "Online"}
                />
              </div>
            </div>
          )}
        </div>
      </section>

      {/* CAMERA NETWORK */}
      <section className="rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-100 px-5 py-4">
          <h2 className="font-semibold text-slate-900">
            Camera Network
          </h2>
          <p className="text-xs text-slate-500">
            Registered city surveillance nodes
          </p>
        </div>

        <div className="grid gap-3 p-5 sm:grid-cols-2 lg:grid-cols-4">
          {cameras.slice(0, 8).map((camera) => (
            <button
              key={camera.code}
              onClick={() => setSelectedCamera(camera)}
              className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-left transition hover:-translate-y-0.5 hover:bg-white hover:shadow-sm"
            >
              <div className="flex items-center justify-between">
                <span className="font-bold text-slate-800">
                  {camera.code}
                </span>

                <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" />
              </div>

              <div className="mt-2 text-xs text-slate-500">
                {camera.name}
              </div>

              <div className="mt-3 text-[10px] uppercase tracking-wider text-slate-400">
                {camera.road || "Road network"}
              </div>
            </button>
          ))}
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

      <div className="mt-2 truncate text-2xl font-bold tracking-tight text-slate-900">
        {value}
      </div>

      <div className="mt-1 text-xs text-slate-500">{sub}</div>
    </div>
  );
}

function MapNode({
  code,
  name,
  left,
  top,
  active = false,
  onClick,
}: {
  code: string;
  name: string;
  left: string;
  top: string;
  active?: boolean;
  onClick?: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="absolute -translate-x-1/2 -translate-y-1/2 text-center"
      style={{ left, top }}
    >
      <div
        className={`mx-auto flex h-16 w-16 items-center justify-center rounded-full border-4 bg-white text-sm font-bold shadow-xl transition hover:scale-105 ${
          active
            ? "border-blue-500 text-blue-700"
            : "border-slate-300 text-slate-500"
        }`}
      >
        {code}
      </div>

      <div className="mt-2 whitespace-nowrap rounded-lg bg-white px-3 py-1.5 text-[10px] font-semibold text-slate-600 shadow-sm">
        {name}
      </div>
    </button>
  );
}

function Legend({ dot, label }: { dot: string; label: string }) {
  return (
    <div className="flex items-center gap-1.5 text-slate-500">
      <span className={`h-2.5 w-2.5 rounded-full ${dot}`} />
      {label}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between border-b border-slate-100 py-2 last:border-0">
      <span className="text-xs text-slate-400">{label}</span>
      <span className="max-w-[150px] truncate text-xs font-semibold text-slate-700">
        {value}
      </span>
    </div>
  );
}
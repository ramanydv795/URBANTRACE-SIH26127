import { useEffect, useMemo, useState } from "react";

type Camera = {
  code: string;
  name?: string;
  lat?: number;
  lng?: number;
  road?: string;
  zone?: string;
  direction_deg?: number;
  status?: string;
};

export default function CameraHealth() {
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    loadCameras();
  }, []);

  async function loadCameras() {
    setLoading(true);
    setError("");

    try {
      const response = await fetch("/api/cameras");

      if (!response.ok) {
        throw new Error(`Camera API returned ${response.status}`);
      }

      const data = await response.json();

      setCameras(data.cameras ?? data.items ?? []);
    } catch (err: any) {
      setError(err.message || "Unable to load camera health");
      setCameras([]);
    } finally {
      setLoading(false);
    }
  }

  const stats = useMemo(() => {
    const online = cameras.filter(
      (camera) => normalizeStatus(camera.status) === "online"
    ).length;

    const offline = cameras.filter(
      (camera) => normalizeStatus(camera.status) === "offline"
    ).length;

    const degraded = cameras.filter(
      (camera) => normalizeStatus(camera.status) === "degraded"
    ).length;

    return {
      total: cameras.length,
      online,
      offline,
      degraded,
    };
  }, [cameras]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-cyan-400">
            Part 4 · Infrastructure
          </div>

          <h1 className="mt-2 text-3xl font-bold text-white">
            Camera Health
          </h1>

          <p className="mt-2 max-w-3xl text-sm text-slate-400">
            Operational status of the city-wide camera network feeding the
            URBANTRACE perception pipeline.
          </p>
        </div>

        <button
          onClick={loadCameras}
          disabled={loading}
          className="rounded-lg border border-slate-700 bg-slate-900 px-4 py-2 text-sm font-medium text-slate-300 transition hover:border-cyan-500/50 hover:text-white disabled:opacity-50"
        >
          {loading ? "Refreshing..." : "Refresh Network"}
        </button>
      </div>

      {/* Network state */}
      <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-5">
        <div className="flex items-center gap-4">
          <div className="h-3 w-3 rounded-full bg-emerald-400" />

          <div>
            <div className="font-semibold text-emerald-300">
              Camera Network Connected
            </div>

            <div className="mt-1 text-sm text-slate-400">
              Camera inventory is being served by the live URBANTRACE API.
            </div>
          </div>
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Metric label="Total cameras" value={stats.total} />
        <Metric label="Online" value={stats.online} emphasis="online" />
        <Metric label="Degraded" value={stats.degraded} emphasis="degraded" />
        <Metric label="Offline" value={stats.offline} emphasis="offline" />
      </div>

      {error && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-5">
          <div className="text-xs uppercase tracking-wider text-red-400">
            Camera Service Error
          </div>

          <div className="mt-2 text-sm text-red-300">{error}</div>
        </div>
      )}

      {/* Camera network */}
      <section className="rounded-xl border border-slate-800 bg-slate-900/70">
        <div className="border-b border-slate-800 p-6">
          <div className="text-xs uppercase tracking-wider text-slate-500">
            Network Inventory
          </div>

          <h2 className="mt-1 text-lg font-semibold text-white">
            Camera Nodes
          </h2>

          <p className="mt-1 text-xs text-slate-500">
            Live camera metadata and operational state.
          </p>
        </div>

        {loading ? (
          <div className="p-10 text-center text-sm text-slate-400">
            Loading camera network...
          </div>
        ) : cameras.length === 0 ? (
          <div className="p-10 text-center text-sm text-slate-500">
            No camera records available.
          </div>
        ) : (
          <div className="grid gap-4 p-5 md:grid-cols-2 xl:grid-cols-3">
            {cameras.map((camera) => (
              <CameraCard key={camera.code} camera={camera} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function CameraCard({ camera }: { camera: Camera }) {
  const status = normalizeStatus(camera.status);

  const statusClasses =
    status === "online"
      ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-300"
      : status === "degraded"
        ? "border-amber-500/20 bg-amber-500/10 text-amber-300"
        : status === "offline"
          ? "border-red-500/20 bg-red-500/10 text-red-300"
          : "border-slate-700 bg-slate-800 text-slate-400";

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-5 transition hover:border-cyan-500/20">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-lg font-bold text-white">
            {camera.code}
          </div>

          <div className="mt-1 text-xs text-slate-500">
            {camera.name ?? `Camera ${camera.code}`}
          </div>
        </div>

        <span
          className={`rounded-full border px-3 py-1 text-[10px] font-semibold uppercase ${statusClasses}`}
        >
          {status}
        </span>
      </div>

      <div className="mt-5 space-y-3">
        <InfoRow label="Road" value={camera.road ?? "—"} />
        <InfoRow label="Zone" value={camera.zone ?? "—"} />

        {camera.direction_deg != null && (
          <InfoRow
            label="Direction"
            value={`${camera.direction_deg}°`}
          />
        )}

        {camera.lat != null && camera.lng != null && (
          <InfoRow
            label="Coordinates"
            value={`${camera.lat.toFixed(4)}, ${camera.lng.toFixed(4)}`}
          />
        )}
      </div>
    </div>
  );
}

function InfoRow({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-slate-800/70 pb-2">
      <span className="text-xs text-slate-500">{label}</span>
      <span className="text-xs font-medium text-slate-300">{value}</span>
    </div>
  );
}

function Metric({
  label,
  value,
  emphasis,
}: {
  label: string;
  value: number;
  emphasis?: "online" | "degraded" | "offline";
}) {
  const valueClass =
    emphasis === "online"
      ? "text-emerald-300"
      : emphasis === "degraded"
        ? "text-amber-300"
        : emphasis === "offline"
          ? "text-red-300"
          : "text-white";

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
      <div className="text-xs uppercase tracking-wider text-slate-500">
        {label}
      </div>

      <div className={`mt-2 text-2xl font-bold ${valueClass}`}>
        {value}
      </div>
    </div>
  );
}

function normalizeStatus(status?: string) {
  const value = String(status ?? "unknown").toLowerCase();

  if (value === "healthy" || value === "active") return "online";

  return value;
}
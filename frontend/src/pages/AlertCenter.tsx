import { useEffect, useMemo, useState } from "react";

type Alert = {
  id?: string | number;
  severity?: string;
  category?: string;
  type?: string;
  message?: string;
  description?: string;
  status?: string;
  created_at?: string;
  timestamp?: string;
  road_id?: number;
  intersection_id?: number;
  camera_id?: string | number;
  vehicle_id?: string;
  confidence?: number;
  [key: string]: any;
};

export default function AlertCenter() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    loadAlerts();
  }, []);

  async function loadAlerts() {
    setLoading(true);
    setError("");

    try {
      const response = await fetch("/api/alerts");

      if (!response.ok) {
        throw new Error(`Alert API returned ${response.status}`);
      }

      const data = await response.json();
      setAlerts(data.items ?? data.alerts ?? []);
    } catch (err: any) {
      setAlerts([]);
      setError(err.message || "Unable to load alerts");
    } finally {
      setLoading(false);
    }
  }

  const counts = useMemo(
    () => ({
      total: alerts.length,
      high: alerts.filter((a) => severity(a) === "high").length,
      medium: alerts.filter((a) => severity(a) === "medium").length,
      low: alerts.filter((a) => severity(a) === "low").length,
    }),
    [alerts]
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-cyan-400">
            Part 5 · Operations
          </div>

          <h1 className="mt-2 text-3xl font-bold text-white">
            Alert Center
          </h1>

          <p className="mt-2 max-w-3xl text-sm text-slate-400">
            Centralized traffic, anomaly and operational alerts generated from
            the URBANTRACE intelligence pipeline.
          </p>
        </div>

        <button
          onClick={loadAlerts}
          disabled={loading}
          className="rounded-lg border border-slate-700 bg-slate-900 px-4 py-2 text-sm font-medium text-slate-300 transition hover:border-cyan-500/50 hover:text-white disabled:opacity-50"
        >
          {loading ? "Refreshing..." : "Refresh Alerts"}
        </button>
      </div>

      <div
        className={`rounded-xl border p-5 ${
          alerts.length === 0
            ? "border-emerald-500/20 bg-emerald-500/5"
            : "border-amber-500/20 bg-amber-500/5"
        }`}
      >
        <div className="flex items-center gap-4">
          <div
            className={`h-3 w-3 rounded-full ${
              alerts.length === 0 ? "bg-emerald-400" : "bg-amber-400"
            }`}
          />

          <div>
            <div
              className={`font-semibold ${
                alerts.length === 0
                  ? "text-emerald-300"
                  : "text-amber-300"
              }`}
            >
              {alerts.length === 0
                ? "No active alerts"
                : `${alerts.length} alert${
                    alerts.length === 1 ? "" : "s"
                  } detected`}
            </div>

            <div className="mt-1 text-sm text-slate-400">
              Alert state reflects the current URBANTRACE demonstration
              environment.
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Metric label="Total alerts" value={counts.total} />
        <Metric label="High severity" value={counts.high} emphasis="high" />
        <Metric
          label="Medium severity"
          value={counts.medium}
          emphasis="medium"
        />
        <Metric label="Low / Info" value={counts.low} />
      </div>

      {error && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-5">
          <div className="text-xs uppercase tracking-wider text-red-400">
            Alert Engine Error
          </div>

          <div className="mt-2 text-sm text-red-300">{error}</div>
        </div>
      )}

      <section className="rounded-xl border border-slate-800 bg-slate-900/70">
        <div className="border-b border-slate-800 p-6">
          <div className="text-xs uppercase tracking-wider text-slate-500">
            Operations Feed
          </div>

          <h2 className="mt-1 text-lg font-semibold text-white">
            Active Intelligence Events
          </h2>

          <p className="mt-1 text-xs text-slate-500">
            Alerts produced by anomaly, traffic and operational intelligence
            components.
          </p>
        </div>

        {loading ? (
          <div className="p-10 text-center text-sm text-slate-400">
            Loading alert intelligence...
          </div>
        ) : alerts.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="divide-y divide-slate-800">
            {alerts.map((alert, index) => (
              <AlertRow key={alert.id ?? index} alert={alert} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function AlertRow({ alert }: { alert: Alert }) {
  const level = severity(alert);

  const title =
    alert.message ??
    alert.description ??
    alert.type ??
    "Traffic event detected";

  const category = alert.category ?? alert.type ?? "Traffic Intelligence";

  const timestamp = alert.created_at ?? alert.timestamp;

  return (
    <div className="p-5 transition hover:bg-slate-950/40">
      <div className="flex items-start gap-4">
        <div
          className={`mt-1 h-9 w-1 shrink-0 rounded-full ${severityBar(level)}`}
        />

        <div className="min-w-0 flex-1">
          <div className="flex flex-col justify-between gap-3 md:flex-row">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs uppercase tracking-wider text-slate-500">
                  {category}
                </span>

                <SeverityBadge level={level} />
              </div>

              <div className="mt-2 font-semibold text-white">{title}</div>
            </div>

            <StatusBadge status={alert.status ?? "open"} />
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            {alert.road_id != null && (
              <InfoChip>
                Road R{String(alert.road_id).padStart(2, "0")}
              </InfoChip>
            )}

            {alert.intersection_id != null && (
              <InfoChip>
                Intersection I{String(alert.intersection_id).padStart(2, "0")}
              </InfoChip>
            )}

            {alert.camera_id != null && (
              <InfoChip>Camera {alert.camera_id}</InfoChip>
            )}

            {alert.confidence != null && (
              <InfoChip>
                Confidence {formatConfidence(alert.confidence)}
              </InfoChip>
            )}

            {timestamp && <InfoChip>{formatTime(timestamp)}</InfoChip>}
          </div>
        </div>
      </div>
    </div>
  );
}

function SeverityBadge({ level }: { level: string }) {
  const classes =
    level === "high"
      ? "border-red-500/20 bg-red-500/10 text-red-300"
      : level === "medium"
        ? "border-amber-500/20 bg-amber-500/10 text-amber-300"
        : level === "low"
          ? "border-cyan-500/20 bg-cyan-500/10 text-cyan-300"
          : "border-slate-700 bg-slate-800 text-slate-300";

  return (
    <span
      className={`rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase ${classes}`}
    >
      {level}
    </span>
  );
}

function StatusBadge({ status }: { status: string }) {
  const normalized = status.toLowerCase();

  const classes =
    normalized === "resolved" || normalized === "closed"
      ? "bg-emerald-500/10 text-emerald-300"
      : "bg-slate-800 text-slate-400";

  return (
    <span
      className={`rounded-full px-3 py-1 text-[10px] uppercase ${classes}`}
    >
      {status}
    </span>
  );
}

function InfoChip({ children }: { children: React.ReactNode }) {
  return (
    <span className="rounded-md border border-slate-800 bg-slate-950 px-2.5 py-1 text-[10px] text-slate-400">
      {children}
    </span>
  );
}

function EmptyState() {
  return (
    <div className="p-10 text-center">
      <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full border border-emerald-500/20 bg-emerald-500/5">
        <div className="h-3 w-3 rounded-full bg-emerald-400" />
      </div>

      <div className="mt-4 font-semibold text-emerald-300">
        Operational state clear
      </div>

      <div className="mx-auto mt-2 max-w-lg text-sm leading-6 text-slate-500">
        The alert engine has not detected a qualifying anomaly, traffic
        constraint, or operational event in the current demonstration data.
      </div>
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
  emphasis?: "high" | "medium";
}) {
  const valueClass =
    emphasis === "high"
      ? "text-red-300"
      : emphasis === "medium"
        ? "text-amber-300"
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

function severity(alert: Alert) {
  const value = String(alert.severity ?? "info").toLowerCase();

  if (value === "critical" || value === "high") return "high";
  if (value === "medium") return "medium";
  if (value === "low") return "low";

  return "info";
}

function severityBar(level: string) {
  if (level === "high") return "bg-red-400";
  if (level === "medium") return "bg-amber-400";
  if (level === "low") return "bg-cyan-400";
  return "bg-slate-600";
}

function formatConfidence(value: number) {
  const n = Number(value);

  if (!Number.isFinite(n)) return "—";

  return `${(n <= 1 ? n * 100 : n).toFixed(1)}%`;
}

function formatTime(value: string) {
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}
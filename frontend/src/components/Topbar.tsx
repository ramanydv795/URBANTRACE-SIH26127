import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type ConnState = "checking" | "connected" | "unreachable";

export default function Topbar({ title }: { title: string }) {
  const [state, setState] = useState<ConnState>("checking");

  useEffect(() => {
    let cancelled = false;
    const check = () => {
      api
        .health()
        .then(() => !cancelled && setState("connected"))
        .catch(() => !cancelled && setState("unreachable"));
    };
    check();
    const id = setInterval(check, 10000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  const dot =
    state === "connected"
      ? "bg-success"
      : state === "unreachable"
      ? "bg-danger"
      : "bg-warning";

  const label =
    state === "connected"
      ? "API connected"
      : state === "unreachable"
      ? "API unreachable"
      : "Checking API...";

  return (
    <header className="h-16 shrink-0 border-b border-border bg-surface flex items-center justify-between px-6">
      <h1 className="text-[16px] font-medium">{title}</h1>
      <div className="flex items-center gap-2 text-[13px] text-ink-muted">
        <span className={`inline-block w-2 h-2 rounded-full ${dot}`} />
        {label}
      </div>
    </header>
  );
}

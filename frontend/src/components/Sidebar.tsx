import { NavLink } from "react-router-dom";

const NAV_ITEMS = [
  { to: "/", label: "Command Center", end: true },
  { to: "/map", label: "Live Traffic Map" },
  { to: "/vehicle", label: "Vehicle Journey" },
  { to: "/explainer", label: "Trajectory Explainer" },
  { to: "/analytics", label: "Traffic Analytics" },
  { to: "/simulator", label: "What-If Simulator" },
  { to: "/alerts", label: "Alert Center" },
  { to: "/cameras", label: "Camera Health" },
  { to: "/replay", label: "Event Replay" },
];

export default function Sidebar() {
  return (
    <aside className="w-60 shrink-0 border-r border-border bg-surface flex flex-col">
      <div className="h-16 flex items-center px-5 border-b border-border">
        <span className="font-semibold text-[15px] tracking-tight">URBANTRACE</span>
      </div>
      <nav className="flex-1 overflow-y-auto py-3">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) =>
              [
                "flex items-center mx-2 mb-0.5 px-3 py-2 rounded-md text-[14px] transition-colors",
                isActive
                  ? "bg-accent-soft text-accent-strong font-medium"
                  : "text-ink-muted hover:bg-surface-2 hover:text-ink",
              ].join(" ")
            }
          >
            {item.label}
          </NavLink>
        ))}
      </nav>
      <div className="px-5 py-4 border-t border-border text-[12px] text-ink-muted">
        Demo City · SIH26127
      </div>
    </aside>
  );
}

import { Outlet, useLocation } from "react-router-dom";
import Sidebar from "./Sidebar";
import Topbar from "./Topbar";

const pageTitles: Record<string, string> = {
  "/": "Command Center",
  "/map": "Live Traffic Map",
  "/vehicle": "Vehicle Journey",
  "/explainer": "Trajectory Explainer",
  "/analytics": "Traffic Analytics",
  "/simulator": "What-If Simulator",
  "/alerts": "Alert Center",
  "/cameras": "Camera Health",
  "/replay": "Event Replay",
};

export default function Layout() {
  const location = useLocation();
  const title = pageTitles[location.pathname] ?? "URBANTRACE";

  return (
    <div className="flex h-screen w-screen overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <Topbar title={title} />
        <main className="flex-1 overflow-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
import { Route, Routes } from "react-router-dom";
import Layout from "@/components/Layout";
import CommandCenter from "@/pages/CommandCenter";
import LiveMap from "@/pages/LiveMap";
import VehicleJourney from "@/pages/VehicleJourney";
import TrajectoryExplainer from "@/pages/TrajectoryExplainer";
import TrafficAnalytics from "@/pages/TrafficAnalytics";
import WhatIfSimulator from "@/pages/WhatIfSimulator";
import AlertCenter from "@/pages/AlertCenter";
import CameraHealth from "@/pages/CameraHealth";
import EventReplay from "@/pages/EventReplay";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<CommandCenter />} handle={{ title: "Command Center" }} />
        <Route path="map" element={<LiveMap />} handle={{ title: "Live Traffic Map" }} />
        <Route path="vehicle" element={<VehicleJourney />} handle={{ title: "Vehicle Journey" }} />
        <Route
          path="explainer"
          element={<TrajectoryExplainer />}
          handle={{ title: "Trajectory Explainer" }}
        />
        <Route
          path="analytics"
          element={<TrafficAnalytics />}
          handle={{ title: "Traffic Analytics" }}
        />
        <Route
          path="simulator"
          element={<WhatIfSimulator />}
          handle={{ title: "What-If Simulator" }}
        />
        <Route path="alerts" element={<AlertCenter />} handle={{ title: "Alert Center" }} />
        <Route path="cameras" element={<CameraHealth />} handle={{ title: "Camera Health" }} />
        <Route path="replay" element={<EventReplay />} handle={{ title: "Event Replay" }} />
      </Route>
    </Routes>
  );
}

import React from "react";
import { PredictiveDriftRadarPanel } from "../../components/PredictiveDriftRadarPanel";

export const metadata = {
  title: "Predictive Drift Radar | Nodal Sentinel",
  description: "Continuous anomaly drift detection and predictive stability monitoring.",
};

export default function DriftRadarPage() {
  return (
    <div className="space-y-6">
      <PredictiveDriftRadarPanel />
    </div>
  );
}

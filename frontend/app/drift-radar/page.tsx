import React from "react";
import { PredictiveDriftRadarPanel } from "../../components/PredictiveDriftRadarPanel";

export const metadata = {
  title: "Predictive Drift Radar | Nodexa",
  description: "Continuous anomaly drift detection and predictive stability monitoring.",
};

export default function DriftRadarPage() {
  return (
    <div className="space-y-6">
      <div className="pb-1">
        <h1 className="text-3xl sm:text-4xl font-bold text-slate-900 tracking-tight">
          Predictive Drift Radar
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          Continuous anomaly drift detection and predictive stability monitoring
        </p>
      </div>

      <PredictiveDriftRadarPanel />
    </div>
  );
}

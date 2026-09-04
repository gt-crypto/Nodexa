import React from "react";
import { EvaluationDashboard } from "../../components/EvaluationDashboard";
import { ConfidenceCalibrationPanel } from "../../components/ConfidenceCalibrationPanel";

export const metadata = {
  title: "Benchmark & Accuracy Evaluation | Nodexa",
  description: "Comprehensive benchmark suite, operational accuracy rates, and confidence calibration.",
};

export default function BenchmarkPage() {
  return (
    <div className="space-y-10">
      {/* Benchmark Evaluation Dashboard */}
      <EvaluationDashboard />

      {/* Confidence Calibration Dashboard */}
      <ConfidenceCalibrationPanel />
    </div>
  );
}

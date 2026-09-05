import React from "react";
import { PatternMinerPanel } from "../../components/PatternMinerPanel";

export const metadata = {
  title: "Pattern Miner | Nodexa",
  description: "Deterministic exception clustering and pattern miner for nodal reconciliation.",
};

export default function PatternsPage() {
  return (
    <div className="space-y-6">
      <div className="pb-1">
        <h1 className="text-3xl sm:text-4xl font-bold text-slate-900 tracking-tight">
          Pattern Miner
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          AI-driven anomaly family and pattern analysis for nodal reconciliation
        </p>
      </div>

      <PatternMinerPanel />
    </div>
  );
}

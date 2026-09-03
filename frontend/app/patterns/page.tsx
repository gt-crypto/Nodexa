import React from "react";
import { PatternMinerPanel } from "../../components/PatternMinerPanel";

export const metadata = {
  title: "Pattern Miner | Nodal Sentinel",
  description: "Deterministic exception clustering and pattern miner for nodal reconciliation.",
};

export default function PatternsPage() {
  return (
    <div className="space-y-6">
      <div className="pb-2">
        <h1 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">
          Pattern Miner
        </h1>
        <p className="text-sm text-slate-400 mt-1">
          AI-driven anomaly family and pattern analysis
        </p>
      </div>

      <PatternMinerPanel />
    </div>
  );
}

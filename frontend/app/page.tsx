import React from "react";
import { SystemStatus } from "../components/SystemStatus";
import { BusinessImpactTile } from "../components/BusinessImpactTile";
import { Cpu, Database, Lock } from "lucide-react";

export default function Home() {
  return (
    <div className="space-y-6">
      {/* Compact Hero Section (Issue 4) */}
      <div className="text-center py-4 sm:py-6 relative">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-teal-500/10 border border-teal-500/30 text-teal-300 text-xs font-mono mb-3 sentinel-glow">
          <span className="flex h-2 w-2 rounded-full bg-teal-400"></span>
          <span>Foundation Architecture Active</span>
        </div>

        <h1 className="text-2xl sm:text-4xl font-extrabold tracking-tight text-white mb-2">
          Nodal <span className="text-transparent bg-clip-text bg-gradient-to-r from-teal-400 via-cyan-300 to-emerald-400">Sentinel</span>
        </h1>

        <p className="text-sm sm:text-base text-slate-300 max-w-xl mx-auto font-medium mb-2">
          AI Finance Controller for Nodal Account Health
        </p>

        <p className="text-xs sm:text-sm text-slate-400 max-w-xl mx-auto mb-4 leading-relaxed">
          Strict separation between deterministic financial control (balance arithmetic, double-entry verification, reconciliation, SLA invariants) and AI-driven investigation.
        </p>

        <div className="flex flex-wrap items-center justify-center gap-2.5 text-xs font-mono">
          <div
            className="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-slate-900/80 border border-slate-800 text-slate-300"
            title="AI agents can inspect evidence but cannot modify financial records."
          >
            <Lock className="w-3.5 h-3.5 text-teal-400" />
            <span>Read-only AI Access</span>
          </div>
          <div className="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-slate-900/80 border border-slate-800 text-slate-300">
            <Cpu className="w-3.5 h-3.5 text-cyan-400" />
            <span>Deterministic Core</span>
          </div>
          <div className="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-slate-900/80 border border-slate-800 text-slate-300">
            <Database className="w-3.5 h-3.5 text-purple-400" />
            <span>Synthetic Invariants</span>
          </div>
        </div>
      </div>

      {/* Live Controller Status */}
      <SystemStatus />

      {/* Tier-2 Business Impact & Deterministic ROI Tile */}
      <BusinessImpactTile />
    </div>
  );
}

import React from "react";
import { SystemStatus } from "../components/SystemStatus";
import { BusinessImpactTile } from "../components/BusinessImpactTile";
import { Cpu, Database, Lock } from "lucide-react";

export default function Home() {
  return (
    <div className="space-y-10">
      {/* Hero Section */}
      <div className="text-center py-8 sm:py-12 relative">
        <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-teal-500/10 border border-teal-500/30 text-teal-300 text-xs font-mono mb-5 sentinel-glow">
          <span className="flex h-2 w-2 rounded-full bg-teal-400"></span>
          Foundation Architecture Active
        </div>

        <h1 className="text-3xl sm:text-5xl font-extrabold tracking-tight text-white mb-3">
          Nodal <span className="text-transparent bg-clip-text bg-gradient-to-r from-teal-400 via-cyan-300 to-emerald-400">Sentinel</span>
        </h1>

        <p className="text-base sm:text-lg text-slate-300 max-w-2xl mx-auto font-medium mb-3">
          AI Finance Controller for Nodal Account Health
        </p>

        <p className="text-xs sm:text-sm text-slate-400 max-w-2xl mx-auto mb-6 leading-relaxed">
          Strict separation between deterministic financial control (balance arithmetic, double-entry verification, reconciliation, SLA invariants) and AI-driven investigation.
        </p>

        <div className="flex flex-wrap items-center justify-center gap-3 text-xs font-mono">
          <div
            className="flex items-center gap-2 px-3.5 py-1.5 rounded-lg bg-slate-900/80 border border-slate-800 text-slate-300"
            title="AI agents can inspect evidence but cannot modify financial records."
          >
            <Lock className="w-4 h-4 text-teal-400" />
            <span>Read-only AI Access</span>
          </div>
          <div className="flex items-center gap-2 px-3.5 py-1.5 rounded-lg bg-slate-900/80 border border-slate-800 text-slate-300">
            <Cpu className="w-4 h-4 text-cyan-400" />
            <span>Deterministic Core</span>
          </div>
          <div className="flex items-center gap-2 px-3.5 py-1.5 rounded-lg bg-slate-900/80 border border-slate-800 text-slate-300">
            <Database className="w-4 h-4 text-purple-400" />
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

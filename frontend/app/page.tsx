import React from "react";
import { SystemStatus } from "../components/SystemStatus";
import { BusinessImpactTile } from "../components/BusinessImpactTile";
import { Cpu, Database, Lock, ShieldCheck, Terminal } from "lucide-react";

export default function Home() {
  return (
    <div className="space-y-6">
      {/* Executive Financial Control Center Header */}
      <div className="border-b border-slate-800/80 pb-5">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded bg-sky-950/40 border border-sky-800/40 text-sky-300 text-xs font-medium font-sans tracking-wide mb-2">
              <span className="flex h-1.5 w-1.5 rounded-full bg-sky-400 animate-pulse" />
              <span>DETERMINISTIC CONTROL ENGINE &bull; MAINNET</span>
            </div>

            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-white font-sans">
              Financial Operations &amp; Risk Controller
            </h1>

            <p className="text-xs sm:text-sm text-slate-400 mt-1 max-w-2xl leading-relaxed font-sans">
              Strict mathematical separation between deterministic financial control (double-entry verification, balance arithmetic, settlement SLAs) and AI-driven investigation.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2 text-xs font-sans shrink-0">
            <div
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-[#0d121d] border border-slate-800 text-slate-300 text-xs font-medium"
              title="AI agents can inspect evidence but cannot modify financial records."
            >
              <Lock className="w-3 h-3 text-sky-400" />
              <span>Read-only AI Boundary</span>
            </div>
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-[#0d121d] border border-slate-800 text-slate-300 text-xs font-medium">
              <Cpu className="w-3 h-3 text-sky-400" />
              <span>Deterministic Core</span>
            </div>
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-[#0d121d] border border-slate-800 text-slate-300 text-xs font-medium">
              <Database className="w-3 h-3 text-sky-400" />
              <span>Integer Minor Units</span>
            </div>
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

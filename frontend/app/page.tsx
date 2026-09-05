import React from "react";
import { SystemStatus } from "../components/SystemStatus";
import { BusinessImpactTile } from "../components/BusinessImpactTile";
import { Cpu, Database, Lock } from "lucide-react";

export default function Home() {
  return (
    <div className="space-y-6">
      {/* Executive Financial Control Center Header */}
      <div className="border-b border-slate-200 pb-5">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded bg-indigo-50 border border-indigo-200 text-indigo-700 text-xs font-medium font-sans tracking-wide mb-2">
              <span className="flex h-1.5 w-1.5 rounded-full bg-indigo-500" />
              <span>DETERMINISTIC CONTROL ENGINE &bull; MAINNET</span>
            </div>

            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900 font-sans">
              Financial Operations &amp; Risk Controller
            </h1>

            <p className="text-xs sm:text-sm text-slate-500 mt-1 max-w-2xl leading-relaxed font-sans">
              Strict mathematical separation between deterministic financial control (double-entry verification, balance arithmetic, settlement SLAs) and AI-driven investigation.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2 text-xs font-sans shrink-0">
            <div
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-white border border-slate-200 text-slate-700 text-xs font-medium shadow-xs"
              title="AI agents can inspect evidence but cannot modify financial records."
            >
              <Lock className="w-3 h-3 text-indigo-600" />
              <span>Read-only AI Boundary</span>
            </div>
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-white border border-slate-200 text-slate-700 text-xs font-medium shadow-xs">
              <Cpu className="w-3 h-3 text-indigo-600" />
              <span>Deterministic Core</span>
            </div>
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-white border border-slate-200 text-slate-700 text-xs font-medium shadow-xs">
              <Database className="w-3 h-3 text-indigo-600" />
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

import React from "react";
import { ControlLoop } from "../../components/ControlLoop";
import { LayerArchitecture } from "../../components/LayerArchitecture";
import { ShieldCheck, CheckCircle, Lock, Cpu, Database } from "lucide-react";

export const metadata = {
  title: "Architecture & Control Loop | Nodexa",
  description: "11-stage autonomous control cycle and 9-layer architectural isolation specification.",
};

export default function ArchitecturePage() {
  return (
    <div className="space-y-12">
      {/* Header Banner */}
      <div className="bg-white p-6 sm:p-8 rounded-2xl border border-slate-200 shadow-xs">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-50 border border-indigo-200 text-indigo-700 text-xs font-mono font-semibold mb-4">
          <Lock className="w-3.5 h-3.5 text-indigo-600" />
          <span>Autonomous Control Specification</span>
        </div>
        <h1 className="text-2xl sm:text-4xl font-bold text-slate-900 tracking-tight">
          System Architecture & Control Loop
        </h1>
        <p className="mt-2 text-sm sm:text-base text-slate-500 max-w-3xl leading-relaxed">
          Nodexa enforces strict separation between deterministic financial control (balance arithmetic, double-entry verification, reconciliation, SLA invariants) and AI-driven investigation.
        </p>

        <div className="mt-6 flex flex-wrap gap-4 text-xs font-mono">
          <div
            className="flex items-center gap-2 px-3.5 py-1.5 rounded-lg bg-slate-50 border border-slate-200 text-slate-700 shadow-2xs"
            title="AI agents can inspect evidence but cannot modify financial records."
          >
            <Lock className="w-4 h-4 text-indigo-600" />
            <span>Read-only AI Access</span>
          </div>
          <div className="flex items-center gap-2 px-3.5 py-1.5 rounded-lg bg-slate-50 border border-slate-200 text-slate-700 shadow-2xs">
            <Cpu className="w-4 h-4 text-cyan-600" />
            <span>Deterministic Core</span>
          </div>
          <div className="flex items-center gap-2 px-3.5 py-1.5 rounded-lg bg-slate-50 border border-slate-200 text-slate-700 shadow-2xs">
            <Database className="w-4 h-4 text-indigo-600" />
            <span>Synthetic Financial Invariants</span>
          </div>
        </div>
      </div>

      {/* 11-Stage Control Loop */}
      <ControlLoop />

      {/* 9-Layer Separation of Concerns */}
      <LayerArchitecture />

      {/* Core Safety & Control Guarantees */}
      <section id="safety-guarantees" className="py-6 border-t border-slate-200">
        <div className="bg-white rounded-2xl p-6 sm:p-8 border border-slate-200 shadow-xs relative overflow-hidden">
          <h2 className="text-xl sm:text-2xl font-bold text-slate-900 mb-6 flex items-center gap-2.5">
            <ShieldCheck className="w-6 h-6 text-indigo-600" />
            <span>Core Safety & Control Guarantees</span>
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm text-slate-700">
            <div className="flex items-start gap-3 p-4 rounded-xl bg-slate-50 border border-slate-200">
              <CheckCircle className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
              <div>
                <h3 className="font-bold text-slate-900 mb-1 text-base">Deterministic financial arithmetic</h3>
                <p className="text-xs text-slate-500 leading-relaxed">All monetary calculations, reconciliations, and balance updates are computed deterministically without LLM intervention.</p>
              </div>
            </div>

            <div className="flex items-start gap-3 p-4 rounded-xl bg-slate-50 border border-slate-200">
              <CheckCircle className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
              <div>
                <h3 className="font-bold text-slate-900 mb-1 text-base">Zero mutation rights for AI</h3>
                <p className="text-xs text-slate-500 leading-relaxed">The AI investigator operates in a read-only sandbox. It can analyze and propose, but cannot execute financial state mutations directly.</p>
              </div>
            </div>

            <div className="flex items-start gap-3 p-4 rounded-xl bg-slate-50 border border-slate-200">
              <CheckCircle className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
              <div>
                <h3 className="font-bold text-slate-900 mb-1 text-base">Double-entry verification gate</h3>
                <p className="text-xs text-slate-500 leading-relaxed">Any remediation step must pass automated double-entry verification and invariant checks prior to transaction commit.</p>
              </div>
            </div>

            <div className="flex items-start gap-3 p-4 rounded-xl bg-slate-50 border border-slate-200">
              <CheckCircle className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
              <div>
                <h3 className="font-bold text-slate-900 mb-1 text-base">Immutable audit trail</h3>
                <p className="text-xs text-slate-400 leading-relaxed">Every anomaly detection, AI reasoning trace, policy decision, and verification check is logged to an immutable audit record.</p>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

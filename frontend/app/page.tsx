import React from "react";
import { Navbar } from "../components/Navbar";
import { SystemStatus } from "../components/SystemStatus";
import { AskSentinelPanel } from "../components/AskSentinelPanel";
import { LiveInjectionConsole } from "../components/LiveInjectionConsole";
import { ControlLoop } from "../components/ControlLoop";
import { LayerArchitecture } from "../components/LayerArchitecture";
import { VerificationPanel } from "../components/VerificationPanel";
import { EvaluationDashboard } from "../components/EvaluationDashboard";
import { ShieldCheck, Cpu, Database, Terminal, ArrowUpRight, Lock, CheckCircle } from "lucide-react";

export default function Home() {
  return (
    <div className="min-h-screen flex flex-col bg-grid-pattern">
      <Navbar />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-12">
        {/* Hero Section */}
        <div className="text-center py-12 sm:py-16 relative">
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-teal-500/10 border border-teal-500/30 text-teal-300 text-xs font-mono mb-6 sentinel-glow">
            <span className="flex h-2 w-2 rounded-full bg-teal-400"></span>
            Foundation Architecture Active
          </div>

          <h1 className="text-4xl sm:text-6xl font-extrabold tracking-tight text-white mb-4">
            Nodal <span className="text-transparent bg-clip-text bg-gradient-to-r from-teal-400 via-cyan-300 to-emerald-400">Sentinel</span>
          </h1>

          <p className="text-lg sm:text-xl text-slate-300 max-w-3xl mx-auto font-medium mb-4">
            AI Finance Controller for Nodal Account Health
          </p>

          <p className="text-sm text-slate-400 max-w-2xl mx-auto mb-8 leading-relaxed">
            Strict separation between deterministic financial control (balance arithmetic, double-entry verification, reconciliation, SLA invariants) and AI-driven investigation (root-cause reasoning, temporal trace analysis, explanation synthesis).
          </p>

          <div className="flex flex-wrap items-center justify-center gap-4 text-xs font-mono">
            <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-slate-900/80 border border-slate-800 text-slate-300">
              <Lock className="w-4 h-4 text-teal-400" />
              <span>Zero LLM Mutation Rights</span>
            </div>
            <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-slate-900/80 border border-slate-800 text-slate-300">
              <Cpu className="w-4 h-4 text-cyan-400" />
              <span>Deterministic Core</span>
            </div>
            <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-slate-900/80 border border-slate-800 text-slate-300">
              <Database className="w-4 h-4 text-purple-400" />
              <span>Synthetic Financial Invariants</span>
            </div>
          </div>
        </div>

        {/* Live Controller Status */}
        <SystemStatus />

        {/* v2.0: Ask Sentinel Grounded Operational Copilot */}
        <AskSentinelPanel />

        {/* v2.0: Live Digital-Twin Injection Console */}
        <LiveInjectionConsole />

        {/* Benchmark Evaluation & Precision/Recall Engine */}
        <EvaluationDashboard />

        {/* Post-Remediation Verification Engine Panel */}
        <VerificationPanel />

        {/* 11-Stage Control Loop */}
        <ControlLoop />

        {/* 9-Layer Separation */}
        <LayerArchitecture />

        {/* Safety Principles Section */}
        <section className="py-12 border-t border-slate-800/80 mb-12">
          <div className="glass-panel rounded-2xl p-8 border border-slate-800/80 relative overflow-hidden">
            <h3 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
              <ShieldCheck className="w-6 h-6 text-teal-400" />
              Core Safety & Control Guarantees
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm text-slate-300">
              <div className="flex items-start gap-3 p-4 rounded-xl bg-slate-900/40 border border-slate-800/60">
                <CheckCircle className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
                <div>
                  <h4 className="font-semibold text-white mb-1">Deterministic Financial Arithmetic</h4>
                  <p className="text-xs text-slate-400">All monetary calculations, reconciliations, and balance updates are computed deterministically without LLM intervention.</p>
                </div>
              </div>

              <div className="flex items-start gap-3 p-4 rounded-xl bg-slate-900/40 border border-slate-800/60">
                <CheckCircle className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
                <div>
                  <h4 className="font-semibold text-white mb-1">Bounded AI Investigation</h4>
                  <p className="text-xs text-slate-400">The AI agent reasons via read-only inspection tools and recommends actions subject to policy approval.</p>
                </div>
              </div>

              <div className="flex items-start gap-3 p-4 rounded-xl bg-slate-900/40 border border-slate-800/60">
                <CheckCircle className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
                <div>
                  <h4 className="font-semibold text-white mb-1">Post-Action Invariant Verification</h4>
                  <p className="text-xs text-slate-400">Any remediation step must pass automated double-entry verification and invariant checks prior to transaction commit.</p>
                </div>
              </div>

              <div className="flex items-start gap-3 p-4 rounded-xl bg-slate-900/40 border border-slate-800/60">
                <CheckCircle className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
                <div>
                  <h4 className="font-semibold text-white mb-1">Immutable Audit Trail</h4>
                  <p className="text-xs text-slate-400">Every anomaly detection, AI reasoning trace, policy decision, and verification check is logged to an immutable audit record.</p>
                </div>
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-900 glass-panel py-6 text-center text-xs text-slate-500 font-mono">
        <p>Nodal Sentinel &copy; 2026 &mdash; Autonomous AI Finance Controller Architecture</p>
      </footer>
    </div>
  );
}

import React from "react";
import {
  Eye,
  AlertTriangle,
  RotateCcw,
  Search,
  FileText,
  DollarSign,
  Layers,
  CheckCircle2,
  Send,
  ShieldCheck,
  History,
  ArrowRight,
} from "lucide-react";

interface Step {
  title: string;
  category: "Deterministic" | "AI Reasoning" | "Safety / Policy" | "Audit";
  desc: string;
  icon: React.ComponentType<{ className?: string }>;
  color: string;
}

const steps: Step[] = [
  {
    title: "1. MONITOR",
    category: "Deterministic",
    desc: "Ingests continuous balance feeds, settlement timers, and account activity.",
    icon: Eye,
    color: "from-blue-500/20 to-blue-500/5 border-blue-500/30 text-blue-400",
  },
  {
    title: "2. DETECT",
    category: "Deterministic",
    desc: "Flags invariant violations, SLA breaches, and unaligned ledger postings.",
    icon: AlertTriangle,
    color: "from-amber-500/20 to-amber-500/5 border-amber-500/30 text-amber-400",
  },
  {
    title: "3. RECONSTRUCT",
    category: "Deterministic",
    desc: "Rebuilds timeline of ledger entries, gateway logs, and settlement snapshots.",
    icon: RotateCcw,
    color: "from-blue-500/20 to-blue-500/5 border-blue-500/30 text-blue-400",
  },
  {
    title: "4. INVESTIGATE",
    category: "AI Reasoning",
    desc: "Explores root causes across multiple data sources using controlled tools.",
    icon: Search,
    color: "from-purple-500/20 to-purple-500/5 border-purple-500/30 text-purple-400",
  },
  {
    title: "5. EXPLAIN",
    category: "AI Reasoning",
    desc: "Generates clear, evidence-backed explanations and causal hypothesis.",
    icon: FileText,
    color: "from-purple-500/20 to-purple-500/5 border-purple-500/30 text-purple-400",
  },
  {
    title: "6. QUANTIFY",
    category: "Deterministic",
    desc: "Calculates precise financial exposure and double-entry discrepancies.",
    icon: DollarSign,
    color: "from-blue-500/20 to-blue-500/5 border-blue-500/30 text-blue-400",
  },
  {
    title: "7. PRIORITIZE",
    category: "Deterministic",
    desc: "Ranks exceptions by financial risk, SLA urgency, and impact threshold.",
    icon: Layers,
    color: "from-blue-500/20 to-blue-500/5 border-blue-500/30 text-blue-400",
  },
  {
    title: "8. DECIDE",
    category: "Safety / Policy",
    desc: "Evaluates policy boundaries to approve auto-action or trigger human review.",
    icon: CheckCircle2,
    color: "from-emerald-500/20 to-emerald-500/5 border-emerald-500/30 text-emerald-400",
  },
  {
    title: "9. RESOLVE / ESCALATE",
    category: "Safety / Policy",
    desc: "Executes verified remediation or routes full dossier to finance ops.",
    icon: Send,
    color: "from-emerald-500/20 to-emerald-500/5 border-emerald-500/30 text-emerald-400",
  },
  {
    title: "10. VERIFY",
    category: "Deterministic",
    desc: "Asserts zero-balance invariants and double-entry validity post-action.",
    icon: ShieldCheck,
    color: "from-blue-500/20 to-blue-500/5 border-blue-500/30 text-blue-400",
  },
  {
    title: "11. AUDIT",
    category: "Audit",
    desc: "Records immutable cryptographic audit trail of all detections & decisions.",
    icon: History,
    color: "from-teal-500/20 to-teal-500/5 border-teal-500/30 text-teal-400",
  },
];

export const ControlLoop: React.FC = () => {
  return (
    <section id="control-loop" className="py-12">
      <div className="text-center max-w-3xl mx-auto mb-10">
        <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-white">
          Architectural Control Loop
        </h2>
        <p className="mt-3 text-slate-400 text-sm sm:text-base">
          A disciplined, 11-stage autonomous control cycle ensuring nodal accounts remain balanced, verified, and continuously compliant.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {steps.map((step, idx) => {
          const Icon = step.icon;
          return (
            <div
              key={step.title}
              className="glass-panel glass-panel-hover rounded-xl p-5 border border-slate-800/80 relative flex flex-col justify-between"
            >
              <div>
                <div className="flex items-center justify-between mb-3">
                  <div className={`p-2.5 rounded-lg border bg-gradient-to-b ${step.color}`}>
                    <Icon className="w-5 h-5" />
                  </div>
                  <span className="text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded border border-slate-700/60 bg-slate-800/50 text-slate-300">
                    {step.category}
                  </span>
                </div>
                <h3 className="font-semibold text-white text-base mb-1.5 font-mono">
                  {step.title}
                </h3>
                <p className="text-xs text-slate-400 leading-relaxed">
                  {step.desc}
                </p>
              </div>

              {idx < steps.length - 1 && (
                <div className="mt-4 pt-3 border-t border-slate-800/40 flex items-center justify-end text-slate-600 text-xs font-mono">
                  <span>Next stage</span>
                  <ArrowRight className="w-3 h-3 ml-1" />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
};

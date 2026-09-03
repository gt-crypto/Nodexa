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
  Activity,
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
    title: "1. Monitor",
    category: "Deterministic",
    desc: "Ingests continuous balance feeds, settlement timers, and account activity.",
    icon: Eye,
    color: "from-blue-500/20 to-blue-500/5 border-blue-500/30 text-blue-400",
  },
  {
    title: "2. Detect",
    category: "Deterministic",
    desc: "Flags invariant violations, SLA breaches, and unaligned ledger postings.",
    icon: AlertTriangle,
    color: "from-amber-500/20 to-amber-500/5 border-amber-500/30 text-amber-400",
  },
  {
    title: "3. Reconstruct",
    category: "Deterministic",
    desc: "Rebuilds timeline of ledger entries, gateway logs, and settlement snapshots.",
    icon: RotateCcw,
    color: "from-blue-500/20 to-blue-500/5 border-blue-500/30 text-blue-400",
  },
  {
    title: "4. Investigate",
    category: "AI Reasoning",
    desc: "Explores root causes across multiple data sources using controlled read-only tools.",
    icon: Search,
    color: "from-purple-500/20 to-purple-500/5 border-purple-500/30 text-purple-400",
  },
  {
    title: "5. Explain",
    category: "AI Reasoning",
    desc: "Generates clear, evidence-backed explanations and causal hypotheses.",
    icon: FileText,
    color: "from-purple-500/20 to-purple-500/5 border-purple-500/30 text-purple-400",
  },
  {
    title: "6. Quantify",
    category: "Deterministic",
    desc: "Calculates precise financial exposure and double-entry discrepancies.",
    icon: DollarSign,
    color: "from-blue-500/20 to-blue-500/5 border-blue-500/30 text-blue-400",
  },
  {
    title: "7. Prioritize",
    category: "Deterministic",
    desc: "Ranks exceptions by financial risk, SLA urgency, and impact threshold.",
    icon: Layers,
    color: "from-blue-500/20 to-blue-500/5 border-blue-500/30 text-blue-400",
  },
  {
    title: "8. Decide",
    category: "Safety / Policy",
    desc: "Evaluates policy boundaries to approve auto-action or trigger human review.",
    icon: CheckCircle2,
    color: "from-emerald-500/20 to-emerald-500/5 border-emerald-500/30 text-emerald-400",
  },
  {
    title: "9. Resolve / Escalate",
    category: "Safety / Policy",
    desc: "Executes verified remediation or routes full dossier to finance operations.",
    icon: Send,
    color: "from-emerald-500/20 to-emerald-500/5 border-emerald-500/30 text-emerald-400",
  },
  {
    title: "10. Verify",
    category: "Deterministic",
    desc: "Asserts zero-balance invariants and double-entry validity post-action.",
    icon: ShieldCheck,
    color: "from-blue-500/20 to-blue-500/5 border-blue-500/30 text-blue-400",
  },
  {
    title: "11. Audit",
    category: "Audit",
    desc: "Records immutable cryptographic audit trail of all detections & decisions.",
    icon: History,
    color: "from-teal-500/20 to-teal-500/5 border-teal-500/30 text-teal-400",
  },
];

export const ControlLoop: React.FC = () => {
  const renderCard = (step: Step, idx: number) => {
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
            <span className="text-xs font-mono px-2 py-0.5 rounded border border-slate-700/60 bg-slate-800/60 text-slate-300 font-medium">
              {step.category}
            </span>
          </div>
          <h3 className="font-semibold text-white text-base mb-1.5 font-mono tracking-tight">
            {step.title}
          </h3>
          <p className="text-sm text-slate-400 leading-relaxed">
            {step.desc}
          </p>
        </div>

        {idx < steps.length - 1 && (
          <div className="mt-4 pt-3 border-t border-slate-800/60 flex items-center justify-end text-slate-500 text-xs font-mono">
            <span>Next stage</span>
            <ArrowRight className="w-3.5 h-3.5 ml-1 text-slate-400" />
          </div>
        )}
      </div>
    );
  };

  return (
    <section id="control-loop" className="py-12 border-t border-slate-800/80">
      <div className="text-center max-w-3xl mx-auto mb-10">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-500/10 border border-blue-500/30 text-blue-300 text-xs font-mono mb-3">
          <Activity className="w-3.5 h-3.5 text-blue-400" />
          <span>Core Operational Lifecycle</span>
        </div>
        <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-white">
          Architectural Control Loop
        </h2>
        <p className="mt-3 text-slate-400 text-sm sm:text-base leading-relaxed">
          A disciplined, 11-stage autonomous control cycle ensuring nodal accounts remain balanced, verified, and continuously compliant.
        </p>
      </div>

      {/* Balanced 3-Column Responsive Grid (Issue 5: Rows 1-3 have 3 items; Row 4 has 2 centered items) */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {steps.slice(0, 9).map((step, idx) => renderCard(step, idx))}
      </div>

      {/* Row 4: Final two cards centered */}
      <div className="mt-5 flex flex-col md:flex-row justify-center gap-5">
        <div className="w-full md:w-[calc(50%-10px)] lg:w-[calc(33.333%-14px)]">
          {renderCard(steps[9], 9)}
        </div>
        <div className="w-full md:w-[calc(50%-10px)] lg:w-[calc(33.333%-14px)]">
          {renderCard(steps[10], 10)}
        </div>
      </div>
    </section>
  );
};

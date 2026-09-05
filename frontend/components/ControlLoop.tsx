"use client";

import React, { useState } from "react";
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
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { Button } from "./ui/Button";

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
    color: "border-indigo-200 bg-indigo-50 text-indigo-600",
  },
  {
    title: "2. Detect",
    category: "Deterministic",
    desc: "Flags invariant violations, SLA breaches, and unaligned ledger postings.",
    icon: AlertTriangle,
    color: "border-amber-200 bg-amber-50 text-amber-600",
  },
  {
    title: "3. Reconstruct",
    category: "Deterministic",
    desc: "Rebuilds timeline of ledger entries, gateway logs, and settlement snapshots.",
    icon: RotateCcw,
    color: "border-indigo-200 bg-indigo-50 text-indigo-600",
  },
  {
    title: "4. Investigate",
    category: "AI Reasoning",
    desc: "Explores root causes across multiple data sources using controlled read-only tools.",
    icon: Search,
    color: "border-indigo-200 bg-indigo-50 text-indigo-600",
  },
  {
    title: "5. Explain",
    category: "AI Reasoning",
    desc: "Generates clear, evidence-backed explanations and causal hypotheses.",
    icon: FileText,
    color: "border-indigo-200 bg-indigo-50 text-indigo-600",
  },
  {
    title: "6. Quantify",
    category: "Deterministic",
    desc: "Calculates precise financial exposure and double-entry discrepancies.",
    icon: DollarSign,
    color: "border-indigo-200 bg-indigo-50 text-indigo-600",
  },
  {
    title: "7. Prioritize",
    category: "Deterministic",
    desc: "Ranks exceptions by financial risk, SLA urgency, and impact threshold.",
    icon: Layers,
    color: "border-indigo-200 bg-indigo-50 text-indigo-600",
  },
  {
    title: "8. Decide",
    category: "Safety / Policy",
    desc: "Evaluates policy boundaries to approve auto-action or trigger human review.",
    icon: CheckCircle2,
    color: "border-emerald-200 bg-emerald-50 text-emerald-600",
  },
  {
    title: "9. Resolve / Escalate",
    category: "Safety / Policy",
    desc: "Executes verified remediation or routes full dossier to finance operations.",
    icon: Send,
    color: "border-emerald-200 bg-emerald-50 text-emerald-600",
  },
  {
    title: "10. Verify",
    category: "Deterministic",
    desc: "Asserts zero-balance invariants and double-entry validity post-action.",
    icon: ShieldCheck,
    color: "border-indigo-200 bg-indigo-50 text-indigo-600",
  },
  {
    title: "11. Audit",
    category: "Audit",
    desc: "Records immutable cryptographic audit trail of all detections & decisions.",
    icon: History,
    color: "border-teal-200 bg-teal-50 text-teal-600",
  },
];

export const ControlLoop: React.FC = () => {
  const [isExpanded, setIsExpanded] = useState(false);

  const renderCard = (step: Step, idx: number) => {
    const Icon = step.icon;
    return (
      <div
        key={idx}
        className="bg-white rounded-xl p-5 border border-slate-200 shadow-2xs hover:shadow-xs hover:border-slate-300 transition flex flex-col justify-between"
      >
        <div>
          <div className="flex items-center justify-between mb-3">
            <div className={`p-2 rounded-lg border ${step.color}`}>
              <Icon className="w-5 h-5" />
            </div>
            <span className="text-[11px] font-mono font-medium px-2 py-0.5 rounded-full bg-slate-100 border border-slate-200 text-slate-600">
              {step.category}
            </span>
          </div>
          <h3 className="font-bold text-slate-900 text-base mb-1.5 font-mono tracking-tight">
            {step.title}
          </h3>
          <p className="text-sm text-slate-500 leading-relaxed">
            {step.desc}
          </p>
        </div>

        {idx < steps.length - 1 && (
          <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-end text-slate-400 text-xs font-mono">
            <span>Next stage</span>
            <ArrowRight className="w-3.5 h-3.5 ml-1 text-slate-400" />
          </div>
        )}
      </div>
    );
  };

  return (
    <section id="control-loop" className="py-12 border-t border-slate-200">
      <div className="text-center max-w-3xl mx-auto mb-6">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-50 border border-indigo-200 text-indigo-700 text-xs font-mono font-semibold mb-3">
          <Activity className="w-3.5 h-3.5 text-indigo-600" />
          <span>Core Operational Lifecycle</span>
        </div>
        <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900">
          Architectural Control Loop
        </h2>
        <p className="mt-3 text-slate-500 text-sm sm:text-base leading-relaxed">
          A disciplined, 11-stage autonomous control cycle ensuring nodal accounts remain balanced, verified, and continuously compliant.
        </p>
        <div className="mt-4 flex justify-center">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setIsExpanded(!isExpanded)}
            icon={isExpanded ? <ChevronUp className="w-4 h-4 text-indigo-600" /> : <ChevronDown className="w-4 h-4 text-indigo-600" />}
          >
            {isExpanded ? "Hide 11-stage control cycle" : "Show 11-stage control cycle (11 steps)"}
          </Button>
        </div>
      </div>

      {isExpanded && (
        <div className="animate-in fade-in duration-200">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {steps.slice(0, 9).map((step, idx) => renderCard(step, idx))}
          </div>

          <div className="mt-5 flex flex-col md:flex-row justify-center gap-5">
            <div className="w-full md:w-[calc(50%-10px)] lg:w-[calc(33.333%-14px)]">
              {renderCard(steps[9], 9)}
            </div>
            <div className="w-full md:w-[calc(50%-10px)] lg:w-[calc(33.333%-14px)]">
              {renderCard(steps[10], 10)}
            </div>
          </div>
        </div>
      )}
    </section>
  );
};

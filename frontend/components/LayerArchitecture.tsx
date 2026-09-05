"use client";

import React, { useState } from "react";
import {
  Lock,
  Cpu,
  Bot,
  ShieldAlert,
  Wrench,
  CheckCircle,
  ScrollText,
  BarChart3,
  LayoutDashboard,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { Button } from "./ui/Button";

interface Layer {
  num: number;
  title: string;
  type: "Deterministic" | "AI Layer" | "Governance / Policy" | "Interface";
  desc: string;
  icon: React.ComponentType<{ className?: string }>;
  accent: string;
}

const layers: Layer[] = [
  {
    num: 1,
    title: "Data Layer",
    type: "Deterministic",
    desc: "Synthetic financial datasets, nodal transactions, bank settlement batches, and event stores.",
    icon: Lock,
    accent: "text-indigo-600 border-indigo-200 bg-indigo-50",
  },
  {
    num: 2,
    title: "Deterministic Financial-Control Layer",
    type: "Deterministic",
    desc: "Monetary arithmetic, reconciliation, balance tracking, SLA timers, double-entry verification, invariant assertions.",
    icon: Cpu,
    accent: "text-cyan-600 border-cyan-200 bg-cyan-50",
  },
  {
    num: 3,
    title: "AI Investigation Layer",
    type: "AI Layer",
    desc: "Cross-source evidence collection, temporal anomaly investigation, root-cause reasoning, and hypothesis generation via structured tools.",
    icon: Bot,
    accent: "text-indigo-600 border-indigo-200 bg-indigo-50",
  },
  {
    num: 4,
    title: "Policy & Safety Layer",
    type: "Governance / Policy",
    desc: "Strict permission gating, monetary thresholds, human-in-the-loop decision routing, and risk limits.",
    icon: ShieldAlert,
    accent: "text-rose-600 border-rose-200 bg-rose-50",
  },
  {
    num: 5,
    title: "Remediation Layer",
    type: "Deterministic",
    desc: "Controlled financial operations executed solely through isolated, verified deterministic micro-actions.",
    icon: Wrench,
    accent: "text-amber-600 border-amber-200 bg-amber-50",
  },
  {
    num: 6,
    title: "Verification Layer",
    type: "Deterministic",
    desc: "Post-action double-entry balance check and zero-variance invariant validation prior to commit.",
    icon: CheckCircle,
    accent: "text-emerald-600 border-emerald-200 bg-emerald-50",
  },
  {
    num: 7,
    title: "Audit Layer",
    type: "Governance / Policy",
    desc: "Immutable append-only record of every detection, reasoning step, decision, and financial action.",
    icon: ScrollText,
    accent: "text-teal-600 border-teal-200 bg-teal-50",
  },
  {
    num: 8,
    title: "Evaluation Layer",
    type: "Governance / Policy",
    desc: "Automated benchmark scenarios assessing agent investigation precision and financial control compliance.",
    icon: BarChart3,
    accent: "text-indigo-600 border-indigo-200 bg-indigo-50",
  },
  {
    num: 9,
    title: "UI Layer",
    type: "Interface",
    desc: "Operator interface presenting real-time account health, discrepancy timelines, AI explanations, and approval queues.",
    icon: LayoutDashboard,
    accent: "text-slate-700 border-slate-200 bg-slate-100",
  },
];

export const LayerArchitecture: React.FC = () => {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <section id="architecture" className="py-12 border-t border-slate-200">
      <div className="text-center max-w-3xl mx-auto mb-6">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-50 border border-indigo-200 text-indigo-700 text-xs font-mono font-semibold mb-4">
          <Lock className="w-3.5 h-3.5 text-indigo-600" />
          Strict Architectural Isolation
        </div>
        <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900">
          9-Layer Separation of Concerns
        </h2>
        <p className="mt-3 text-slate-500 text-sm sm:text-base leading-relaxed">
          The AI investigation engine has zero direct access to modify financial state. All ledger operations are strictly isolated inside deterministic, verified control barriers.
        </p>
        <div className="mt-4 flex justify-center">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setIsExpanded(!isExpanded)}
            icon={isExpanded ? <ChevronUp className="w-4 h-4 text-indigo-600" /> : <ChevronDown className="w-4 h-4 text-indigo-600" />}
          >
            {isExpanded ? "Hide 9-layer architecture" : "Show 9-layer architecture (9 layers)"}
          </Button>
        </div>
      </div>

      {isExpanded && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5 animate-in fade-in duration-200">
          {layers.map((layer) => {
            const Icon = layer.icon;
            return (
              <div
                key={layer.num}
                className="bg-white rounded-xl p-5 border border-slate-200 shadow-2xs hover:shadow-xs hover:border-slate-300 transition flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <div className={`p-2 rounded-lg border ${layer.accent}`}>
                      <Icon className="w-5 h-5" />
                    </div>
                    <span className="font-mono text-xs font-bold text-slate-400">
                      LAYER 0{layer.num}
                    </span>
                  </div>
                  <h3 className="font-bold text-slate-900 text-base mb-1.5 font-mono">
                    {layer.title}
                  </h3>
                  <p className="text-sm text-slate-500 leading-relaxed">
                    {layer.desc}
                  </p>
                </div>

                <div className="mt-4 pt-3 border-t border-slate-100">
                  <span className="text-xs font-mono text-slate-400">
                    Category: <span className="text-slate-700 font-semibold">{layer.type}</span>
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
};

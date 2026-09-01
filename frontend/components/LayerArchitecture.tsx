import React from "react";
import { Lock, Cpu, Bot, ShieldAlert, Wrench, CheckCircle, ScrollText, BarChart3, LayoutDashboard } from "lucide-react";

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
    accent: "text-blue-400 border-blue-500/20 bg-blue-500/10",
  },
  {
    num: 2,
    title: "Deterministic Financial-Control Layer",
    type: "Deterministic",
    desc: "Monetary arithmetic, reconciliation, balance tracking, SLA timers, double-entry verification, invariant assertions.",
    icon: Cpu,
    accent: "text-cyan-400 border-cyan-500/20 bg-cyan-500/10",
  },
  {
    num: 3,
    title: "AI Investigation Layer",
    type: "AI Layer",
    desc: "Cross-source evidence collection, temporal anomaly investigation, root-cause reasoning, and hypothesis generation via structured tools.",
    icon: Bot,
    accent: "text-purple-400 border-purple-500/20 bg-purple-500/10",
  },
  {
    num: 4,
    title: "Policy & Safety Layer",
    type: "Governance / Policy",
    desc: "Strict permission gating, monetary thresholds, human-in-the-loop decision routing, and risk limits.",
    icon: ShieldAlert,
    accent: "text-rose-400 border-rose-500/20 bg-rose-500/10",
  },
  {
    num: 5,
    title: "Remediation Layer",
    type: "Deterministic",
    desc: "Controlled financial operations executed solely through isolated, verified deterministic micro-actions.",
    icon: Wrench,
    accent: "text-amber-400 border-amber-500/20 bg-amber-500/10",
  },
  {
    num: 6,
    title: "Verification Layer",
    type: "Deterministic",
    desc: "Post-action double-entry balance check and zero-variance invariant validation prior to commit.",
    icon: CheckCircle,
    accent: "text-emerald-400 border-emerald-500/20 bg-emerald-500/10",
  },
  {
    num: 7,
    title: "Audit Layer",
    type: "Governance / Policy",
    desc: "Immutable append-only record of every detection, reasoning step, decision, and financial action.",
    icon: ScrollText,
    accent: "text-teal-400 border-teal-500/20 bg-teal-500/10",
  },
  {
    num: 8,
    title: "Evaluation Layer",
    type: "Governance / Policy",
    desc: "Automated benchmark scenarios assessing agent investigation precision and financial control compliance.",
    icon: BarChart3,
    accent: "text-indigo-400 border-indigo-500/20 bg-indigo-500/10",
  },
  {
    num: 9,
    title: "UI Layer",
    type: "Interface",
    desc: "Operator interface presenting real-time account health, discrepancy timelines, AI explanations, and approval queues.",
    icon: LayoutDashboard,
    accent: "text-slate-300 border-slate-700 bg-slate-800/40",
  },
];

export const LayerArchitecture: React.FC = () => {
  return (
    <section id="architecture" className="py-12 border-t border-slate-800/80">
      <div className="text-center max-w-3xl mx-auto mb-10">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-teal-500/10 border border-teal-500/20 text-teal-400 text-xs font-mono mb-4">
          <Lock className="w-3.5 h-3.5" />
          Strict Architectural Isolation
        </div>
        <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-white">
          9-Layer Separation of Concerns
        </h2>
        <p className="mt-3 text-slate-400 text-sm sm:text-base">
          The AI investigation engine has zero direct access to modify financial state. All ledger operations are strictly isolated inside deterministic, verified control barriers.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {layers.map((layer) => {
          const Icon = layer.icon;
          return (
            <div
              key={layer.num}
              className="glass-panel glass-panel-hover rounded-xl p-5 border border-slate-800/80 flex flex-col justify-between"
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
                <h3 className="font-semibold text-white text-base mb-1.5">
                  {layer.title}
                </h3>
                <p className="text-xs text-slate-400 leading-relaxed">
                  {layer.desc}
                </p>
              </div>

              <div className="mt-4 pt-3 border-t border-slate-800/40">
                <span className="text-[11px] font-mono text-slate-500">
                  Category: <span className="text-slate-300">{layer.type}</span>
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
};

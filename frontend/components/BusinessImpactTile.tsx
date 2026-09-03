"use client";

import React, { useState, useEffect } from "react";
import {
  TrendingUp,
  AlertTriangle,
  Info,
  ChevronDown,
  ChevronUp,
  RefreshCcw,
  CheckCircle2,
  HelpCircle,
  DollarSign,
} from "lucide-react";
import { BusinessImpactData, fetchBusinessImpact } from "../lib/api";
import { Button } from "./ui/Button";
import { SectionHeading } from "./ui/SectionHeading";

export function BusinessImpactTile() {
  const [data, setData] = useState<BusinessImpactData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showMethodology, setShowMethodology] = useState(false);

  useEffect(() => {
    loadImpact();
  }, []);

  const loadImpact = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchBusinessImpact();
      setData(res);
    } catch (err: any) {
      setError(err.message || "Failed to load business impact metrics.");
    } finally {
      setLoading(false);
    }
  };

  const formatRupees = (paise: number) => {
    const rupees = paise / 100.0;
    return `₹${rupees.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  };

  return (
    <section id="impact" className="w-full">
      <div className="glass-panel rounded-2xl p-6 sm:p-8 border border-slate-800/80 shadow-2xl relative overflow-hidden">
        {/* Background glow */}
        <div className="absolute top-0 right-0 -mr-20 -mt-20 w-80 h-80 bg-teal-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute bottom-0 left-0 -ml-20 -mb-20 w-80 h-80 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none" />

        {/* Section Header (Issue 3 & 14) */}
        <SectionHeading
          icon={<TrendingUp className="w-6 h-6 text-teal-400" />}
          title="Business Impact & Value Surfaced"
          badge={{
            text: "Tier-2 Business Impact (v2.0 ROI Tile)",
            icon: <DollarSign className="w-3.5 h-3.5 text-teal-400" />,
            color: "bg-teal-500/10 border-teal-500/30 text-teal-300",
          }}
          description="Auditable, transparent operational metrics measuring potential risk exposure identified and governance value delivered across nodal accounts."
          action={
            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setShowMethodology(!showMethodology)}
                icon={<Info className="w-3.5 h-3.5 text-cyan-400" />}
                title="View deterministic calculation methodology"
              >
                <span>Methodology</span>
                {showMethodology ? (
                  <ChevronUp className="w-3.5 h-3.5 ml-1 text-slate-400" />
                ) : (
                  <ChevronDown className="w-3.5 h-3.5 ml-1 text-slate-400" />
                )}
              </Button>

              <Button
                variant="icon"
                onClick={loadImpact}
                disabled={loading}
                title="Refresh business impact"
                aria-label="Refresh business impact"
                icon={<RefreshCcw className={`w-4 h-4 ${loading ? "animate-spin text-teal-400" : ""}`} />}
              />
            </div>
          }
        />

        {/* Main Content Area */}
        <div className="space-y-6">
          {error && (
            <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-sm flex items-center gap-3">
              <AlertTriangle className="w-5 h-5 shrink-0 text-rose-400" />
              <span>{error}</span>
            </div>
          )}

          {/* Primary Hero Metric: Financial Exposure Identified */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            <div className="lg:col-span-5 rounded-2xl bg-gradient-to-br from-slate-900/90 to-slate-950 border border-teal-500/30 p-6 flex flex-col justify-between relative overflow-hidden shadow-inner">
              <div className="absolute top-0 right-0 p-8 opacity-5 pointer-events-none">
                <TrendingUp className="w-48 h-48 text-teal-400" />
              </div>

              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-mono font-semibold uppercase tracking-wider text-slate-400">
                    Financial exposure identified
                  </span>
                  <span className="px-2 py-0.5 rounded text-xs font-mono font-bold bg-teal-500/15 text-teal-300 border border-teal-500/30">
                    POTENTIAL
                  </span>
                </div>

                <div className="mt-2 flex items-baseline gap-2">
                  <span className="text-xl sm:text-2xl font-bold text-teal-400">₹</span>
                  <span className="text-3xl sm:text-4xl lg:text-5xl font-extrabold text-white tracking-tight font-mono">
                    {data ? (data.financial_exposure_identified / 100).toLocaleString("en-IN", { minimumFractionDigits: 2 }) : "—"}
                  </span>
                </div>

                <p className="text-xs text-slate-300 mt-2 flex items-center gap-1.5 leading-relaxed">
                  <CheckCircle2 className="w-3.5 h-3.5 text-teal-400 shrink-0" />
                  Potential financial risk surfaced for governance and policy review
                </p>
              </div>

              <div className="mt-6 pt-4 border-t border-slate-800/80 flex items-center justify-between text-xs font-mono">
                <span className="text-slate-400">Realized savings:</span>
                <span className="text-slate-500 italic">
                  {data?.realized_savings === null ? "null (honest governance)" : data?.realized_savings}
                </span>
              </div>
            </div>

            {/* Secondary Operational Metrics Grid */}
            <div className="lg:col-span-7 grid grid-cols-2 sm:grid-cols-2 gap-4">
              <div className="rounded-xl bg-slate-900/60 border border-slate-800 p-5 flex flex-col justify-between">
                <div>
                  <span className="text-xs font-mono text-slate-400 block mb-1">Actionable cases</span>
                  <span className="text-2xl sm:text-3xl font-bold text-white font-mono">
                    {data?.actionable_case_count ?? "—"}
                  </span>
                </div>
                <div className="text-xs text-slate-400 mt-3 pt-2 border-t border-slate-800/60">
                  Exceptions with quantifiable exposure
                </div>
              </div>

              <div className="rounded-xl bg-slate-900/60 border border-slate-800 p-5 flex flex-col justify-between">
                <div>
                  <span className="text-xs font-mono text-slate-400 block mb-1">High-risk cases</span>
                  <span className="text-2xl sm:text-3xl font-bold text-amber-300 font-mono">
                    {data?.high_risk_case_count ?? "—"}
                  </span>
                </div>
                <div className="text-xs text-slate-400 mt-3 pt-2 border-t border-slate-800/60">
                  Severity: HIGH or CRITICAL
                </div>
              </div>

              <div className="rounded-xl bg-slate-900/60 border border-slate-800 p-5 flex flex-col justify-between">
                <div>
                  <span className="text-xs font-mono text-slate-400 block mb-1">Recurring patterns</span>
                  <span className="text-2xl sm:text-3xl font-bold text-cyan-300 font-mono">
                    {data?.recurring_pattern_count ?? "—"}
                  </span>
                </div>
                <div className="text-xs text-slate-400 mt-3 pt-2 border-t border-slate-800/60">
                  Identified by pattern miner
                </div>
              </div>

              <div className="rounded-xl bg-slate-900/60 border border-slate-800 p-5 flex flex-col justify-between">
                <div>
                  <span className="text-xs font-mono text-slate-400 block mb-1">Merchants impacted</span>
                  <span className="text-2xl sm:text-3xl font-bold text-purple-300 font-mono">
                    {data?.merchants_impacted ?? "—"}
                  </span>
                </div>
                <div className="text-xs text-slate-400 mt-3 pt-2 border-t border-slate-800/60">
                  Distinct merchant accounts protected
                </div>
              </div>
            </div>
          </div>

          {/* Transparent Classification Disclaimer */}
          <div className="rounded-xl bg-slate-900/40 border border-slate-800/80 p-4 text-xs text-slate-300 flex items-start gap-3">
            <Info className="w-4 h-4 text-cyan-400 shrink-0 mt-0.5" />
            <div className="leading-relaxed">
              <strong className="text-white">Classification guarantee: </strong>
              {data?.disclaimer ||
                "Exposure identified for review; not equivalent to recovered savings. No post-remediation realized savings are fabricated without concrete financial recovery evidence."}
            </div>
          </div>

          {/* Expandable Traceability & Methodology Drawer (Issue 15: H3) */}
          {showMethodology && (
            <div className="rounded-xl bg-slate-950/80 border border-slate-800 p-6 space-y-4 animate-in fade-in duration-200">
              <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                <HelpCircle className="w-4 h-4 text-cyan-400" />
                <span>Deterministic calculation methodology & traceability</span>
              </h3>
              <p className="text-sm text-slate-300 leading-relaxed">
                Nodal Sentinel rejects black-box or hallucinated financial claims. All metrics displayed in this tile are computed directly from SQLite persisted application records without LLM interpolation.
              </p>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs font-mono">
                <div className="p-3 rounded-lg bg-slate-900/80 border border-slate-800">
                  <div className="text-cyan-400 font-bold mb-1">Financial exposure identified</div>
                  <div className="text-slate-300">SUM(ExceptionRecord.exposure) over distinct exception records</div>
                </div>
                <div className="p-3 rounded-lg bg-slate-900/80 border border-slate-800">
                  <div className="text-cyan-400 font-bold mb-1">Actionable cases</div>
                  <div className="text-slate-300">COUNT(ExceptionRecord) WHERE exposure &gt; 0</div>
                </div>
                <div className="p-3 rounded-lg bg-slate-900/80 border border-slate-800">
                  <div className="text-cyan-400 font-bold mb-1">High-risk cases</div>
                  <div className="text-slate-300">COUNT(ExceptionRecord) WHERE severity IN (&apos;HIGH&apos;, &apos;CRITICAL&apos;)</div>
                </div>
                <div className="p-3 rounded-lg bg-slate-900/80 border border-slate-800">
                  <div className="text-cyan-400 font-bold mb-1">Recurring patterns</div>
                  <div className="text-slate-300">COUNT(ExceptionCluster) WHERE exception_count &ge; 2</div>
                </div>
                <div className="p-3 rounded-lg bg-slate-900/80 border border-slate-800">
                  <div className="text-cyan-400 font-bold mb-1">Merchants impacted</div>
                  <div className="text-slate-300">COUNT(DISTINCT GatewayTransaction.merchant_id)</div>
                </div>
                <div className="p-3 rounded-lg bg-slate-900/80 border border-slate-800">
                  <div className="text-cyan-400 font-bold mb-1">Double-counting protection</div>
                  <div className="text-slate-300">Deduplicated exception IDs eliminate join multiplication</div>
                </div>
              </div>

              <div className="text-xs text-slate-400 font-mono">
                API endpoint: <span className="text-slate-300">GET /impact/roi</span> | Engine version: <span className="text-slate-300">{data?.version || "v1.0.0"}</span>
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

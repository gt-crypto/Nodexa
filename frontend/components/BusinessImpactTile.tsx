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
  ShieldCheck,
} from "lucide-react";
import { BusinessImpactData, fetchBusinessImpact } from "../lib/api";
import { executeWithColdStartRetry } from "../lib/resilience";
import { ColdStartWakingCard } from "./ColdStartWakingCard";
import { formatPaiseOrUnavailable } from "../lib/formatters";
import { Button } from "./ui/Button";

export function BusinessImpactTile() {
  const [data, setData] = useState<BusinessImpactData | null>(null);
  const [loading, setLoading] = useState(false);
  const [wakingState, setWakingState] = useState<{ attempt: number; isTimeout: boolean } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showMethodology, setShowMethodology] = useState(false);

  useEffect(() => {
    loadImpact();
  }, []);

  const loadImpact = async () => {
    setLoading(true);
    setError(null);
    setWakingState(null);
    try {
      const res = await executeWithColdStartRetry(
        () => fetchBusinessImpact(),
        {
          onWaking: (attempt, maxAttempts) => {
            setWakingState({ attempt, isTimeout: false });
          },
          onRecovered: () => {
            setWakingState(null);
          },
        }
      );
      setData(res);
      setWakingState(null);
    } catch (err: any) {
      if (wakingState && wakingState.attempt >= 6) {
        setWakingState({ attempt: 6, isTimeout: true });
      } else {
        setError(err.message || "Failed to load business impact metrics.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <section id="impact" className="w-full">
      <div className="rounded-xl p-5 sm:p-6 border border-slate-800/80 bg-[#0d121d] shadow-sm relative overflow-hidden">
        {/* Main Card Header */}
        <header className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-800/80 mb-5">
          <div className="flex items-start sm:items-center gap-3 min-w-0">
            <div className="p-2 rounded-lg bg-[#111726] border border-slate-800 text-sky-400 shrink-0">
              <TrendingUp className="w-4 h-4" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <h2 className="text-base font-semibold text-white tracking-tight font-sans">
                  Business Impact &amp; Value Surfaced
                </h2>
                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded text-xs font-mono bg-sky-950/30 border border-sky-800/40 text-sky-300">
                  <DollarSign className="w-3 h-3 text-sky-400" />
                  <span>Tier-2 Business Impact</span>
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5 max-w-2xl leading-relaxed">
                Auditable operational metrics measuring potential risk exposure identified and governance value delivered across nodal accounts.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0 self-start sm:self-center">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setShowMethodology(!showMethodology)}
              icon={<Info className="w-3.5 h-3.5 text-sky-400" />}
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
              variant="secondary"
              size="sm"
              onClick={loadImpact}
              disabled={loading}
              title="Refresh business impact"
              aria-label="Refresh business impact"
              icon={<RefreshCcw className={`w-3.5 h-3.5 ${loading ? "animate-spin text-sky-400" : ""}`} />}
            >
              Refresh
            </Button>
          </div>
        </header>

        {/* Main Content Area */}
        <div className="space-y-5">
          {wakingState ? (
            <ColdStartWakingCard
              attempt={wakingState.attempt}
              maxAttempts={6}
              isTimeout={wakingState.isTimeout}
              onRetry={loadImpact}
              description="Connecting to Finance Controller…"
              compact
            />
          ) : error ? (
            <div className="p-3 rounded-lg bg-rose-950/30 border border-rose-800/40 text-rose-300 text-xs flex items-center gap-2.5">
              <AlertTriangle className="w-4 h-4 shrink-0 text-rose-400" />
              <span>{error}</span>
            </div>
          ) : null}

          {/* Primary Hero Metric: Financial Exposure Identified */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
            <div className="lg:col-span-5 rounded-xl bg-[#090d16] border border-sky-800/40 p-5 flex flex-col justify-between shadow-sm">
              <div className="space-y-2.5">
                <span className="text-xs font-medium text-slate-300 font-sans block">
                  Financial Exposure Identified
                </span>

                <div className="flex items-baseline gap-2.5 flex-wrap">
                  <div className="flex items-baseline gap-1">
                    <span className="text-xl font-bold text-sky-400 font-sans">₹</span>
                    <span className="text-3xl sm:text-4xl font-bold text-white tracking-tight financial-num">
                      {data ? (data.financial_exposure_identified / 100).toLocaleString("en-IN", { minimumFractionDigits: 2 }) : "—"}
                    </span>
                  </div>
                  <span className="px-2 py-0.5 rounded text-xs font-semibold font-sans bg-sky-950/50 text-sky-300 border border-sky-800/50 tracking-wide">
                    POTENTIAL
                  </span>
                </div>

                <p className="text-xs text-slate-400 flex items-center gap-1.5 leading-relaxed font-sans font-normal">
                  <CheckCircle2 className="w-3.5 h-3.5 text-sky-400 shrink-0" />
                  <span>Potential financial risk surfaced for governance and policy review</span>
                </p>
              </div>

              <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between text-xs">
                <span className="text-slate-400 font-sans">Realized savings</span>
                <span className="text-slate-200 font-semibold num-tabular font-sans">
                  {formatPaiseOrUnavailable(data?.realized_savings, "N/A")}
                </span>
              </div>
            </div>

            {/* Secondary Operational Metrics Grid */}
            <div className="lg:col-span-7 grid grid-cols-2 gap-3">
              <div className="rounded-xl bg-[#090d16] border border-slate-800/80 p-4 flex flex-col justify-between">
                <div>
                  <span className="text-xs font-medium text-slate-400 block mb-1 font-sans">Actionable Cases</span>
                  <span className="text-2xl font-bold text-white financial-num">
                    {data?.actionable_case_count ?? "—"}
                  </span>
                </div>
                <div className="text-xs text-slate-400 mt-2 pt-2 border-t border-slate-800/60 font-sans">
                  Quantifiable exposure &gt; 0
                </div>
              </div>

              <div className="rounded-xl bg-[#090d16] border border-slate-800/80 p-4 flex flex-col justify-between">
                <div>
                  <span className="text-xs font-medium text-slate-400 block mb-1 font-sans">High-Risk Cases</span>
                  <span className="text-2xl font-bold text-amber-400 financial-num">
                    {data?.high_risk_case_count ?? "—"}
                  </span>
                </div>
                <div className="text-xs text-slate-400 mt-2 pt-2 border-t border-slate-800/60 font-sans">
                  Severity: HIGH / CRITICAL
                </div>
              </div>

              <div className="rounded-xl bg-[#090d16] border border-slate-800/80 p-4 flex flex-col justify-between">
                <div>
                  <span className="text-xs font-medium text-slate-400 block mb-1 font-sans">Recurring Patterns</span>
                  <span className="text-2xl font-bold text-sky-400 financial-num">
                    {data?.recurring_pattern_count ?? "—"}
                  </span>
                </div>
                <div className="text-xs text-slate-400 mt-2 pt-2 border-t border-slate-800/60 font-sans">
                  Identified by pattern miner
                </div>
              </div>

              <div className="rounded-xl bg-[#090d16] border border-slate-800/80 p-4 flex flex-col justify-between">
                <div>
                  <span className="text-xs font-medium text-slate-400 block mb-1 font-sans">Merchants Impacted</span>
                  <span className="text-2xl font-bold text-purple-400 financial-num">
                    {data?.merchants_impacted ?? "—"}
                  </span>
                </div>
                <div className="text-xs text-slate-400 mt-2 pt-2 border-t border-slate-800/60 font-sans">
                  Distinct merchant accounts
                </div>
              </div>
            </div>
          </div>

          {/* Transparent Classification Disclaimer */}
          <div className="rounded-lg bg-[#090d16] border border-slate-800/80 p-3 text-xs text-slate-300 flex items-start gap-2.5">
            <Info className="w-3.5 h-3.5 text-sky-400 shrink-0 mt-0.5" />
            <div className="leading-relaxed space-y-0.5">
              <strong className="text-white font-medium block text-xs">
                Classification Guarantee:
              </strong>
              <p className="text-xs text-slate-400 font-normal leading-relaxed">
                {data?.disclaimer ||
                  "Exposure identified for review; not equivalent to recovered savings. No post-remediation realized savings are fabricated without concrete financial recovery evidence."}
              </p>
            </div>
          </div>

          {/* Expandable Traceability & Methodology Drawer */}
          {showMethodology && (
            <div className="rounded-xl bg-[#090d16] border border-slate-800 p-5 space-y-3 animate-in fade-in duration-150">
              <h3 className="text-xs font-semibold text-white flex items-center gap-2 font-mono uppercase tracking-wider">
                <HelpCircle className="w-3.5 h-3.5 text-sky-400" />
                <span>Deterministic Calculation Methodology &amp; Traceability</span>
              </h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Nodexa rejects black-box or hallucinated financial claims. All metrics displayed in this tile are computed directly from SQLite persisted application records without LLM interpolation.
              </p>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5 text-xs font-mono pt-1">
                <div className="p-2.5 rounded bg-[#0d121d] border border-slate-800">
                  <div className="text-sky-400 font-medium mb-0.5">Financial exposure identified</div>
                  <div className="text-slate-400">SUM(ExceptionRecord.exposure) over distinct exception records</div>
                </div>
                <div className="p-2.5 rounded bg-[#0d121d] border border-slate-800">
                  <div className="text-sky-400 font-medium mb-0.5">Actionable cases</div>
                  <div className="text-slate-400">COUNT(ExceptionRecord) WHERE exposure &gt; 0</div>
                </div>
                <div className="p-2.5 rounded bg-[#0d121d] border border-slate-800">
                  <div className="text-sky-400 font-medium mb-0.5">High-risk cases</div>
                  <div className="text-slate-400">COUNT(ExceptionRecord) WHERE severity IN (&apos;HIGH&apos;, &apos;CRITICAL&apos;)</div>
                </div>
                <div className="p-2.5 rounded bg-[#0d121d] border border-slate-800">
                  <div className="text-sky-400 font-medium mb-0.5">Recurring patterns</div>
                  <div className="text-slate-400">COUNT(ExceptionCluster) WHERE exception_count &ge; 2</div>
                </div>
                <div className="p-2.5 rounded bg-[#0d121d] border border-slate-800">
                  <div className="text-sky-400 font-medium mb-0.5">Merchants impacted</div>
                  <div className="text-slate-400">COUNT(DISTINCT GatewayTransaction.merchant_id)</div>
                </div>
                <div className="p-2.5 rounded bg-[#0d121d] border border-slate-800">
                  <div className="text-sky-400 font-medium mb-0.5">Double-counting protection</div>
                  <div className="text-slate-400">Deduplicated exception IDs eliminate join multiplication</div>
                </div>
              </div>

              <div className="text-xs text-slate-400 font-mono pt-1">
                API endpoint: <span className="text-slate-300">GET /impact/roi</span> | Engine version: <span className="text-slate-300">{data?.version || "v1.0.0"}</span>
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

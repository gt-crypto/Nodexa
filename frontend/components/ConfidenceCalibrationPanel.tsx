"use client";

import React, { useState, useEffect } from "react";
import {
  Target,
  CheckCircle2,
  AlertTriangle,
  HelpCircle,
  RefreshCcw,
  ChevronDown,
  ChevronUp,
  Info,
  Layers,
  Bot,
  TrendingUp,
  Gauge,
} from "lucide-react";
import { ConfidenceCalibrationData, fetchConfidenceCalibration } from "../lib/api";
import { Button } from "./ui/Button";
import { SectionHeading } from "./ui/SectionHeading";

export function ConfidenceCalibrationPanel() {
  const [data, setData] = useState<ConfidenceCalibrationData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showMethodology, setShowMethodology] = useState(false);

  // Filters
  const [predTypeFilter, setPredTypeFilter] = useState<string>("");
  const [sourceFilter, setSourceFilter] = useState<string>("");

  useEffect(() => {
    loadCalibration();
  }, [predTypeFilter, sourceFilter]);

  const loadCalibration = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchConfidenceCalibration(
        predTypeFilter || undefined,
        sourceFilter || undefined
      );
      setData(res);
    } catch (err: any) {
      setError(err.message || "Failed to load confidence calibration data.");
    } finally {
      setLoading(false);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "CALIBRATED":
        return "bg-emerald-500/15 border-emerald-500/40 text-emerald-300";
      case "UNDER_CONFIDENT":
        return "bg-cyan-500/15 border-cyan-500/40 text-cyan-300";
      case "OVER_CONFIDENT":
        return "bg-rose-500/15 border-rose-500/40 text-rose-300";
      case "INSUFFICIENT_DATA":
      default:
        return "bg-amber-500/15 border-amber-500/40 text-amber-300";
    }
  };

  const getConfidenceLevelStyle = (level: string) => {
    switch (level) {
      case "HIGH":
        return "bg-emerald-500/10 text-emerald-400 border-emerald-500/30";
      case "MEDIUM":
        return "bg-amber-500/10 text-amber-400 border-amber-500/30";
      case "LOW":
      default:
        return "bg-slate-800 text-slate-300 border-slate-700";
    }
  };

  return (
    <section id="calibration" className="w-full">
      <div className="glass-panel rounded-2xl p-6 sm:p-8 border border-slate-800/90 shadow-2xl relative overflow-hidden">
        {/* Top Glow Accent */}
        <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-cyan-500 via-indigo-500 to-emerald-500" />

        {/* Section Header (Issue 3 & 14) */}
        <SectionHeading
          icon={<Gauge className="w-6 h-6 text-cyan-400" />}
          title="Confidence Calibration Dashboard"
          badge={{
            text: "Tier-3 Empirical Calibration (v2.0 Judge Dashboard)",
            icon: <Target className="w-3.5 h-3.5 text-cyan-400" />,
            color: "bg-cyan-500/10 border-cyan-500/30 text-cyan-300",
          }}
          description="Empirical verification evaluating whether Nodexa's confidence labels correspond to observed correctness across genuine historical prediction outcomes without fabricating probabilities."
          action={
            <div className="flex flex-wrap items-center gap-2">
              <select
                value={predTypeFilter}
                onChange={(e) => setPredTypeFilter(e.target.value)}
                className="px-3 py-1.5 rounded-xl border border-slate-700 bg-slate-800/90 text-slate-300 text-xs font-mono focus:outline-none focus:border-cyan-500"
              >
                <option value="">All prediction types</option>
                <option value="INVESTIGATION">Investigations</option>
                <option value="VERIFIER">Adversarial verifier</option>
                <option value="DRIFT">Drift radar</option>
              </select>

              <select
                value={sourceFilter}
                onChange={(e) => setSourceFilter(e.target.value)}
                className="px-3 py-1.5 rounded-xl border border-slate-700 bg-slate-800/90 text-slate-300 text-xs font-mono focus:outline-none focus:border-cyan-500"
              >
                <option value="">All sources</option>
                <option value="seeded">Seeded benchmark</option>
                <option value="live-injected">Live-injected</option>
              </select>

              <Button
                variant="secondary"
                size="sm"
                onClick={() => setShowMethodology(!showMethodology)}
                icon={<Info className="w-3.5 h-3.5 text-cyan-400" />}
              >
                <span>{showMethodology ? "Hide methodology" : "Methodology"}</span>
                {showMethodology ? (
                  <ChevronUp className="w-3.5 h-3.5 ml-1 text-slate-400" />
                ) : (
                  <ChevronDown className="w-3.5 h-3.5 ml-1 text-slate-400" />
                )}
              </Button>

              <Button
                variant="icon"
                onClick={loadCalibration}
                disabled={loading}
                title="Refresh calibration data"
                aria-label="Refresh calibration data"
                icon={<RefreshCcw className={`w-4 h-4 ${loading ? "animate-spin text-cyan-400" : ""}`} />}
              />
            </div>
          }
        />

        {/* Panel Body */}
        <div className="space-y-6">
          {error && (
            <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-sm flex items-center gap-3">
              <AlertTriangle className="w-5 h-5 shrink-0 text-rose-400" />
              <span>{error}</span>
            </div>
          )}

          {/* Key Metrics Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Status Card */}
            <div className="p-6 rounded-2xl bg-gradient-to-br from-slate-900/90 to-slate-950 border border-slate-800 flex flex-col justify-between shadow-inner">
              <div>
                <div className="text-xs font-mono uppercase tracking-wider text-slate-400 mb-1 font-semibold">
                  Calibration status
                </div>
                <div className="mt-2">
                  <span
                    className={`inline-block px-3 py-1 rounded-full text-xs font-mono font-bold border ${getStatusBadge(
                      data?.status || "INSUFFICIENT_DATA"
                    )}`}
                  >
                    {data?.status || "INSUFFICIENT_DATA"}
                  </span>
                </div>
              </div>
              <p className="text-xs text-slate-400 mt-4 leading-relaxed">
                {data?.status === "INSUFFICIENT_DATA"
                  ? "Honest reporting: insufficient evaluated observations."
                  : "Empirical evaluation across historical outcomes."}
              </p>
            </div>

            {/* Total Predictions & Coverage */}
            <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 flex flex-col justify-between">
              <div>
                <div className="text-xs font-mono uppercase tracking-wider text-slate-400 mb-1 font-semibold">
                  Predictions surfaced
                </div>
                <div className="flex items-baseline gap-2 mt-2">
                  <span className="text-3xl font-extrabold text-white font-mono">
                    {data?.total_predictions ?? 0}
                  </span>
                  <span className="text-slate-500 font-mono text-xs">total</span>
                </div>
              </div>
              <div className="text-xs font-mono text-slate-400 mt-4 pt-3 border-t border-slate-800 flex justify-between">
                <span>Evaluated: <strong className="text-emerald-400">{data?.evaluated_predictions ?? 0}</strong></span>
                <span>Unevaluated: <strong className="text-slate-300">{data?.unevaluated_predictions ?? 0}</strong></span>
              </div>
            </div>

            {/* Overall Correctness */}
            <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 flex flex-col justify-between">
              <div>
                <div className="text-xs font-mono uppercase tracking-wider text-slate-400 mb-1 font-semibold">
                  Evaluated correctness
                </div>
                <div className="flex items-baseline gap-2 mt-2">
                  <span className="text-3xl font-extrabold text-emerald-400 font-mono">
                    {data?.correctness_rate !== null && data?.correctness_rate !== undefined
                      ? `${(data.correctness_rate * 100).toFixed(1)}%`
                      : "—"}
                  </span>
                </div>
              </div>
              <p className="text-xs text-slate-400 mt-4 leading-relaxed">
                Empirical agreement between prediction and verified outcome.
              </p>
            </div>

            {/* Numerical Calibration */}
            <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 flex flex-col justify-between">
              <div>
                <div className="text-xs font-mono uppercase tracking-wider text-slate-400 mb-1 font-semibold">
                  Brier & ECE scores
                </div>
                <div className="mt-2 text-xs font-mono space-y-1">
                  <div className="flex justify-between">
                    <span className="text-slate-400">Brier score:</span>
                    <span className="text-slate-300 font-bold">
                      {data?.numerical_metrics?.brier_score !== null && data?.numerical_metrics?.brier_score !== undefined
                        ? data.numerical_metrics.brier_score.toFixed(4)
                        : "Unavailable"}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">ECE:</span>
                    <span className="text-slate-300 font-bold">
                      {data?.numerical_metrics?.ece !== null && data?.numerical_metrics?.ece !== undefined
                        ? data.numerical_metrics.ece.toFixed(4)
                        : "Unavailable"}
                    </span>
                  </div>
                </div>
              </div>
              <p className="text-xs text-slate-400 mt-3 leading-relaxed">
                {data?.numerical_metrics?.reason || "Requires genuine numerical probabilities."}
              </p>
            </div>
          </div>

          {/* Categorical Confidence Buckets Table */}
          <div className="rounded-2xl bg-slate-900/40 border border-slate-800 p-6 space-y-4">
            <h3 className="text-xs font-mono uppercase tracking-wider text-slate-300 font-semibold flex items-center justify-between">
              <span>Confidence level breakdown & observed correctness</span>
              <span className="text-slate-400 font-normal">HIGH &bull; MEDIUM &bull; LOW</span>
            </h3>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400 text-xs">
                    <th className="py-3 px-4">Confidence level</th>
                    <th className="py-3 px-4">Total count</th>
                    <th className="py-3 px-4">Evaluated count</th>
                    <th className="py-3 px-4">Observed correctness</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {data?.confidence_buckets &&
                    Object.entries(data.confidence_buckets).map(([level, b]) => {
                      const crPercent =
                        b.correctness_rate !== null ? (b.correctness_rate * 100).toFixed(1) : "—";
                      return (
                        <tr key={level} className="hover:bg-slate-900/40 transition">
                          <td className="py-3 px-4">
                            <span
                              className={`px-2.5 py-0.5 rounded-full text-xs font-bold border ${getConfidenceLevelStyle(
                                b.confidence_level
                              )}`}
                            >
                              {b.confidence_level}
                            </span>
                          </td>
                          <td className="py-3 px-4 text-white font-bold">{b.prediction_count}</td>
                          <td className="py-3 px-4 text-slate-300">{b.evaluated_count}</td>
                          <td className="py-3 px-4">
                            {b.correctness_rate !== null ? (
                              <span className="text-slate-300">
                                <span className="text-emerald-400 font-semibold">{b.correct_count} correct</span> ({crPercent}%)
                              </span>
                            ) : (
                              <span className="text-slate-500 italic">No evaluated outcomes available</span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Reliability Diagram / Numerical Bins Drawer (Issue 15: H3) */}
          {data && data.numerical_metrics.status === "CALCULATED" && (
            <div className="rounded-2xl bg-slate-950 border border-slate-800 p-6 space-y-4">
              <h3 className="text-sm font-semibold text-white font-mono flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-emerald-400" />
                <span>Reliability diagram data (5 bins)</span>
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-5 gap-3 text-xs font-mono">
                {data.numerical_metrics.reliability_bins.map((bin, i) => (
                  <div key={i} className="p-3 rounded-xl bg-slate-900/60 border border-slate-800 space-y-1">
                    <div className="text-cyan-400 font-bold">{bin.range}</div>
                    <div className="text-slate-400">Count: {bin.count}</div>
                    <div className="text-emerald-400">
                      Acc: {bin.accuracy !== null ? `${(bin.accuracy * 100).toFixed(1)}%` : "—"}
                    </div>
                    <div className="text-purple-300">
                      Conf: {bin.confidence !== null ? `${(bin.confidence * 100).toFixed(1)}%` : "—"}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Methodology & Limitations Drawer (Issue 15: H3) */}
          {showMethodology && (
            <div className="rounded-2xl bg-slate-950 border border-slate-800 p-6 space-y-4 animate-in fade-in duration-200">
              <h3 className="text-sm font-semibold text-white font-mono flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-cyan-400" />
                <span>Calibration methodology & verification bounds</span>
              </h3>

              <div className="text-xs text-slate-300 space-y-2 leading-relaxed">
                <p>
                  <strong>1. Empirical Correctness vs Probability:</strong> Nodexa makes a strict distinction between a confidence label (e.g. HIGH) and mathematical probability. A HIGH confidence prediction means the engine identified consistent supporting operational signals, not that it represents a 90% Bayesian failure probability.
                </p>
                <p>
                  <strong>2. Evaluation Ground Truth Isolation:</strong> Evaluated outcomes are obtained strictly from benchmark ground truth comparisons (<code className="text-cyan-300">evaluation_cases</code>) and verified post-decision verification records (<code className="text-cyan-300">verification_records</code>). Live-injected anomalies without confirmed ground truth remain isolated in the unevaluated count and do not alter the evaluated correctness rate.
                </p>
                <p>
                  <strong>3. Numerical Calibration Requirements:</strong> Brier Score and Expected Calibration Error (ECE) are only computed when genuine numerical probabilities exist with at least 5 evaluated outcomes. If observations are sparse or categorical-only, numerical metrics are explicitly marked unavailable rather than manufactured.
                </p>
              </div>

              <div className="pt-2 flex flex-wrap items-center gap-3 text-xs font-mono">
                <div className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-slate-900 text-slate-300 border border-slate-800">
                  <Layers className="w-3.5 h-3.5 text-cyan-400" />
                  <span>Seeded observations: {data?.source_breakdown.seeded_count || 0}</span>
                </div>
                {(data?.source_breakdown.live_injected_count || 0) > 0 && (
                  <div className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-indigo-500/10 text-indigo-300 border border-indigo-500/30">
                    <Bot className="w-3.5 h-3.5 text-indigo-400" />
                    <span>Live-injected: {data?.source_breakdown.live_injected_count} (Unevaluated)</span>
                  </div>
                )}
                <span className="text-slate-400 ml-auto">
                  Version: {data?.methodology_version || "v1.0.0"} | Snapshot: {data?.snapshot_id || "—"}
                </span>
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

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
        return "bg-emerald-50 border-emerald-200 text-emerald-700";
      case "UNDER_CONFIDENT":
        return "bg-cyan-50 border-cyan-200 text-cyan-700";
      case "OVER_CONFIDENT":
        return "bg-rose-50 border-rose-200 text-rose-700";
      case "INSUFFICIENT_DATA":
      default:
        return "bg-amber-50 border-amber-200 text-amber-700";
    }
  };

  const getConfidenceLevelStyle = (level: string) => {
    switch (level) {
      case "HIGH":
        return "bg-emerald-50 text-emerald-700 border-emerald-200";
      case "MEDIUM":
        return "bg-amber-50 text-amber-700 border-amber-200";
      case "LOW":
      default:
        return "bg-slate-100 text-slate-700 border-slate-200";
    }
  };

  return (
    <section id="calibration" className="w-full">
      <div className="rounded-xl p-5 sm:p-6 border border-slate-200 bg-white shadow-xs relative overflow-hidden">
        {/* Subtle Brand Accent Line */}
        <div className="absolute top-0 left-0 right-0 h-0.5 bg-gradient-to-r from-indigo-500/80 via-cyan-400/60 to-transparent" />

        {/* Section Header */}
        <SectionHeading
          icon={<Gauge className="w-5 h-5 text-indigo-600" />}
          title="Confidence Calibration Dashboard"
          badge={{
            text: "Tier-3 Empirical Calibration (Judge Dashboard)",
            icon: <Target className="w-3.5 h-3.5 text-indigo-600" />,
            color: "bg-indigo-50 border-indigo-200 text-indigo-700",
          }}
          description="Empirical verification evaluating whether Nodexa's confidence labels correspond to observed correctness across genuine historical prediction outcomes without fabricating probabilities."
          action={
            <div className="flex flex-wrap items-center gap-2">
              <select
                value={predTypeFilter}
                onChange={(e) => setPredTypeFilter(e.target.value)}
                className="px-2.5 py-1 rounded-lg border border-slate-300 bg-white text-slate-900 text-xs font-mono focus:outline-none focus:border-indigo-500 shadow-2xs"
              >
                <option value="">All prediction types</option>
                <option value="INVESTIGATION">Investigations</option>
                <option value="VERIFIER">Adversarial verifier</option>
                <option value="DRIFT">Drift radar</option>
              </select>

              <select
                value={sourceFilter}
                onChange={(e) => setSourceFilter(e.target.value)}
                className="px-2.5 py-1 rounded-lg border border-slate-300 bg-white text-slate-900 text-xs font-mono focus:outline-none focus:border-indigo-500 shadow-2xs"
              >
                <option value="">All sources</option>
                <option value="seeded">Seeded benchmark</option>
                <option value="live-injected">Live-injected</option>
              </select>

              <Button
                variant="secondary"
                size="sm"
                onClick={() => setShowMethodology(!showMethodology)}
                icon={<Info className="w-3.5 h-3.5 text-indigo-600" />}
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
                icon={<RefreshCcw className={`w-3.5 h-3.5 ${loading ? "animate-spin text-indigo-600" : ""}`} />}
              />
            </div>
          }
        />

        {/* Panel Body */}
        <div className="space-y-5 mt-4">
          {error && (
            <div className="p-3.5 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center gap-3">
              <AlertTriangle className="w-4 h-4 shrink-0 text-rose-600" />
              <span>{error}</span>
            </div>
          )}

          {/* Key Metrics Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
            {/* Status Card */}
            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 flex flex-col justify-between shadow-2xs">
              <div>
                <div className="text-[10px] font-mono uppercase tracking-wider text-slate-500 mb-1 font-bold">
                  Calibration Status
                </div>
                <div className="mt-1.5">
                  <span
                    className={`inline-block px-2.5 py-0.5 rounded text-xs font-mono font-bold border ${getStatusBadge(
                      data?.status || "INSUFFICIENT_DATA"
                    )}`}
                  >
                    {data?.status || "INSUFFICIENT_DATA"}
                  </span>
                </div>
              </div>
              <p className="text-[11px] text-slate-500 mt-3 leading-relaxed">
                {data?.status === "INSUFFICIENT_DATA"
                  ? "Honest reporting: insufficient evaluated observations."
                  : "Empirical evaluation across historical outcomes."}
              </p>
            </div>

            {/* Total Predictions & Coverage */}
            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 flex flex-col justify-between shadow-2xs">
              <div>
                <div className="text-[10px] font-mono uppercase tracking-wider text-slate-500 mb-1 font-bold">
                  Predictions Surfaced
                </div>
                <div className="flex items-baseline gap-2 mt-1.5">
                  <span className="text-2xl sm:text-3xl font-bold text-slate-900 font-mono num-tabular">
                    {data?.total_predictions ?? 0}
                  </span>
                  <span className="text-slate-400 font-mono text-xs">total</span>
                </div>
              </div>
              <div className="text-[11px] font-mono text-slate-600 mt-3 pt-2.5 border-t border-slate-200 flex justify-between">
                <span>Evaluated: <strong className="text-emerald-700 num-tabular font-bold">{data?.evaluated_predictions ?? 0}</strong></span>
                <span>Unevaluated: <strong className="text-slate-700 num-tabular font-bold">{data?.unevaluated_predictions ?? 0}</strong></span>
              </div>
            </div>

            {/* Overall Correctness */}
            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 flex flex-col justify-between shadow-2xs">
              <div>
                <div className="text-[10px] font-mono uppercase tracking-wider text-slate-500 mb-1 font-bold">
                  Evaluated Correctness
                </div>
                <div className="flex items-baseline gap-2 mt-1.5">
                  <span className="text-2xl sm:text-3xl font-bold text-emerald-700 font-mono num-tabular">
                    {data?.correctness_rate !== null && data?.correctness_rate !== undefined
                      ? `${(data.correctness_rate * 100).toFixed(1)}%`
                      : "—"}
                  </span>
                </div>
              </div>
              <p className="text-[11px] text-slate-500 mt-3 leading-relaxed">
                Empirical agreement between prediction and verified outcome.
              </p>
            </div>

            {/* Numerical Calibration */}
            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 flex flex-col justify-between shadow-2xs">
              <div>
                <div className="text-[10px] font-mono uppercase tracking-wider text-slate-500 mb-1 font-bold">
                  Brier & ECE Scores
                </div>
                <div className="mt-1.5 text-xs font-mono space-y-1">
                  <div className="flex justify-between">
                    <span className="text-slate-500">Brier:</span>
                    <span className="text-slate-900 font-bold num-tabular">
                      {data?.numerical_metrics?.brier_score !== null && data?.numerical_metrics?.brier_score !== undefined
                        ? data.numerical_metrics.brier_score.toFixed(4)
                        : "Unavailable"}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">ECE:</span>
                    <span className="text-slate-900 font-bold num-tabular">
                      {data?.numerical_metrics?.ece !== null && data?.numerical_metrics?.ece !== undefined
                        ? data.numerical_metrics.ece.toFixed(4)
                        : "Unavailable"}
                    </span>
                  </div>
                </div>
              </div>
              <p className="text-[11px] text-slate-500 mt-2.5 leading-relaxed">
                {data?.numerical_metrics?.reason || "Requires genuine numerical probabilities."}
              </p>
            </div>
          </div>

          {/* Categorical Confidence Buckets Table */}
          <div className="rounded-xl bg-white border border-slate-200 p-4 sm:p-5 space-y-3 shadow-2xs">
            <h3 className="text-xs font-mono uppercase tracking-wider text-slate-700 font-bold flex items-center justify-between">
              <span>Confidence Level Breakdown & Observed Correctness</span>
              <span className="text-slate-400 font-normal">HIGH &bull; MEDIUM &bull; LOW</span>
            </h3>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-200 text-slate-600 text-[11px] uppercase tracking-wider bg-slate-50 font-sans font-semibold">
                    <th className="py-2.5 px-3">Confidence Level</th>
                    <th className="py-2.5 px-3 text-right">Total Count</th>
                    <th className="py-2.5 px-3 text-right">Evaluated Count</th>
                    <th className="py-2.5 px-3">Observed Correctness</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 font-sans">
                  {data?.confidence_buckets &&
                    Object.entries(data.confidence_buckets).map(([level, b]) => {
                      const crPercent =
                        b.correctness_rate !== null ? (b.correctness_rate * 100).toFixed(1) : "—";
                      return (
                        <tr key={level} className="hover:bg-slate-50 transition">
                          <td className="py-2.5 px-3">
                            <span
                              className={`px-2 py-0.5 rounded text-[10px] font-bold font-mono border ${getConfidenceLevelStyle(
                                b.confidence_level
                              )}`}
                            >
                              {b.confidence_level}
                            </span>
                          </td>
                          <td className="py-2.5 px-3 text-slate-900 font-bold text-right num-tabular">{b.prediction_count}</td>
                          <td className="py-2.5 px-3 text-slate-700 text-right num-tabular">{b.evaluated_count}</td>
                          <td className="py-2.5 px-3">
                            {b.correctness_rate !== null ? (
                              <span className="text-slate-700">
                                <span className="text-emerald-700 font-semibold num-tabular">{b.correct_count} correct</span> (<span className="num-tabular font-medium">{crPercent}%</span>)
                              </span>
                            ) : (
                              <span className="text-slate-400 italic">No evaluated outcomes available</span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Reliability Diagram / Numerical Bins Drawer */}
          {data && data.numerical_metrics.status === "CALCULATED" && (
            <div className="rounded-xl bg-slate-50 border border-slate-200 p-4 space-y-3 shadow-2xs">
              <h3 className="text-xs font-bold text-slate-900 font-mono flex items-center gap-2 uppercase tracking-wider">
                <TrendingUp className="w-3.5 h-3.5 text-emerald-600" />
                <span>Reliability Diagram Data (5 Bins)</span>
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-5 gap-2.5 text-xs font-mono">
                {data.numerical_metrics.reliability_bins.map((bin, i) => (
                  <div key={i} className="p-2.5 rounded-lg bg-white border border-slate-200 space-y-1 shadow-2xs">
                    <div className="text-indigo-600 font-bold">{bin.range}</div>
                    <div className="text-slate-500 text-[11px]">Count: <span className="text-slate-900 font-semibold num-tabular">{bin.count}</span></div>
                    <div className="text-emerald-700 text-[11px] font-medium">
                      Acc: <span className="num-tabular">{bin.accuracy !== null ? `${(bin.accuracy * 100).toFixed(1)}%` : "—"}</span>
                    </div>
                    <div className="text-indigo-600 text-[11px] font-medium">
                      Conf: <span className="num-tabular">{bin.confidence !== null ? `${(bin.confidence * 100).toFixed(1)}%` : "—"}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Methodology & Limitations Drawer */}
          {showMethodology && (
            <div className="rounded-xl bg-slate-50 border border-slate-200 p-4 sm:p-5 space-y-3 animate-in fade-in duration-200 shadow-2xs">
              <h3 className="text-xs font-bold text-slate-900 font-mono flex items-center gap-2 uppercase tracking-wider">
                <CheckCircle2 className="w-3.5 h-3.5 text-indigo-600" />
                <span>Calibration Methodology & Verification Bounds</span>
              </h3>

              <div className="text-xs text-slate-600 space-y-2 leading-relaxed">
                <p>
                  <strong>1. Empirical Correctness vs Probability:</strong> Nodexa makes a strict distinction between a confidence label (e.g. HIGH) and mathematical probability. A HIGH confidence prediction means the engine identified consistent supporting operational signals, not that it represents a 90% Bayesian failure probability.
                </p>
                <p>
                  <strong>2. Evaluation Ground Truth Isolation:</strong> Evaluated outcomes are obtained strictly from benchmark ground truth comparisons (<code className="text-indigo-600 bg-white px-1 py-0.5 rounded border border-slate-200 font-mono">evaluation_cases</code>) and verified post-decision verification records (<code className="text-indigo-600 bg-white px-1 py-0.5 rounded border border-slate-200 font-mono">verification_records</code>). Live-injected anomalies without confirmed ground truth remain isolated in the unevaluated count and do not alter the evaluated correctness rate.
                </p>
                <p>
                  <strong>3. Numerical Calibration Requirements:</strong> Brier Score and Expected Calibration Error (ECE) are only computed when genuine numerical probabilities exist with at least 5 evaluated outcomes. If observations are sparse or categorical-only, numerical metrics are explicitly marked unavailable rather than manufactured.
                </p>
              </div>

              <div className="pt-2 flex flex-wrap items-center gap-2 text-xs font-mono">
                <div className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-white text-slate-700 border border-slate-200 shadow-2xs">
                  <Layers className="w-3 h-3 text-indigo-600" />
                  <span>Seeded observations: <strong className="text-slate-900 num-tabular">{data?.source_breakdown.seeded_count || 0}</strong></span>
                </div>
                {(data?.source_breakdown.live_injected_count || 0) > 0 && (
                  <div className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-indigo-50 text-indigo-700 border border-indigo-200">
                    <Bot className="w-3 h-3 text-indigo-600" />
                    <span>Live-injected: <strong className="text-slate-900 num-tabular">{data?.source_breakdown.live_injected_count}</strong> (Unevaluated)</span>
                  </div>
                )}
                <span className="text-slate-400 ml-auto text-[11px]">
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

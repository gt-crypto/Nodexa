"use client";

import React, { useState, useEffect } from "react";
import {
  Activity,
  AlertTriangle,
  TrendingDown,
  TrendingUp,
  Clock,
  Shield,
  HelpCircle,
  RefreshCcw,
  ChevronDown,
  ChevronUp,
  Info,
  Radar,
  ArrowUpRight,
  ArrowDownRight,
  Minus,
} from "lucide-react";
import { DriftPredictionData, fetchDriftPrediction } from "../lib/api";
import { Button } from "./ui/Button";
import { SectionHeading } from "./ui/SectionHeading";

export function PredictiveDriftRadarPanel() {
  const [data, setData] = useState<DriftPredictionData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showDetails, setShowDetails] = useState(false);

  useEffect(() => {
    loadPrediction();
  }, []);

  const loadPrediction = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchDriftPrediction();
      setData(res);
    } catch (err: any) {
      setError(err.message || "Failed to load drift radar prediction.");
    } finally {
      setLoading(false);
    }
  };

  const formatRupees = (paise: number) => {
    return (paise / 100).toLocaleString("en-IN", { minimumFractionDigits: 2 });
  };

  const getRiskBandBadge = (band: string) => {
    switch (band) {
      case "CRITICAL":
        return "bg-rose-500/15 border-rose-500/40 text-rose-300";
      case "HIGH":
        return "bg-orange-500/15 border-orange-500/40 text-orange-300";
      case "MODERATE":
        return "bg-amber-500/15 border-amber-500/40 text-amber-300";
      case "LOW":
      default:
        return "bg-emerald-500/15 border-emerald-500/40 text-emerald-300";
    }
  };

  const getDirectionBadge = (dir: string) => {
    switch (dir) {
      case "DETERIORATING":
        return {
          icon: <ArrowUpRight className="w-4 h-4 text-rose-400" />,
          style: "bg-rose-500/15 border-rose-500/40 text-rose-300",
        };
      case "IMPROVING":
        return {
          icon: <ArrowDownRight className="w-4 h-4 text-emerald-400" />,
          style: "bg-emerald-500/15 border-emerald-500/40 text-emerald-300",
        };
      case "STABLE":
      default:
        return {
          icon: <Minus className="w-4 h-4 text-slate-400" />,
          style: "bg-slate-800 border-slate-700 text-slate-300",
        };
    }
  };

  return (
    <section id="drift" className="w-full">
      <div className="glass-panel rounded-2xl p-6 sm:p-8 border border-slate-800/90 shadow-2xl relative overflow-hidden">
        {/* Glow Accent */}
        <div className="absolute top-0 right-0 -mr-20 -mt-20 w-80 h-80 bg-rose-500/10 rounded-full blur-3xl pointer-events-none" />

        {/* Section Header (Issue 3 & 14) */}
        <SectionHeading
          icon={<Radar className="w-6 h-6 text-rose-400 animate-pulse" />}
          title="Predictive Nodal Drift Radar"
          badge={{
            text: "Tier-3 Predictive Analytics (v2.0 Early-Warning Radar)",
            icon: <Activity className="w-3.5 h-3.5 text-rose-400" />,
            color: "bg-rose-500/10 border-rose-500/30 text-rose-300",
          }}
          description="Deterministic early-warning detection monitoring leading signals of operational and control deterioration across nodal accounts before SLA breaches occur."
          action={
            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setShowDetails(!showDetails)}
                icon={<Info className="w-3.5 h-3.5 text-cyan-400" />}
              >
                <span>{showDetails ? "Hide details" : "Window details"}</span>
                {showDetails ? (
                  <ChevronUp className="w-3.5 h-3.5 ml-1 text-slate-400" />
                ) : (
                  <ChevronDown className="w-3.5 h-3.5 ml-1 text-slate-400" />
                )}
              </Button>

              <Button
                variant="icon"
                onClick={loadPrediction}
                disabled={loading}
                title="Refresh drift radar"
                aria-label="Refresh drift radar"
                icon={<RefreshCcw className={`w-4 h-4 ${loading ? "animate-spin text-rose-400" : ""}`} />}
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

          {/* Insufficient Data State */}
          {data && data.direction === "INSUFFICIENT_DATA" ? (
            <div className="p-6 rounded-2xl bg-slate-900/60 border border-amber-500/30 text-center space-y-3">
              <HelpCircle className="w-12 h-12 text-amber-400 mx-auto opacity-75" />
              <h3 className="text-lg font-bold text-white">Insufficient temporal baseline observations</h3>
              <p className="text-sm text-slate-300 max-w-xl mx-auto leading-relaxed">
                Predictive drift estimation requires multiple historical observation windows. As continuous operational transactions flow into the nodal account, the radar will activate automatically.
              </p>
            </div>
          ) : (
            <>
              {/* Radar Hero Metrics Grid */}
              <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-4">
                {/* Score Card */}
                <div className="md:col-span-1 p-6 rounded-2xl bg-gradient-to-br from-slate-900/90 to-slate-950 border border-slate-800 flex flex-col justify-between shadow-inner">
                  <div>
                    <div className="text-xs font-mono uppercase tracking-wider text-slate-400 mb-1 font-semibold">
                      Nodal drift score
                    </div>
                    <div className="flex items-baseline gap-2 mt-2">
                      <span className="text-4xl sm:text-5xl font-extrabold text-white font-mono">
                        {data?.drift_score ?? 0}
                      </span>
                      <span className="text-slate-500 font-mono text-xs">/ 100</span>
                    </div>
                    <div className="mt-3">
                      <span
                        className={`inline-block px-3 py-1 rounded-full text-xs font-mono font-bold border ${getRiskBandBadge(
                          data?.risk_band || "LOW"
                        )}`}
                      >
                        {data?.risk_band || "LOW"} RISK DRIFT
                      </span>
                    </div>
                  </div>

                  <div className="text-xs text-slate-400 mt-4 pt-3 border-t border-slate-800">
                    Confidence: <strong className="text-slate-300 font-mono">{data?.confidence || "MEDIUM"}</strong>
                  </div>
                </div>

                {/* Direction Card */}
                <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 flex flex-col justify-between">
                  <div>
                    <div className="text-xs font-mono uppercase tracking-wider text-slate-400 mb-2 font-semibold">
                      Observed trajectory
                    </div>
                    <div className="flex items-center gap-2 mt-2">
                      {data && (
                        <span
                          className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border text-xs font-mono font-bold ${
                            getDirectionBadge(data.direction).style
                          }`}
                        >
                          {getDirectionBadge(data.direction).icon}
                          <span>{data.direction}</span>
                        </span>
                      )}
                    </div>
                  </div>

                  <p className="text-xs text-slate-400 mt-4 leading-relaxed">
                    Comparison between baseline and current observation windows.
                  </p>
                </div>

                {/* Leading Indicators Summary */}
                <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 flex flex-col justify-between">
                  <div>
                    <div className="text-xs font-mono uppercase tracking-wider text-slate-400 mb-1 font-semibold">
                      Leading signals active
                    </div>
                    <div className="text-3xl font-extrabold text-white font-mono mt-2">
                      {data?.signals?.filter((s) => s.contribution > 0).length ?? 0}
                    </div>
                  </div>

                  <p className="text-xs text-slate-400 mt-4 leading-relaxed">
                    Weighted operational signals monitoring SLA, exceptions & controls.
                  </p>
                </div>

                {/* Action Urgency */}
                <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 flex flex-col justify-between">
                  <div>
                    <div className="text-xs font-mono uppercase tracking-wider text-slate-400 mb-1 font-semibold">
                      Suggested action
                    </div>
                    <div className="text-base font-bold text-teal-300 mt-2 font-mono">
                      {data?.risk_band === "HIGH_DRIFT"
                        ? "IMMEDIATE RECONCILIATION AUDIT"
                        : data?.risk_band === "ELEVATED"
                        ? "TIGHTEN RISK CONTROLS"
                        : data?.risk_band === "WATCH"
                        ? "WATCHLIST EXCEPTION QUEUES"
                        : "NOMINAL CONTROL HEALTH"}
                    </div>
                  </div>

                  <p className="text-xs text-slate-400 mt-4 leading-relaxed">
                    Deterministic recommendations derived from leading signals.
                  </p>
                </div>
              </div>

              {/* Signals Breakdown Table (Issue 15: H3) */}
              <div className="p-6 rounded-2xl bg-slate-900/40 border border-slate-800 space-y-4">
                <h3 className="text-xs font-mono uppercase tracking-wider text-slate-300 font-semibold flex items-center justify-between">
                  <span>Deterministic leading signals breakdown</span>
                  <span className="text-slate-500 font-normal">Weights normalized to 100</span>
                </h3>

                <div className="space-y-3">
                  {data?.signals && data.signals.length > 0 ? (
                    data.signals.map((sig, i) => (
                      <div
                        key={i}
                        className="p-4 rounded-xl bg-slate-900/80 border border-slate-800/80 flex flex-col md:flex-row md:items-center justify-between gap-3"
                      >
                        <div className="space-y-1">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-semibold text-white">
                              {sig.name || sig.signal.replace(/_/g, " ")}
                            </span>
                            <span className="text-xs font-mono text-slate-400">({sig.signal})</span>
                          </div>
                          <p className="text-xs text-slate-400">{sig.explanation}</p>
                        </div>

                        <div className="flex items-center gap-4 shrink-0 text-xs font-mono">
                          <div className="text-right">
                            <span className="text-slate-400 block text-xs">Observed delta</span>
                            <span className="font-bold text-white">
                              {sig.delta > 0 ? `+${sig.delta}` : sig.delta}
                            </span>
                          </div>

                          <div className="text-right pl-4 border-l border-slate-800">
                            <span className="text-slate-400 block text-xs">Score contribution</span>
                            <span
                              className={`font-bold ${
                                sig.contribution > 0 ? "text-amber-400" : "text-slate-400"
                              }`}
                            >
                              +{sig.contribution} pts
                            </span>
                          </div>
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="text-xs text-slate-400 py-4 text-center">
                      No deteriorating operational signals detected.
                    </div>
                  )}
                </div>
              </div>

              {/* Baseline vs Current Comparison Drawer (Issue 15: H3) */}
              {showDetails && data && (
                <div className="rounded-2xl bg-slate-950 border border-slate-800 p-6 space-y-4 animate-in fade-in duration-200">
                  <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                    <Clock className="w-4 h-4 text-cyan-400" />
                    <span>Temporal observation windows & metrics delta</span>
                  </h3>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono">
                    <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800">
                      <div className="text-cyan-400 font-bold mb-2">Baseline window</div>
                      <div className="text-slate-400">
                        {data.observation_window.baseline_start
                          ? new Date(data.observation_window.baseline_start).toLocaleString()
                          : "—"}{" "}
                        &rarr;{" "}
                        {data.observation_window.baseline_end
                          ? new Date(data.observation_window.baseline_end).toLocaleString()
                          : "—"}
                      </div>
                      <div className="mt-3 pt-3 border-t border-slate-800 space-y-1 text-slate-300">
                        <div>Exceptions: {data.baseline_metrics.exception_count}</div>
                        <div>Exposure: ₹{formatRupees(data.baseline_metrics.exposure_minor_units || 0)}</div>
                        <div>High-risk cases: {data.baseline_metrics.high_risk_count}</div>
                        <div>Control failures: {data.baseline_metrics.control_failures}</div>
                      </div>
                    </div>

                    <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800">
                      <div className="text-rose-400 font-bold mb-2">Current window</div>
                      <div className="text-slate-400">
                        {data.observation_window.current_start
                          ? new Date(data.observation_window.current_start).toLocaleString()
                          : "—"}{" "}
                        &rarr;{" "}
                        {data.observation_window.current_end
                          ? new Date(data.observation_window.current_end).toLocaleString()
                          : "—"}
                      </div>
                      <div className="mt-3 pt-3 border-t border-slate-800 space-y-1 text-slate-300">
                        <div>Exceptions: {data.current_metrics.exception_count}</div>
                        <div>Exposure: ₹{formatRupees(data.current_metrics.exposure_minor_units || 0)}</div>
                        <div>High-risk cases: {data.current_metrics.high_risk_count}</div>
                        <div>Control failures: {data.current_metrics.control_failures}</div>
                      </div>
                    </div>
                  </div>

                  <div className="pt-2 flex flex-wrap items-center gap-3 text-xs font-mono">
                    <div className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-slate-900 text-slate-300 border border-slate-800">
                      <Shield className="w-3.5 h-3.5 text-teal-400" />
                      <span>Zero ML hallucination guarantee</span>
                    </div>
                    <div className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-slate-900 text-slate-300 border border-slate-800">
                      <Activity className="w-3.5 h-3.5 text-rose-400" />
                      <span>Deterministic delta calculation</span>
                    </div>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </section>
  );
}

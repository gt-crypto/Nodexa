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
import { executeWithColdStartRetry } from "../lib/resilience";
import { ColdStartWakingCard } from "./ColdStartWakingCard";
import { formatNumber, formatSignedNumber, toSentenceCase } from "../lib/formatters";
import { Button } from "./ui/Button";
import { SectionHeading } from "./ui/SectionHeading";

export function PredictiveDriftRadarPanel() {
  const [data, setData] = useState<DriftPredictionData | null>(null);
  const [loading, setLoading] = useState(false);
  const [wakingState, setWakingState] = useState<{ attempt: number; isTimeout: boolean } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showDetails, setShowDetails] = useState(false);

  useEffect(() => {
    loadPrediction();
  }, []);

  const loadPrediction = async () => {
    setLoading(true);
    setError(null);
    setWakingState(null);
    try {
      const res = await executeWithColdStartRetry(
        () => fetchDriftPrediction(),
        {
          onWaking: (attempt) => setWakingState({ attempt, isTimeout: false }),
          onRecovered: () => setWakingState(null),
        }
      );
      setData(res);
      setWakingState(null);
    } catch (err: any) {
      if (wakingState && wakingState.attempt >= 6) {
        setWakingState({ attempt: 6, isTimeout: true });
      } else {
        setError(err.message || "Failed to load drift radar prediction.");
      }
    } finally {
      setLoading(false);
    }
  };

  const formatRupees = (paise: number) => {
    return (paise / 100).toLocaleString("en-IN", { minimumFractionDigits: 2 });
  };

  const formatRiskBandText = (band?: string) => {
    switch (band) {
      case "CRITICAL":
        return "Critical Risk Drift";
      case "HIGH":
        return "High Risk Drift";
      case "MODERATE":
      case "ELEVATED":
        return "Elevated Risk Drift";
      case "WATCH":
        return "Watch Risk Drift";
      case "LOW":
      case "STABLE":
      default:
        return "Stable Risk Drift";
    }
  };

  const getRiskBandBadge = (band: string) => {
    switch (band) {
      case "CRITICAL":
        return "bg-rose-50 border-rose-200 text-rose-700";
      case "HIGH":
        return "bg-rose-50 border-rose-200 text-rose-700";
      case "ELEVATED":
        return "bg-amber-50 border-amber-200 text-amber-800";
      case "WATCH":
        return "bg-amber-50 border-amber-200 text-amber-700";
      case "LOW":
      case "STABLE":
      default:
        return "bg-emerald-50 border-emerald-200 text-emerald-700";
    }
  };

  const getDirectionBadge = (dir: string) => {
    switch (dir) {
      case "DETERIORATING":
        return {
          icon: <ArrowUpRight className="w-3.5 h-3.5 text-rose-600" />,
          style: "bg-rose-50 border-rose-200 text-rose-700",
        };
      case "IMPROVING":
        return {
          icon: <ArrowDownRight className="w-3.5 h-3.5 text-emerald-600" />,
          style: "bg-emerald-50 border-emerald-200 text-emerald-700",
        };
      case "STABLE":
      default:
        return {
          icon: <Minus className="w-3.5 h-3.5 text-slate-400" />,
          style: "bg-slate-100 border-slate-200 text-slate-700",
        };
    }
  };

  return (
    <section id="drift-radar" className="w-full">
      <div className="rounded-xl p-5 sm:p-6 border border-slate-200 bg-white shadow-xs relative overflow-hidden">
        {/* Section Header */}
        <SectionHeading
          icon={<Radar className="w-5 h-5 text-indigo-600" />}
          title="Predictive Nodal Drift Radar"
          badge={{
            text: "Tier-2 Predictive Control",
            icon: <Activity className="w-3 h-3 text-indigo-600" />,
            color: "bg-indigo-50 border-indigo-200 text-indigo-700",
          }}
          description="Deterministic early-warning detection monitoring leading signals of operational and control deterioration across nodal accounts before SLA breaches occur."
          action={
            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setShowDetails(!showDetails)}
                icon={<Info className="w-3.5 h-3.5 text-indigo-600" />}
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
                icon={<RefreshCcw className={`w-3.5 h-3.5 ${loading ? "animate-spin text-indigo-600" : ""}`} />}
              />
            </div>
          }
        />

        {/* Panel Body */}
        <div className="space-y-5">
          {wakingState ? (
            <ColdStartWakingCard
              attempt={wakingState.attempt}
              maxAttempts={6}
              isTimeout={wakingState.isTimeout}
              onRetry={loadPrediction}
              description="Connecting to Predictive Drift Radar…"
              compact
            />
          ) : error ? (
            <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center gap-2.5">
              <AlertTriangle className="w-4 h-4 shrink-0 text-rose-600" />
              <span>{error}</span>
            </div>
          ) : null}

          {/* Insufficient Data State */}
          {data && data.direction === "INSUFFICIENT_DATA" ? (
            <div className="p-6 rounded-xl bg-slate-50 border border-amber-200 text-center space-y-2.5">
              <HelpCircle className="w-8 h-8 text-amber-500 mx-auto" />
              <h3 className="text-sm font-bold text-slate-900 font-sans">Insufficient temporal baseline observations</h3>
              <p className="text-xs text-slate-500 max-w-md mx-auto leading-relaxed">
                Predictive drift estimation requires multiple historical observation windows. As continuous operational transactions flow into the nodal account, the radar will activate automatically.
              </p>
            </div>
          ) : (
            <>
              {/* Radar Hero Metrics Grid */}
              <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-3">
                {/* Score Card */}
                <div className="md:col-span-1 p-4 rounded-xl bg-slate-50 border border-slate-200 flex flex-col justify-between shadow-2xs">
                  <div>
                    <div className="text-[11px] font-sans font-bold uppercase tracking-wider text-slate-500 mb-1">
                      Nodal Drift Score
                    </div>
                    <div className="flex items-baseline gap-1.5 mt-1.5">
                      <span className="text-3xl sm:text-4xl font-bold text-slate-900 financial-num">
                        {data?.drift_score ?? 0}
                      </span>
                      <span className="text-slate-400 font-sans text-xs">/ 100</span>
                    </div>
                    <div className="mt-2.5">
                      <span
                        className={`inline-block px-2.5 py-0.5 rounded text-[11px] font-bold font-sans border ${getRiskBandBadge(
                          data?.risk_band || "LOW"
                        )}`}
                      >
                        {formatRiskBandText(data?.risk_band)}
                      </span>
                    </div>
                  </div>

                  <div className="text-[11px] text-slate-500 mt-3 pt-2.5 border-t border-slate-200 font-sans">
                    Confidence: <strong className="text-slate-800">{data?.confidence || "MEDIUM"}</strong>
                  </div>
                </div>

                {/* Direction Card */}
                <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 flex flex-col justify-between shadow-2xs">
                  <div>
                    <div className="text-[11px] font-sans font-bold uppercase tracking-wider text-slate-500 mb-1">
                      Observed Trajectory
                    </div>
                    <div className="flex items-center gap-2 mt-2">
                      {data && (
                        <span
                          className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded border text-xs font-mono font-bold ${
                            getDirectionBadge(data.direction).style
                          }`}
                        >
                          {getDirectionBadge(data.direction).icon}
                          <span>{data.direction}</span>
                        </span>
                      )}
                    </div>
                  </div>

                  <p className="text-[11px] text-slate-500 mt-3 leading-relaxed font-sans">
                    Baseline vs current observation window comparison.
                  </p>
                </div>

                {/* Leading Indicators Summary */}
                <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 flex flex-col justify-between shadow-2xs">
                  <div>
                    <div className="text-[11px] font-sans font-bold uppercase tracking-wider text-slate-500 mb-1">
                      Leading Signals Active
                    </div>
                    <div className="text-2xl font-bold text-slate-900 financial-num mt-1.5">
                      {data?.signals?.filter((s) => s.contribution > 0).length ?? 0}
                    </div>
                  </div>

                  <p className="text-[11px] text-slate-500 mt-3 leading-relaxed font-sans">
                    Weighted operational signals monitoring SLA, exceptions &amp; controls.
                  </p>
                </div>

                {/* Action Urgency */}
                <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 flex flex-col justify-between shadow-2xs">
                  <div>
                    <div className="text-[11px] font-sans font-bold uppercase tracking-wider text-slate-500 mb-1">
                      Suggested Action
                    </div>
                    <div className="text-xs font-bold text-indigo-700 mt-2 font-sans tracking-wide">
                      {data?.risk_band === "HIGH_DRIFT"
                        ? "IMMEDIATE RECONCILIATION AUDIT"
                        : data?.risk_band === "ELEVATED"
                        ? "TIGHTEN RISK CONTROLS"
                        : data?.risk_band === "WATCH"
                        ? "WATCHLIST EXCEPTION QUEUES"
                        : "NOMINAL CONTROL HEALTH"}
                    </div>
                  </div>

                  <p className="text-[11px] text-slate-500 mt-3 leading-relaxed font-sans">
                    Deterministic recommendations derived from leading signals.
                  </p>
                </div>
              </div>

              {/* Signals Breakdown Table */}
              <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-3">
                <h3 className="text-[11px] font-mono uppercase tracking-wider text-slate-800 font-bold flex items-center justify-between">
                  <span>Deterministic Leading Signals Breakdown</span>
                  <span className="text-slate-500 font-normal">Weights Normalized to 100</span>
                </h3>

                <div className="space-y-2">
                  {data?.signals && data.signals.length > 0 ? (
                    data.signals.map((sig, i) => (
                      <div
                        key={i}
                        className="p-3 rounded-lg bg-white border border-slate-200 flex flex-col md:flex-row md:items-center justify-between gap-2.5 shadow-2xs"
                      >
                        <div className="space-y-0.5">
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-bold text-slate-900">
                              {sig.name || sig.signal.replace(/_/g, " ")}
                            </span>
                            <span className="text-[10px] font-mono text-slate-400">({sig.signal})</span>
                          </div>
                          <p className="text-xs text-slate-500">{sig.explanation}</p>
                        </div>

                        <div className="flex items-center gap-4 shrink-0 text-xs font-mono">
                          <div className="text-right">
                            <span className="text-slate-400 block text-[10px] font-medium">Observed delta</span>
                            <span className="font-bold text-slate-900 font-mono num-tabular">
                              {formatSignedNumber(sig.delta)}
                            </span>
                          </div>

                          <div className="text-right pl-3 border-l border-slate-200">
                            <span className="text-slate-400 block text-[10px] font-medium">Contribution</span>
                            <span
                              className={`font-bold num-tabular ${
                                sig.contribution > 0 ? "text-amber-600" : "text-slate-500"
                              }`}
                            >
                              +{sig.contribution} pts
                            </span>
                          </div>
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="text-xs text-slate-400 py-3 text-center font-mono">
                      No deteriorating operational signals detected.
                    </div>
                  )}
                </div>
              </div>

              {/* Baseline vs Current Comparison Drawer */}
              {showDetails && data && (
                <div className="rounded-xl bg-slate-50 border border-slate-200 p-4 space-y-3 animate-in fade-in duration-150 shadow-2xs">
                  <h3 className="text-xs font-bold text-slate-900 flex items-center gap-1.5 font-mono uppercase tracking-wider">
                    <Clock className="w-3.5 h-3.5 text-indigo-600" />
                    <span>Temporal Observation Windows &amp; Metrics Delta</span>
                  </h3>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs font-mono">
                    <div className="p-3 rounded-lg bg-white border border-slate-200 shadow-2xs">
                      <div className="text-indigo-600 font-bold mb-1.5 text-xs">Baseline Window</div>
                      <div className="text-slate-500 text-[11px]">
                        {data.observation_window.baseline_start
                          ? new Date(data.observation_window.baseline_start).toLocaleString()
                          : "—"}{" "}
                        &rarr;{" "}
                        {data.observation_window.baseline_end
                          ? new Date(data.observation_window.baseline_end).toLocaleString()
                          : "—"}
                      </div>
                      <div className="mt-2.5 pt-2.5 border-t border-slate-100 space-y-1 text-slate-700 text-[11px]">
                        <div>Exceptions: {formatNumber(data.baseline_metrics.exception_count)}</div>
                        <div>Exposure: ₹{formatRupees(data.baseline_metrics.exposure_minor_units || 0)}</div>
                        <div>High-risk cases: {formatNumber(data.baseline_metrics.high_risk_count)}</div>
                        <div>Control failures: {formatNumber(data.baseline_metrics.control_failures)}</div>
                      </div>
                    </div>

                    <div className="p-3 rounded-lg bg-white border border-slate-200 shadow-2xs">
                      <div className="text-rose-600 font-bold mb-1.5 text-xs">Current Window</div>
                      <div className="text-slate-500 text-[11px]">
                        {data.observation_window.current_start
                          ? new Date(data.observation_window.current_start).toLocaleString()
                          : "—"}{" "}
                        &rarr;{" "}
                        {data.observation_window.current_end
                          ? new Date(data.observation_window.current_end).toLocaleString()
                          : "—"}
                      </div>
                      <div className="mt-2.5 pt-2.5 border-t border-slate-100 space-y-1 text-slate-700 text-[11px]">
                        <div>Exceptions: {formatNumber(data.current_metrics.exception_count)}</div>
                        <div>Exposure: ₹{formatRupees(data.current_metrics.exposure_minor_units || 0)}</div>
                        <div>High-risk cases: {formatNumber(data.current_metrics.high_risk_count)}</div>
                        <div>Control failures: {formatNumber(data.current_metrics.control_failures)}</div>
                      </div>
                    </div>
                  </div>

                  <div className="pt-1 flex flex-wrap items-center gap-2 text-xs font-mono">
                    <div className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-white text-slate-700 border border-slate-200 text-[11px] shadow-2xs">
                      <Shield className="w-3 h-3 text-indigo-600" />
                      <span>Zero ML hallucination guarantee</span>
                    </div>
                    <div className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-white text-slate-700 border border-slate-200 text-[11px] shadow-2xs">
                      <Activity className="w-3 h-3 text-rose-600" />
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

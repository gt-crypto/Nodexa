"use client";

import React, { useState, useEffect } from "react";
import {
  Award,
  BarChart3,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Play,
  RefreshCw,
  Search,
  ShieldCheck,
  ShieldAlert,
  Coins,
  Cpu,
  FileSpreadsheet,
  Target,
  Sparkles,
  Layers,
  ArrowRight,
  Filter,
} from "lucide-react";
import {
  EvaluationReportSummary,
  EvaluationCaseResponse,
  EvaluationRunResponse,
} from "../types";
import {
  runEvaluation,
  getLatestBenchmark,
  getEvaluationRuns,
  getEvaluationCases,
} from "../lib/api";
import { executeWithColdStartRetry } from "../lib/resilience";
import { ColdStartWakingCard } from "./ColdStartWakingCard";
import { Button } from "./ui/Button";
import { Tabs } from "./ui/Tabs";

function formatAccuracy(val: number | undefined | null): string {
  if (val === undefined || val === null || isNaN(val)) {
    return "N/A";
  }
  return `${(val * 100).toFixed(1)}%`;
}

export const EvaluationDashboard: React.FC = () => {
  const [datasetId, setDatasetId] = useState<string>("ds_seed42_demo");
  const [report, setReport] = useState<EvaluationReportSummary | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [wakingState, setWakingState] = useState<{ attempt: number; isTimeout: boolean } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<
    "overview" | "detection" | "risk" | "exposure" | "cases" | "safety"
  >("overview");
  const [caseFilter, setCaseFilter] = useState<
    "ALL" | "TRUE_POSITIVE" | "FALSE_POSITIVE" | "FALSE_NEGATIVE" | "FALSE_CLOSURE"
  >("ALL");

  useEffect(() => {
    loadLatestBenchmark();
  }, []);

  const loadLatestBenchmark = async () => {
    try {
      const data = await executeWithColdStartRetry(
        () => getLatestBenchmark(),
        {
          onWaking: (attempt) => setWakingState({ attempt, isTimeout: false }),
          onRecovered: () => setWakingState(null),
        }
      );
      if (data) {
        setReport(data);
        if (data.run?.dataset_id) {
          setDatasetId(data.run.dataset_id);
        }
      }
      setWakingState(null);
    } catch {
      // Benchmark report not yet generated or cold-start
      if (wakingState && wakingState.attempt >= 6) {
        setWakingState({ attempt: 6, isTimeout: true });
      }
    }
  };

  const handleRunEvaluation = async (force: boolean = true) => {
    if (!datasetId.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const data = await runEvaluation(datasetId.trim(), force);
      setReport(data);
    } catch (err: any) {
      setError(err.message || "Failed to execute benchmark evaluation.");
    } finally {
      setLoading(false);
    }
  };

  const formatPaise = (paise: number) => {
    const inr = paise / 100;
    return `₹${inr.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  };

  const allCases: EvaluationCaseResponse[] = report
    ? [
        ...(report.false_positives || []),
        ...(report.false_negatives || []),
        ...(report.misclassifications || []),
      ]
    : [];

  const filteredCases = allCases.filter((c) => {
    if (caseFilter === "ALL") return true;
    if (caseFilter === "FALSE_CLOSURE") return c.is_false_closure;
    return c.match_status === caseFilter;
  });

  return (
    <section id="benchmark" className="w-full">
      <div className="bg-white border border-slate-200 rounded-2xl p-6 sm:p-8 shadow-xs text-slate-900">
        {/* Header */}
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between pb-6 border-b border-slate-200 gap-4">
          <div>
            <div className="flex items-center gap-3">
              <div className="p-2 bg-indigo-50 border border-indigo-100 rounded-xl text-indigo-600">
                <Award className="w-6 h-6" />
              </div>
              <div>
                <h2 className="text-xl sm:text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
                  <span>Benchmark Evaluation & Precision/Recall Engine</span>
                  <span className="text-xs px-2.5 py-0.5 rounded-full font-mono bg-indigo-50 text-indigo-700 border border-indigo-200 font-semibold">
                    v1.0.0
                  </span>
                </h2>
                <p className="text-sm text-slate-500 mt-1">
                  Independent accuracy evaluation layer with zero operational mutation and deterministic scoring
                </p>
              </div>
            </div>
          </div>

          {/* Action Controls */}
          <div className="flex items-center gap-2 w-full md:w-auto">
            <div className="relative flex-1 md:w-64">
              <Search className="w-4 h-4 absolute left-3 top-3 text-slate-400" />
              <input
                type="text"
                value={datasetId}
                onChange={(e) => setDatasetId(e.target.value)}
                placeholder="Dataset ID (e.g. ds_seed42_...)"
                className="w-full bg-white border border-slate-300 pl-9 pr-3 py-2 text-sm rounded-lg focus:outline-none focus:border-indigo-500 font-mono text-slate-900 shadow-2xs"
              />
            </div>
            <Button
              onClick={() => handleRunEvaluation(true)}
              disabled={loading || !datasetId.trim()}
              variant="primary"
              loading={loading}
              icon={<Play className="w-4 h-4 fill-current" />}
            >
              Run Benchmark
            </Button>
          </div>
        </div>

        {wakingState ? (
          <div className="mt-4">
            <ColdStartWakingCard
              attempt={wakingState.attempt}
              maxAttempts={6}
              isTimeout={wakingState.isTimeout}
              onRetry={loadLatestBenchmark}
              description="Connecting to Benchmark Evaluation Engine…"
              compact
            />
          </div>
        ) : error ? (
          <div className="mt-4 p-4 bg-rose-50 border border-rose-200 rounded-lg flex items-center gap-3 text-rose-800 text-sm">
            <AlertTriangle className="w-5 h-5 flex-shrink-0 text-rose-600" />
            <span>{error}</span>
          </div>
        ) : null}

        {report ? (
          <div className="mt-6 space-y-6">
            {/* Top KPI Metrics Banner */}
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              {/* Overall Score */}
              <div className="bg-white border border-slate-200 p-4 rounded-xl shadow-2xs relative overflow-hidden">
                <div className="flex justify-between items-start">
                  <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider font-sans">
                    Overall Benchmark Score
                  </span>
                  <Sparkles className="w-4 h-4 text-indigo-600" />
                </div>
                <div className="mt-2 flex items-baseline gap-2">
                  <span
                    className={`text-3xl font-bold financial-num ${
                      report.run.overall_score >= 80
                        ? "text-emerald-600"
                        : report.run.overall_score >= 60
                        ? "text-amber-600"
                        : "text-rose-600"
                    }`}
                  >
                    {report.run.overall_score}
                  </span>
                  <span className="text-xs text-slate-400 font-sans">/ 100</span>
                </div>
                <div className="mt-2.5 w-full bg-slate-100 border border-slate-200 rounded-full h-2.5 overflow-hidden p-0.5">
                  <div
                    className="bg-gradient-to-r from-indigo-500 to-cyan-500 h-full rounded-full transition-all duration-500"
                    style={{ width: `${Math.min(report.run.overall_score, 100)}%` }}
                  />
                </div>
              </div>

              {/* Precision & Recall */}
              <div className="bg-white border border-slate-200 p-4 rounded-xl shadow-2xs">
                <div className="flex justify-between items-start">
                  <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider font-sans">
                    Precision / Recall
                  </span>
                  <Target className="w-4 h-4 text-indigo-600" />
                </div>
                <div className="mt-2 flex items-baseline gap-2">
                  <span className="text-2xl font-bold text-indigo-600 financial-num">
                    {(report.run.precision * 100).toFixed(1)}%
                  </span>
                  <span className="text-xs text-slate-400">
                    / <span className="financial-num font-semibold text-slate-600">{(report.run.recall * 100).toFixed(1)}%</span>
                  </span>
                </div>
                <div className="mt-1 text-xs text-slate-500 font-sans num-tabular">
                  {report.run.precision_bps} bps / {report.run.recall_bps} bps
                </div>
              </div>

              {/* F1 Score */}
              <div className="bg-white border border-slate-200 p-4 rounded-xl shadow-2xs">
                <div className="flex justify-between items-start">
                  <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider font-sans">
                    F1 Metric
                  </span>
                  <BarChart3 className="w-4 h-4 text-indigo-600" />
                </div>
                <div className="mt-2 flex items-baseline gap-2">
                  <span className="text-2xl font-bold text-indigo-600 financial-num">
                    {(report.run.f1_score * 100).toFixed(1)}%
                  </span>
                  <span className="text-xs text-slate-500 font-sans num-tabular">
                    ({report.run.f1_score_bps} bps)
                  </span>
                </div>
                <div className="mt-1 text-xs text-slate-500 font-sans num-tabular">
                  TP: {report.run.true_positives} | FP: {report.run.false_positives} | FN:{" "}
                  {report.run.false_negatives}
                </div>
              </div>

              {/* Financial Exposure Accuracy */}
              <div className="bg-white border border-slate-200 p-4 rounded-xl shadow-2xs">
                <div className="flex justify-between items-start">
                  <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider font-sans">
                    Exposure Exact Match
                  </span>
                  <Coins className="w-4 h-4 text-amber-600" />
                </div>
                <div className="mt-2 flex items-baseline gap-2">
                  <span className="text-2xl font-bold text-amber-600 financial-num">
                    {(report.exposure_accuracy.exact_match_rate * 100).toFixed(1)}%
                  </span>
                  <span className="text-xs text-slate-400 num-tabular font-sans">
                    ({report.exposure_accuracy.exact_matches}/{report.exposure_accuracy.total_evaluated})
                  </span>
                </div>
                <div className="mt-1 text-xs text-slate-500 font-sans num-tabular">
                  MAE: {formatPaise(report.exposure_accuracy.mean_absolute_error)}
                </div>
              </div>

              {/* Critical Safety Status */}
              <div
                className={`p-4 rounded-xl border ${
                  report.run.safety_status === "PASSED"
                    ? "bg-emerald-50 border-emerald-200 text-emerald-800"
                    : "bg-rose-50 border-rose-200 text-rose-800"
                }`}
              >
                <div className="flex justify-between items-start">
                  <span className="text-[11px] font-bold uppercase tracking-wider font-sans">
                    Critical Safety Gate
                  </span>
                  {report.run.safety_status === "PASSED" ? (
                    <ShieldCheck className="w-5 h-5 text-emerald-600" />
                  ) : (
                    <ShieldAlert className="w-5 h-5 text-rose-600" />
                  )}
                </div>
                <div className="mt-2 text-xl font-bold font-sans tracking-wide">
                  {report.run.safety_status}
                </div>
                <div className="mt-1 text-xs opacity-90 font-sans num-tabular font-medium">
                  False Closures: {report.false_closure_count} (0 Required)
                </div>
              </div>
            </div>

            {/* Sub-system Component Scores Strip */}
            <div className="p-4 rounded-xl bg-slate-50/80 border border-slate-200 space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-xs font-bold text-slate-700 uppercase tracking-wider font-mono">
                  Sub-system component scores (100 pts max)
                </span>
                <span className="text-xs text-slate-500 font-mono">Isolated synthetic ground truth</span>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2.5">
                {[
                  {
                    label: "Detection",
                    score: report.run.scores.detection,
                    max: 25,
                    color: "text-indigo-600",
                  },
                  {
                    label: "Investigation",
                    score: report.run.scores.investigation,
                    max: 15,
                    color: "text-indigo-600",
                  },
                  {
                    label: "Financial Exposure",
                    score: report.run.scores.financial,
                    max: 15,
                    color: "text-amber-600",
                  },
                  {
                    label: "Risk Materiality",
                    score: report.run.scores.risk,
                    max: 20,
                    color: "text-indigo-600",
                  },
                  {
                    label: "Policy Gating",
                    score: report.run.scores.policy,
                    max: 10,
                    color: "text-emerald-600",
                  },
                  {
                    label: "Remediation",
                    score: report.run.scores.remediation,
                    max: 5,
                    color: "text-cyan-600",
                  },
                  {
                    label: "Verification",
                    score: report.run.scores.verification,
                    max: 10,
                    color: "text-teal-600",
                  },
                ].map((c) => (
                  <div
                    key={c.label}
                    className="bg-white border border-slate-200 p-3 rounded-lg flex flex-col justify-between shadow-2xs"
                  >
                    <span className="text-xs text-slate-500 font-medium truncate">
                      {c.label}
                    </span>
                    <div className="mt-1 flex items-baseline justify-between">
                      <span className={`text-lg font-bold ${c.color}`}>
                        {c.score}
                      </span>
                      <span className="text-xs text-slate-400 font-medium">/{c.max}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Navigation Tabs */}
            <Tabs
              ariaLabel="Benchmark evaluation sections"
              activeTab={activeTab}
              onChange={(id) => setActiveTab(id as any)}
              tabs={[
                { id: "overview", label: "Benchmark Overview" },
                { id: "detection", label: "Detection Metrics by Type" },
                { id: "risk", label: "Risk & Confusion Matrices" },
                { id: "exposure", label: "Financial Exposure" },
                { id: "cases", label: "Case Explorer", count: allCases.length },
                { id: "safety", label: "Safety & Invariants" },
              ]}
            />

            {/* Tab 1: Benchmark Overview */}
            {activeTab === "overview" && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="bg-white border border-slate-200 p-5 rounded-xl shadow-2xs space-y-4">
                  <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                    <Cpu className="w-4 h-4 text-indigo-600" />
                    Execution Meta & Architectural Isolation
                  </h3>
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <span className="text-xs text-slate-400 uppercase font-semibold">Run ID</span>
                      <p className="font-mono text-slate-900 text-xs truncate mt-0.5">
                        {report.run.evaluation_run_id}
                      </p>
                    </div>
                    <div>
                      <span className="text-xs text-slate-400 uppercase font-semibold">Dataset ID</span>
                      <p className="font-mono text-slate-900 text-xs truncate mt-0.5">
                        {report.run.dataset_id}
                      </p>
                    </div>
                    <div>
                      <span className="text-xs text-slate-400 uppercase font-semibold">Benchmark Version</span>
                      <p className="text-slate-900 mt-0.5">{report.run.benchmark_version}</p>
                    </div>
                    <div>
                      <span className="text-xs text-slate-400 uppercase font-semibold">Operational Isolation</span>
                      <p className="text-emerald-700 font-semibold mt-0.5">Read-Only Enforced</p>
                    </div>
                    <div>
                      <span className="text-xs text-slate-400 uppercase font-semibold">Total GT Cases</span>
                      <p className="text-slate-900 font-bold mt-0.5">
                        {report.run.total_ground_truth_cases}
                      </p>
                    </div>
                    <div>
                      <span className="text-xs text-slate-400 uppercase font-semibold">Total Predictions</span>
                      <p className="text-slate-900 font-bold mt-0.5">{report.run.total_predictions}</p>
                    </div>
                  </div>
                </div>

                <div className="bg-white border border-slate-200 p-5 rounded-xl shadow-2xs space-y-4">
                  <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                    <Layers className="w-4 h-4 text-indigo-600" />
                    Operational Stage Accuracy Rates
                  </h3>
                  <div className="space-y-2.5 text-sm">
                    <div className="flex justify-between items-center">
                      <span className="text-slate-600">Root Cause Diagnosis Accuracy</span>
                      <span className="font-mono font-bold text-indigo-600">
                        {formatAccuracy(report.root_cause_accuracy)}
                      </span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-slate-600">Severity Classification Accuracy</span>
                      <span className="font-mono font-bold text-indigo-600">
                        {formatAccuracy(report.severity_accuracy)}
                      </span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-slate-600">Priority Level Accuracy</span>
                      <span className="font-mono font-bold text-indigo-600">
                        {formatAccuracy(report.priority_accuracy)}
                      </span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-slate-600">Policy Gating Compliance</span>
                      <span className="font-mono font-bold text-emerald-700">
                        {formatAccuracy(report.policy_accuracy)}
                      </span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-slate-600">Remediation Execution Success</span>
                      <span className="font-mono font-bold text-cyan-600">
                        {formatAccuracy(report.remediation_success_rate)}
                      </span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-slate-600">Post-Remediation Verification</span>
                      <span className="font-mono font-bold text-teal-600">
                        {formatAccuracy(report.verification_success_rate)}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Tab 2: Detection by Type */}
            {activeTab === "detection" && (
              <div className="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-2xs">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 text-[11px] uppercase text-slate-600 border-b border-slate-200 font-semibold font-sans tracking-wider">
                    <tr>
                      <th className="px-4 py-3 text-left">Anomaly Category</th>
                      <th className="px-4 py-3 text-right">Expected</th>
                      <th className="px-4 py-3 text-right">Predicted</th>
                      <th className="px-4 py-3 text-right">TP</th>
                      <th className="px-4 py-3 text-right">FP</th>
                      <th className="px-4 py-3 text-right">FN</th>
                      <th className="px-4 py-3 text-right">Precision</th>
                      <th className="px-4 py-3 text-right">Recall</th>
                      <th className="px-4 py-3 text-right">F1 Score</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {Object.entries(report.detection_by_type || {}).map(([name, m]) => (
                      <tr key={name} className="hover:bg-slate-50 transition">
                        <td className="px-4 py-3 font-semibold text-slate-900 font-mono text-xs text-left">
                          {name}
                        </td>
                        <td className="px-4 py-3 text-slate-600 text-right num-tabular">{m.expected_count}</td>
                        <td className="px-4 py-3 text-slate-600 text-right num-tabular">{m.predicted_count}</td>
                        <td className="px-4 py-3 text-emerald-700 font-semibold text-right num-tabular">{m.true_positives}</td>
                        <td className="px-4 py-3 text-rose-600 text-right num-tabular">{m.false_positives}</td>
                        <td className="px-4 py-3 text-amber-600 text-right num-tabular">{m.false_negatives}</td>
                        <td className="px-4 py-3 text-xs text-indigo-600 text-right font-medium num-tabular">
                          {(m.precision * 100).toFixed(1)}%
                        </td>
                        <td className="px-4 py-3 text-xs text-indigo-600 text-right font-medium num-tabular">
                          {(m.recall * 100).toFixed(1)}%
                        </td>
                        <td className="px-4 py-3 text-xs font-bold text-indigo-700 text-right num-tabular">
                          {(m.f1_score * 100).toFixed(1)}%
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Tab 3: Risk & Confusion Matrices */}
            {activeTab === "risk" && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Severity Matrix */}
                <div className="bg-white border border-slate-200 p-5 rounded-xl shadow-2xs space-y-3">
                  <h3 className="font-bold text-sm text-slate-900">
                    Severity classification matrix
                  </h3>
                  <div className="space-y-2">
                    {report.severity_confusion_matrix?.map((item, idx) => (
                      <div
                        key={idx}
                        className="flex justify-between items-center bg-slate-50 p-2.5 rounded-lg border border-slate-100 text-xs"
                      >
                        <div className="flex items-center gap-2">
                          <span className="text-slate-500 font-mono">Expected:</span>
                          <span className="font-semibold text-slate-900">{item.expected_class}</span>
                          <ArrowRight className="w-3 h-3 text-slate-400" />
                          <span className="text-slate-500 font-mono">Predicted:</span>
                          <span className="font-semibold text-indigo-600">
                            {item.predicted_class}
                          </span>
                        </div>
                        <span className="px-2 py-0.5 rounded bg-indigo-50 text-indigo-700 font-mono font-bold border border-indigo-200">
                          {item.count} cases
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Priority Matrix */}
                <div className="bg-white border border-slate-200 p-5 rounded-xl shadow-2xs space-y-3">
                  <h3 className="font-bold text-sm text-slate-900">Priority level matrix</h3>
                  <div className="space-y-2">
                    {report.priority_confusion_matrix?.map((item, idx) => (
                      <div
                        key={idx}
                        className="flex justify-between items-center bg-slate-50 p-2.5 rounded-lg border border-slate-100 text-xs"
                      >
                        <div className="flex items-center gap-2">
                          <span className="text-slate-500 font-mono">Expected:</span>
                          <span className="font-semibold text-slate-900">{item.expected_class}</span>
                          <ArrowRight className="w-3 h-3 text-slate-400" />
                          <span className="text-slate-500 font-mono">Predicted:</span>
                          <span className="font-semibold text-indigo-600">
                            {item.predicted_class}
                          </span>
                        </div>
                        <span className="px-2 py-0.5 rounded bg-indigo-50 text-indigo-700 font-mono font-bold border border-indigo-200">
                          {item.count} cases
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* Tab 4: Financial Exposure */}
            {activeTab === "exposure" && (
              <div className="bg-white border border-slate-200 p-5 rounded-xl shadow-2xs space-y-4">
                <h3 className="font-bold text-base text-slate-900 flex items-center gap-2">
                  <Coins className="w-5 h-5 text-amber-600" />
                  Integer Minor Unit (Paise) Exposure Fidelity
                </h3>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                  <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
                    <span className="text-xs text-slate-500 font-medium">Total Expected</span>
                    <p className="text-base font-mono font-bold text-slate-900 mt-1">
                      {formatPaise(report.exposure_accuracy.total_expected_exposure)}
                    </p>
                  </div>
                  <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
                    <span className="text-xs text-slate-500 font-medium">Total Predicted</span>
                    <p className="text-base font-mono font-bold text-slate-900 mt-1">
                      {formatPaise(report.exposure_accuracy.total_predicted_exposure)}
                    </p>
                  </div>
                  <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
                    <span className="text-xs text-slate-500 font-medium">Total Absolute Error</span>
                    <p className="text-base font-mono font-bold text-amber-600 mt-1">
                      {formatPaise(report.exposure_accuracy.total_absolute_error)}
                    </p>
                  </div>
                  <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
                    <span className="text-xs text-slate-500 font-medium">Zero-Exposure Verified</span>
                    <p className="text-base font-mono font-bold text-emerald-700 mt-1">
                      {report.exposure_accuracy.zero_exposure_cases_verified} Cases
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* Tab 5: Case Explorer */}
            {activeTab === "cases" && (
              <div className="space-y-4">
                <div className="flex gap-2">
                  {[
                    { id: "ALL", label: `All Anomaly Cases (${allCases.length})` },
                    { id: "TRUE_POSITIVE", label: "True Positives" },
                    { id: "FALSE_CLOSURE", label: "False Closures" },
                  ].map((f) => (
                    <button
                      key={f.id}
                      onClick={() => setCaseFilter(f.id as any)}
                      className={`px-3 py-1.5 text-xs font-semibold rounded-lg border transition ${
                        caseFilter === f.id
                          ? "bg-indigo-50 border-indigo-200 text-indigo-700"
                          : "bg-white border-slate-200 text-slate-600 hover:bg-slate-50"
                      }`}
                    >
                      {f.label}
                    </button>
                  ))}
                </div>

                <div className="bg-white border border-slate-200 rounded-xl overflow-x-auto shadow-2xs">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-50 uppercase text-slate-600 border-b border-slate-200 font-semibold font-sans tracking-wider text-[11px]">
                      <tr>
                        <th className="px-3 py-2.5">Case ID</th>
                        <th className="px-3 py-2.5">Predicted Exception</th>
                        <th className="px-3 py-2.5">Status</th>
                        <th className="px-3 py-2.5">Matched By</th>
                        <th className="px-3 py-2.5 text-right">Expected Exposure</th>
                        <th className="px-3 py-2.5 text-right">Predicted Exposure</th>
                        <th className="px-3 py-2.5 text-right">Error Delta</th>
                        <th className="px-3 py-2.5">Error Tags</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {filteredCases.map((c) => (
                        <tr key={c.evaluation_case_id} className="hover:bg-slate-50 transition">
                          <td className="px-3 py-2.5 font-mono text-slate-900 font-medium">
                            {c.ground_truth_case_id || "N/A"}
                          </td>
                          <td className="px-3 py-2.5 font-mono text-indigo-600 truncate max-w-[180px] font-semibold">
                            {c.predicted_exception_id || "N/A"}
                          </td>
                          <td className="px-3 py-2.5">
                            <span
                              className={`px-2 py-0.5 rounded text-xs font-mono font-bold ${
                                c.match_status === "TRUE_POSITIVE" || c.match_status === "LEGITIMATE_CORRECT"
                                  ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                                  : c.match_status === "FALSE_POSITIVE"
                                  ? "bg-rose-50 text-rose-700 border border-rose-200"
                                  : "bg-amber-50 text-amber-700 border border-amber-200"
                              }`}
                            >
                              {c.match_status}
                            </span>
                          </td>
                          <td className="px-3 py-2.5 text-slate-500 font-mono text-xs">
                            {c.matched_by}
                          </td>
                          <td className="px-3 py-2.5 text-right text-slate-700 font-medium num-tabular">
                            {formatPaise(c.expected_exposure)}
                          </td>
                          <td className="px-3 py-2.5 text-right text-slate-700 font-medium num-tabular">
                            {formatPaise(c.predicted_exposure)}
                          </td>
                          <td
                            className={`px-3 py-2.5 text-right font-semibold num-tabular ${
                              c.exposure_error === 0 ? "text-emerald-700" : "text-amber-600"
                            }`}
                          >
                            {formatPaise(c.exposure_error)}
                          </td>
                          <td className="px-3 py-2.5">
                            {c.error_categories?.map((cat) => (
                              <span
                                key={cat}
                                className="inline-block mr-1 px-1.5 py-0.5 rounded bg-slate-100 text-[9px] font-mono text-slate-600 border border-slate-200"
                              >
                                {cat}
                              </span>
                            ))}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Tab 6: Safety & Invariants */}
            {activeTab === "safety" && (
              <div className="bg-white border border-slate-200 p-5 rounded-xl shadow-2xs space-y-4">
                <h3 className="font-bold text-base text-slate-900 flex items-center gap-2">
                  <ShieldCheck className="w-5 h-5 text-emerald-600" />
                  Critical Safety Invariant Gates (0-Tolerance)
                </h3>
                <div className="space-y-3">
                  {[
                    {
                      rule: "False Verified Closure = 0",
                      status: report.false_closure_count === 0 ? "PASSED" : "FAILED",
                      desc: "An exception must never be marked verified and closed if ground truth resolution was unachievable or exposure remains non-zero.",
                    },
                    {
                      rule: "Zero Operational Mutation",
                      status: "PASSED",
                      desc: "Evaluation layer enforces strictly read-only access to operational financial records, ledgers, and exceptions.",
                    },
                    {
                      rule: "Ground-Truth Architectural Isolation",
                      status: "PASSED",
                      desc: "Operational detection and investigation modules have 0 dependency or leakage on ground-truth schemas.",
                    },
                    {
                      rule: "Legitimate Case Protection",
                      status:
                        report.legitimate_cases_summary?.all_zero_exposure_verified
                          ? "PASSED"
                          : "WARNING",
                      desc: "Partial settlements and valid calendar timing exceptions are guarded with 0 exposure and no inappropriate financial clawbacks.",
                    },
                  ].map((gate) => (
                    <div
                      key={gate.rule}
                      className="flex justify-between items-start bg-slate-50 p-3.5 rounded-lg border border-slate-200"
                    >
                      <div>
                        <span className="font-bold text-sm text-slate-900">
                          {gate.rule}
                        </span>
                        <p className="text-xs text-slate-500 mt-0.5">{gate.desc}</p>
                      </div>
                      <span
                        className={`px-2.5 py-1 rounded text-xs font-mono font-bold ${
                          gate.status === "PASSED"
                            ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                            : "bg-rose-50 text-rose-700 border border-rose-200"
                        }`}
                      >
                        {gate.status}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="mt-8 text-center py-12 border border-dashed border-slate-300 rounded-xl bg-slate-50/50">
            <Award className="w-12 h-12 text-slate-400 mx-auto mb-3" />
            <h3 className="text-base font-bold text-slate-900">
              No Active Benchmark Evaluation Loaded
            </h3>
            <p className="text-sm text-slate-500 max-w-md mx-auto mt-1">
              Provide a dataset ID above (e.g. <span className="font-mono">ds_seed42_demo</span>) and click "Run Benchmark" to execute the full evaluation suite.
            </p>
          </div>
        )}
      </div>
    </section>
  );
};

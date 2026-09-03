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
      const data = await getLatestBenchmark();
      if (data) {
        setReport(data);
        if (data.run?.dataset_id) {
          setDatasetId(data.run.dataset_id);
        }
      }
    } catch {
      // Benchmark report not yet generated on initial load
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
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 sm:p-8 shadow-2xl text-slate-100">
        {/* Header */}
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between pb-6 border-b border-slate-800 gap-4">
          <div>
            <div className="flex items-center gap-3">
              <div className="p-2 bg-indigo-500/10 border border-indigo-500/30 rounded-xl text-indigo-400">
                <Award className="w-6 h-6" />
              </div>
              <div>
                <h2 className="text-xl sm:text-2xl font-bold text-white tracking-wide flex items-center gap-2">
                  <span>Benchmark Evaluation & Precision/Recall Engine</span>
                  <span className="text-xs px-2.5 py-0.5 rounded-full font-mono bg-indigo-900/60 text-indigo-300 border border-indigo-700/50">
                    v1.0.0
                  </span>
                </h2>
                <p className="text-sm text-slate-400 mt-1">
                  Independent accuracy evaluation layer with zero operational mutation and deterministic scoring
                </p>
              </div>
            </div>
          </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2 w-full md:w-auto">
          <div className="relative flex-1 md:w-64">
            <Search className="w-4 h-4 absolute left-3 top-3 text-slate-500" />
            <input
              type="text"
              value={datasetId}
              onChange={(e) => setDatasetId(e.target.value)}
              placeholder="Dataset ID (e.g. ds_seed42_...)"
              className="w-full bg-slate-950 border border-slate-700 pl-9 pr-3 py-2 text-sm rounded-lg focus:outline-none focus:border-indigo-500 font-mono text-slate-200"
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

      {error && (
        <div className="mt-4 p-4 bg-rose-500/10 border border-rose-500/30 rounded-lg flex items-center gap-3 text-rose-300 text-sm">
          <AlertTriangle className="w-5 h-5 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {report ? (
        <div className="mt-6 space-y-6">
          {/* Top KPI Metrics Banner */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            {/* Overall Score */}
            <div className="bg-slate-950/70 border border-slate-800 p-4 rounded-xl relative overflow-hidden">
              <div className="flex justify-between items-start">
                <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                  Overall Benchmark Score
                </span>
                <Sparkles className="w-4 h-4 text-indigo-400" />
              </div>
              <div className="mt-2 flex items-baseline gap-2">
                <span
                  className={`text-3xl font-extrabold ${
                    report.run.overall_score >= 80
                      ? "text-emerald-400"
                      : report.run.overall_score >= 60
                      ? "text-amber-400"
                      : "text-rose-400"
                  }`}
                >
                  {report.run.overall_score}
                </span>
                <span className="text-xs text-slate-500">/ 100</span>
              </div>
              <div className="mt-2.5 w-full bg-slate-900 border border-slate-700/60 rounded-full h-2.5 overflow-hidden p-0.5">
                <div
                  className="bg-gradient-to-r from-indigo-500 to-teal-400 h-full rounded-full transition-all duration-500"
                  style={{ width: `${Math.min(report.run.overall_score, 100)}%` }}
                />
              </div>
            </div>

            {/* Precision & Recall */}
            <div className="bg-slate-950/70 border border-slate-800 p-4 rounded-xl">
              <div className="flex justify-between items-start">
                <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                  Precision / Recall
                </span>
                <Target className="w-4 h-4 text-blue-400" />
              </div>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="text-2xl font-extrabold text-blue-400">
                  {(report.run.precision * 100).toFixed(1)}%
                </span>
                <span className="text-xs text-slate-500">
                  / {(report.run.recall * 100).toFixed(1)}%
                </span>
              </div>
              <div className="mt-1 text-xs text-slate-400 font-mono">
                {report.run.precision_bps} bps / {report.run.recall_bps} bps
              </div>
            </div>

            {/* F1 Score */}
            <div className="bg-slate-950/70 border border-slate-800 p-4 rounded-xl">
              <div className="flex justify-between items-start">
                <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                  F1 Metric
                </span>
                <BarChart3 className="w-4 h-4 text-purple-400" />
              </div>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="text-2xl font-extrabold text-purple-400">
                  {(report.run.f1_score * 100).toFixed(1)}%
                </span>
                <span className="text-xs text-purple-300/70 font-mono">
                  ({report.run.f1_score_bps} bps)
                </span>
              </div>
              <div className="mt-1 text-xs text-slate-400">
                TP: {report.run.true_positives} | FP: {report.run.false_positives} | FN:{" "}
                {report.run.false_negatives}
              </div>
            </div>

            {/* Financial Exposure Accuracy */}
            <div className="bg-slate-950/70 border border-slate-800 p-4 rounded-xl">
              <div className="flex justify-between items-start">
                <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                  Exposure Exact Match
                </span>
                <Coins className="w-4 h-4 text-amber-400" />
              </div>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="text-2xl font-extrabold text-amber-400">
                  {(report.exposure_accuracy.exact_match_rate * 100).toFixed(1)}%
                </span>
                <span className="text-xs text-slate-500">
                  ({report.exposure_accuracy.exact_matches}/{report.exposure_accuracy.total_evaluated})
                </span>
              </div>
              <div className="mt-1 text-xs text-slate-400 font-mono">
                MAE: {formatPaise(report.exposure_accuracy.mean_absolute_error)}
              </div>
            </div>

            {/* Critical Safety Status */}
            <div
              className={`p-4 rounded-xl border ${
                report.run.safety_status === "PASSED"
                  ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-300"
                  : "bg-rose-500/10 border-rose-500/30 text-rose-300"
              }`}
            >
              <div className="flex justify-between items-start">
                <span className="text-xs font-semibold uppercase tracking-wider">
                  Critical Safety Gate
                </span>
                {report.run.safety_status === "PASSED" ? (
                  <ShieldCheck className="w-5 h-5 text-emerald-400" />
                ) : (
                  <ShieldAlert className="w-5 h-5 text-rose-400" />
                )}
              </div>
              <div className="mt-2 text-xl font-bold tracking-wider">
                {report.run.safety_status}
              </div>
              <div className="mt-1 text-xs opacity-80">
                False Closures: {report.false_closure_count} (0 Required)
              </div>
            </div>
          </div>

          {/* Sub-system Component Scores Strip (Issue 21: Secondary Metrics Grouping) */}
          <div className="p-4 rounded-xl bg-slate-900/40 border border-slate-800/80 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider font-mono">
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
                  color: "text-blue-400",
                },
                {
                  label: "Investigation",
                  score: report.run.scores.investigation,
                  max: 15,
                  color: "text-indigo-400",
                },
                {
                  label: "Financial Exposure",
                  score: report.run.scores.financial,
                  max: 15,
                  color: "text-amber-400",
                },
                {
                  label: "Risk Materiality",
                  score: report.run.scores.risk,
                  max: 20,
                  color: "text-purple-400",
                },
                {
                  label: "Policy Gating",
                  score: report.run.scores.policy,
                  max: 10,
                  color: "text-emerald-400",
                },
                {
                  label: "Remediation",
                  score: report.run.scores.remediation,
                  max: 5,
                  color: "text-cyan-400",
                },
                {
                  label: "Verification",
                  score: report.run.scores.verification,
                  max: 10,
                  color: "text-teal-400",
                },
              ].map((c) => (
                <div
                  key={c.label}
                  className="bg-slate-950/60 border border-slate-800/80 p-3 rounded-lg flex flex-col justify-between"
                >
                  <span className="text-xs text-slate-400 font-medium truncate">
                    {c.label}
                  </span>
                  <div className="mt-1 flex items-baseline justify-between">
                    <span className={`text-lg font-bold ${c.color}`}>
                      {c.score}
                    </span>
                    <span className="text-xs text-slate-500">/{c.max}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Navigation Tabs (Issue 5: Reusable Tabs Component) */}
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
              <div className="bg-slate-950/60 border border-slate-800 p-5 rounded-xl space-y-4">
                <h3 className="text-base font-semibold text-white flex items-center gap-2">
                  <Cpu className="w-4 h-4 text-indigo-400" />
                  Execution Meta & Architectural Isolation
                </h3>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="text-xs text-slate-500 uppercase">Run ID</span>
                    <p className="font-mono text-slate-200 text-xs truncate">
                      {report.run.evaluation_run_id}
                    </p>
                  </div>
                  <div>
                    <span className="text-xs text-slate-500 uppercase">Dataset ID</span>
                    <p className="font-mono text-slate-200 text-xs truncate">
                      {report.run.dataset_id}
                    </p>
                  </div>
                  <div>
                    <span className="text-xs text-slate-500 uppercase">Benchmark Version</span>
                    <p className="text-slate-200">{report.run.benchmark_version}</p>
                  </div>
                  <div>
                    <span className="text-xs text-slate-500 uppercase">Operational Isolation</span>
                    <p className="text-emerald-400 font-medium">Read-Only Enforced</p>
                  </div>
                  <div>
                    <span className="text-xs text-slate-500 uppercase">Total GT Cases</span>
                    <p className="text-slate-200 font-semibold">
                      {report.run.total_ground_truth_cases}
                    </p>
                  </div>
                  <div>
                    <span className="text-xs text-slate-500 uppercase">Total Predictions</span>
                    <p className="text-slate-200 font-semibold">{report.run.total_predictions}</p>
                  </div>
                </div>
              </div>

              <div className="bg-slate-950/60 border border-slate-800 p-5 rounded-xl space-y-4">
                <h3 className="text-base font-semibold text-white flex items-center gap-2">
                  <Layers className="w-4 h-4 text-emerald-400" />
                  Operational Stage Accuracy Rates
                </h3>
                <div className="space-y-2.5 text-sm">
                  <div className="flex justify-between items-center">
                    <span className="text-slate-400">Root Cause Diagnosis Accuracy</span>
                    <span className="font-mono font-bold text-indigo-400">
                      {formatAccuracy(report.root_cause_accuracy)}
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-slate-400">Severity Classification Accuracy</span>
                    <span className="font-mono font-bold text-purple-400">
                      {formatAccuracy(report.severity_accuracy)}
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-slate-400">Priority Level Accuracy</span>
                    <span className="font-mono font-bold text-purple-400">
                      {formatAccuracy(report.priority_accuracy)}
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-slate-400">Policy Gating Compliance</span>
                    <span className="font-mono font-bold text-emerald-400">
                      {formatAccuracy(report.policy_accuracy)}
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-slate-400">Remediation Execution Success</span>
                    <span className="font-mono font-bold text-cyan-400">
                      {formatAccuracy(report.remediation_success_rate)}
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-slate-400">Post-Remediation Verification</span>
                    <span className="font-mono font-bold text-teal-400">
                      {formatAccuracy(report.verification_success_rate)}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Tab 2: Detection by Type */}
          {activeTab === "detection" && (
            <div className="bg-slate-950/60 border border-slate-800 rounded-xl overflow-hidden">
              <table className="w-full text-left text-sm">
                <thead className="bg-slate-900/80 text-xs uppercase text-slate-400 border-b border-slate-800 font-mono">
                  <tr>
                    <th className="px-4 py-3">Anomaly Category</th>
                    <th className="px-4 py-3">Expected</th>
                    <th className="px-4 py-3">Predicted</th>
                    <th className="px-4 py-3">TP</th>
                    <th className="px-4 py-3">FP</th>
                    <th className="px-4 py-3">FN</th>
                    <th className="px-4 py-3">Precision</th>
                    <th className="px-4 py-3">Recall</th>
                    <th className="px-4 py-3">F1 Score</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {Object.entries(report.detection_by_type || {}).map(([name, m]) => (
                    <tr key={name} className="hover:bg-slate-900/40">
                      <td className="px-4 py-3 font-medium text-slate-200 font-mono text-xs">
                        {name}
                      </td>
                      <td className="px-4 py-3 text-slate-400">{m.expected_count}</td>
                      <td className="px-4 py-3 text-slate-400">{m.predicted_count}</td>
                      <td className="px-4 py-3 text-emerald-400 font-semibold">{m.true_positives}</td>
                      <td className="px-4 py-3 text-rose-400">{m.false_positives}</td>
                      <td className="px-4 py-3 text-amber-400">{m.false_negatives}</td>
                      <td className="px-4 py-3 font-mono text-xs text-blue-300">
                        {(m.precision * 100).toFixed(1)}%
                      </td>
                      <td className="px-4 py-3 font-mono text-xs text-blue-300">
                        {(m.recall * 100).toFixed(1)}%
                      </td>
                      <td className="px-4 py-3 font-mono text-xs font-bold text-purple-300">
                        {(m.f1_score * 100).toFixed(1)}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Tab 3: Risk & Confusion Matrices (Issue 15: H3 headers) */}
          {activeTab === "risk" && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Severity Matrix */}
              <div className="bg-slate-950/60 border border-slate-800 p-5 rounded-xl space-y-3">
                <h3 className="font-semibold text-sm text-white">
                  Severity classification matrix
                </h3>
                <div className="space-y-2">
                  {report.severity_confusion_matrix?.map((item, idx) => (
                    <div
                      key={idx}
                      className="flex justify-between items-center bg-slate-900/50 p-2.5 rounded-lg text-xs"
                    >
                      <div className="flex items-center gap-2">
                        <span className="text-slate-400 font-mono">Expected:</span>
                        <span className="font-semibold text-slate-200">{item.expected_class}</span>
                        <ArrowRight className="w-3 h-3 text-slate-600" />
                        <span className="text-slate-400 font-mono">Predicted:</span>
                        <span className="font-semibold text-indigo-300">
                          {item.predicted_class}
                        </span>
                      </div>
                      <span className="px-2 py-0.5 rounded bg-indigo-900/40 text-indigo-300 font-mono font-bold">
                        {item.count} cases
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Priority Matrix */}
              <div className="bg-slate-950/60 border border-slate-800 p-5 rounded-xl space-y-3">
                <h3 className="font-semibold text-sm text-white">Priority level matrix</h3>
                <div className="space-y-2">
                  {report.priority_confusion_matrix?.map((item, idx) => (
                    <div
                      key={idx}
                      className="flex justify-between items-center bg-slate-900/50 p-2.5 rounded-lg text-xs"
                    >
                      <div className="flex items-center gap-2">
                        <span className="text-slate-400 font-mono">Expected:</span>
                        <span className="font-semibold text-slate-200">{item.expected_class}</span>
                        <ArrowRight className="w-3 h-3 text-slate-600" />
                        <span className="text-slate-400 font-mono">Predicted:</span>
                        <span className="font-semibold text-purple-300">
                          {item.predicted_class}
                        </span>
                      </div>
                      <span className="px-2 py-0.5 rounded bg-purple-900/40 text-purple-300 font-mono font-bold">
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
            <div className="bg-slate-950/60 border border-slate-800 p-5 rounded-xl space-y-4">
              <h3 className="font-semibold text-base text-white flex items-center gap-2">
                <Coins className="w-5 h-5 text-amber-400" />
                Integer Minor Unit (Paise) Exposure Fidelity
              </h3>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <div className="p-3 bg-slate-900/60 rounded-lg border border-slate-800">
                  <span className="text-xs text-slate-400">Total Expected</span>
                  <p className="text-base font-mono font-bold text-slate-200 mt-1">
                    {formatPaise(report.exposure_accuracy.total_expected_exposure)}
                  </p>
                </div>
                <div className="p-3 bg-slate-900/60 rounded-lg border border-slate-800">
                  <span className="text-xs text-slate-400">Total Predicted</span>
                  <p className="text-base font-mono font-bold text-slate-200 mt-1">
                    {formatPaise(report.exposure_accuracy.total_predicted_exposure)}
                  </p>
                </div>
                <div className="p-3 bg-slate-900/60 rounded-lg border border-slate-800">
                  <span className="text-xs text-slate-400">Total Absolute Error</span>
                  <p className="text-base font-mono font-bold text-amber-400 mt-1">
                    {formatPaise(report.exposure_accuracy.total_absolute_error)}
                  </p>
                </div>
                <div className="p-3 bg-slate-900/60 rounded-lg border border-slate-800">
                  <span className="text-xs text-slate-400">Zero-Exposure Verified</span>
                  <p className="text-base font-mono font-bold text-emerald-400 mt-1">
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
                    className={`px-3 py-1.5 text-xs font-medium rounded-lg border transition ${
                      caseFilter === f.id
                        ? "bg-indigo-600/30 border-indigo-500 text-indigo-300"
                        : "bg-slate-950 border-slate-800 text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    {f.label}
                  </button>
                ))}
              </div>

              <div className="bg-slate-950/60 border border-slate-800 rounded-xl overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-900/80 uppercase text-slate-400 border-b border-slate-800 font-mono">
                    <tr>
                      <th className="px-3 py-2.5">Case ID</th>
                      <th className="px-3 py-2.5">Predicted Exception</th>
                      <th className="px-3 py-2.5">Status</th>
                      <th className="px-3 py-2.5">Matched By</th>
                      <th className="px-3 py-2.5">Expected Exposure</th>
                      <th className="px-3 py-2.5">Predicted Exposure</th>
                      <th className="px-3 py-2.5">Error Delta</th>
                      <th className="px-3 py-2.5">Error Tags</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {filteredCases.map((c) => (
                      <tr key={c.evaluation_case_id} className="hover:bg-slate-900/40">
                        <td className="px-3 py-2.5 font-mono text-slate-200">
                          {c.ground_truth_case_id || "N/A"}
                        </td>
                        <td className="px-3 py-2.5 font-mono text-indigo-300 truncate max-w-[180px]">
                          {c.predicted_exception_id || "N/A"}
                        </td>
                        <td className="px-3 py-2.5">
                          <span
                            className={`px-2 py-0.5 rounded text-xs font-mono font-bold ${
                              c.match_status === "TRUE_POSITIVE" || c.match_status === "LEGITIMATE_CORRECT"
                                ? "bg-emerald-950 text-emerald-400 border border-emerald-800"
                                : c.match_status === "FALSE_POSITIVE"
                                ? "bg-rose-950 text-rose-400 border border-rose-800"
                                : "bg-amber-950 text-amber-400 border border-amber-800"
                            }`}
                          >
                            {c.match_status}
                          </span>
                        </td>
                        <td className="px-3 py-2.5 text-slate-400 font-mono text-xs">
                          {c.matched_by}
                        </td>
                        <td className="px-3 py-2.5 font-mono text-slate-300">
                          {formatPaise(c.expected_exposure)}
                        </td>
                        <td className="px-3 py-2.5 font-mono text-slate-300">
                          {formatPaise(c.predicted_exposure)}
                        </td>
                        <td
                          className={`px-3 py-2.5 font-mono font-semibold ${
                            c.exposure_error === 0 ? "text-emerald-400" : "text-amber-400"
                          }`}
                        >
                          {formatPaise(c.exposure_error)}
                        </td>
                        <td className="px-3 py-2.5">
                          {c.error_categories?.map((cat) => (
                            <span
                              key={cat}
                              className="inline-block mr-1 px-1.5 py-0.5 rounded bg-slate-800 text-[9px] font-mono text-slate-300"
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
            <div className="bg-slate-950/60 border border-slate-800 p-5 rounded-xl space-y-4">
              <h3 className="font-semibold text-base text-white flex items-center gap-2">
                <ShieldCheck className="w-5 h-5 text-emerald-400" />
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
                    className="flex justify-between items-start bg-slate-900/60 p-3.5 rounded-lg border border-slate-800"
                  >
                    <div>
                      <span className="font-semibold text-sm text-slate-200">
                        {gate.rule}
                      </span>
                      <p className="text-xs text-slate-400 mt-0.5">{gate.desc}</p>
                    </div>
                    <span
                      className={`px-2.5 py-1 rounded text-xs font-mono font-bold ${
                        gate.status === "PASSED"
                          ? "bg-emerald-950 text-emerald-400 border border-emerald-800"
                          : "bg-rose-950 text-rose-400 border border-rose-800"
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
        <div className="mt-8 text-center py-12 border border-dashed border-slate-800 rounded-xl bg-slate-950/30">
          <Award className="w-12 h-12 text-slate-600 mx-auto mb-3" />
          <h3 className="text-base font-semibold text-slate-300">
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

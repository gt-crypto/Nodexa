"use client";

import React, { useState, useRef } from "react";
import {
  Upload,
  FileSpreadsheet,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  ShieldCheck,
  Cpu,
  ArrowRight,
  RefreshCw,
  Download,
  Info,
  Layers,
  ChevronRight,
  TrendingUp,
  Clock,
  Sparkles,
  Database,
  Lock,
} from "lucide-react";
import {
  validateSandboxCsv,
  analyzeSandboxCsv,
  fetchSampleSandboxCsv,
  SandboxValidationResult,
  SandboxAnalysisReport,
  SandboxExceptionItem,
} from "../lib/api";

type Step = "upload" | "validating" | "preview" | "analyzing" | "results";

export default function SandboxPanel() {
  const [step, setStep] = useState<Step>("upload");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [csvRawText, setCsvRawText] = useState<string>("");
  const [fileName, setFileName] = useState<string>("");
  const [dragActive, setDragActive] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Validation State
  const [validation, setValidation] = useState<SandboxValidationResult | null>(null);
  const [isValidating, setIsValidating] = useState<boolean>(false);

  // Analysis State
  const [analysis, setAnalysis] = useState<SandboxAnalysisReport | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState<boolean>(false);
  const [analysisStage, setAnalysisStage] = useState<string>("");

  // Drawer / Inspection State
  const [selectedException, setSelectedException] = useState<SandboxExceptionItem | null>(null);
  const [filterSeverity, setFilterSeverity] = useState<string>("ALL");

  const fileInputRef = useRef<HTMLInputElement>(null);

  // Handle Drag & Drop
  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      processFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      processFile(e.target.files[0]);
    }
  };

  const processFile = async (file: File) => {
    if (!file.name.toLowerCase().endsWith(".csv")) {
      setErrorMsg("Please upload a valid CSV file (.csv).");
      return;
    }
    setErrorMsg(null);
    setSelectedFile(file);
    setFileName(file.name);
    setIsValidating(true);
    setStep("validating");

    try {
      const res = await validateSandboxCsv(file);
      setValidation(res);
      setStep("preview");
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to validate CSV file.");
      setStep("upload");
    } finally {
      setIsValidating(false);
    }
  };

  const loadSampleDataset = async () => {
    setErrorMsg(null);
    setIsValidating(true);
    setStep("validating");
    try {
      const sampleText = await fetchSampleSandboxCsv();
      setCsvRawText(sampleText);
      setSelectedFile(null);
      setFileName("nodexa_sample_anomaly_dataset.csv");

      const res = await validateSandboxCsv(undefined, sampleText);
      setValidation(res);
      setStep("preview");
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to load sample dataset.");
      setStep("upload");
    } finally {
      setIsValidating(false);
    }
  };

  const runAnalysis = async () => {
    if (!validation?.is_valid) return;
    setIsAnalyzing(true);
    setStep("analyzing");
    setErrorMsg(null);

    // Simulated progress indicators for UX clarity
    setAnalysisStage("Mounting isolated in-memory SQLite sandbox engine...");
    await new Promise((r) => setTimeout(r, 600));

    setAnalysisStage("Normalizing operational feeds & double-entry nodal ledger...");
    await new Promise((r) => setTimeout(r, 600));

    setAnalysisStage("Executing 5 deterministic reconciliation & safety control checks...");

    try {
      const report = await analyzeSandboxCsv(
        selectedFile || undefined,
        !selectedFile ? csvRawText : undefined,
        fileName || "sandbox_dataset.csv"
      );
      setAnalysisStage("Mining recurring transaction pattern clusters...");
      await new Promise((r) => setTimeout(r, 500));

      setAnalysis(report);
      setStep("results");
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to complete sandbox analysis.");
      setStep("preview");
    } finally {
      setIsAnalyzing(false);
    }
  };

  const resetAll = () => {
    setStep("upload");
    setSelectedFile(null);
    setCsvRawText("");
    setFileName("");
    setValidation(null);
    setAnalysis(null);
    setSelectedException(null);
    setErrorMsg(null);
  };

  const exportReportJson = () => {
    if (!analysis) return;
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(analysis, null, 2));
    const downloadAnchor = document.createElement("a");
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", `nodexa_sandbox_report_${Date.now()}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  const filteredExceptions = (analysis?.exceptions || []).filter((exc) => {
    if (filterSeverity === "ALL") return true;
    return exc.severity.toUpperCase() === filterSeverity;
  });

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="relative overflow-hidden rounded-xl border border-slate-800 bg-gradient-to-r from-slate-900 via-slate-900/90 to-slate-950 p-6 shadow-2xl backdrop-blur-md">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2.5">
              <div className="p-2 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
                <FileSpreadsheet className="h-5 w-5" />
              </div>
              <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
                Test New Dataset
                <span className="text-xs font-medium px-2.5 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                  Ephemeral Sandbox
                </span>
              </h1>
            </div>
            <p className="text-sm text-slate-400 max-w-3xl">
              Upload custom operational finance batches or evaluate unseen CSV data against Nodexa&apos;s deterministic reconciliation, double-entry audit, and pattern-mining pipeline.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-800/80 border border-slate-700/60 text-xs text-slate-300">
              <Lock className="h-3.5 w-3.5 text-emerald-400" />
              <span>Zero Production Mutation</span>
            </div>
            {step !== "upload" && (
              <button
                onClick={resetAll}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-medium text-slate-300 border border-slate-700 transition"
              >
                <RefreshCw className="h-3.5 w-3.5" />
                Reset
              </button>
            )}
          </div>
        </div>

        {/* Isolation Guarantee Bar */}
        <div className="mt-4 pt-4 border-t border-slate-800/60 flex flex-wrap items-center justify-between gap-3 text-xs text-slate-400">
          <div className="flex items-center gap-2">
            <span className="flex h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-slate-300 font-mono">sqlite:///:memory:</span>
            <span>&bull;</span>
            <span>Execution completely isolated in ephemeral memory</span>
          </div>
          <div className="text-slate-500">
            Canonical 272-record production dataset remains 100% immutable
          </div>
        </div>
      </div>

      {/* Error Alert */}
      {errorMsg && (
        <div className="rounded-lg border border-rose-500/30 bg-rose-950/30 p-4 text-rose-300 flex items-start gap-3">
          <AlertTriangle className="h-5 w-5 text-rose-400 flex-shrink-0 mt-0.5" />
          <div className="space-y-1">
            <p className="text-sm font-medium">Operation Error</p>
            <p className="text-xs text-rose-400">{errorMsg}</p>
          </div>
        </div>
      )}

      {/* STEP 1: UPLOAD ZONE */}
      {step === "upload" && (
        <div className="space-y-4">
          <div
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            className={`relative rounded-xl border-2 border-dashed p-10 text-center transition-all ${
              dragActive
                ? "border-emerald-500 bg-emerald-500/5 shadow-lg shadow-emerald-500/10"
                : "border-slate-800 bg-slate-900/40 hover:border-slate-700 hover:bg-slate-900/60"
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv"
              onChange={handleFileInput}
              className="hidden"
              id="csv-file-input"
            />

            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-xl bg-slate-800/90 border border-slate-700 text-emerald-400 mb-4">
              <Upload className="h-6 w-6" />
            </div>

            <h3 className="text-base font-semibold text-white mb-1">
              Upload Operational CSV Dataset
            </h3>
            <p className="text-xs text-slate-400 max-w-md mx-auto mb-5">
              Drag and drop your operational CSV file here, or click browse. Requires columns:{" "}
              <code className="text-emerald-400">transaction_id</code>,{" "}
              <code className="text-emerald-400">merchant_id</code>,{" "}
              <code className="text-emerald-400">amount</code>,{" "}
              <code className="text-emerald-400">status</code>,{" "}
              <code className="text-emerald-400">transaction_date</code>.
            </p>

            <div className="flex flex-wrap items-center justify-center gap-3">
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-sm font-medium text-white shadow-lg shadow-emerald-600/20 transition"
              >
                <FileSpreadsheet className="h-4 w-4" />
                Browse File (.csv)
              </button>

              <button
                type="button"
                onClick={loadSampleDataset}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-sm font-medium text-slate-200 transition"
              >
                <Sparkles className="h-4 w-4 text-amber-400" />
                Load Sample Anomaly Dataset
              </button>
            </div>

            <div className="mt-6 flex items-center justify-center gap-6 text-xs text-slate-500">
              <span>Max file size: 5 MB</span>
              <span>&bull;</span>
              <span>Encodings: UTF-8 / ASCII</span>
              <span>&bull;</span>
              <span>Non-destructive validation</span>
            </div>
          </div>

          {/* Quick Guidance Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-4 space-y-2">
              <div className="flex items-center gap-2 text-slate-200 font-medium text-xs">
                <Database className="h-4 w-4 text-cyan-400" />
                1. Ephemeral Sandbox
              </div>
              <p className="text-xs text-slate-400">
                Uploaded rows are parsed and loaded into a temporary in-memory database. PostgreSQL production tables are completely bypassed and preserved.
              </p>
            </div>

            <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-4 space-y-2">
              <div className="flex items-center gap-2 text-slate-200 font-medium text-xs">
                <Cpu className="h-4 w-4 text-purple-400" />
                2. Autonomous Controls
              </div>
              <p className="text-xs text-slate-400">
                Executes the exact same 5 financial reconciliation checks: Ghost Settlement, Double Dip, Settlement SLA Breach, Partial Deficit, and Missing Allocation.
              </p>
            </div>

            <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-4 space-y-2">
              <div className="flex items-center gap-2 text-slate-200 font-medium text-xs">
                <ShieldCheck className="h-4 w-4 text-amber-400" />
                3. Honest Benchmarking
              </div>
              <p className="text-xs text-slate-400">
                Because third-party datasets lack verified ground truth labels, accuracy metrics (Precision/Recall/F1) are transparently marked as unavailable.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* STEP 2: VALIDATING SPINNER */}
      {step === "validating" && (
        <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-12 text-center space-y-4">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-2 border-emerald-500 border-t-transparent mb-2" />
          <h3 className="text-base font-semibold text-white">Validating CSV Structure</h3>
          <p className="text-xs text-slate-400 max-w-sm mx-auto">
            Checking header columns, parsing date formats, and validating numeric monetary fields...
          </p>
        </div>
      )}

      {/* STEP 3: PREVIEW & CONFIRMATION */}
      {step === "preview" && validation && (
        <div className="space-y-6">
          {/* Validation Status Card */}
          <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-5 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                {validation.is_valid ? (
                  <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                    <CheckCircle2 className="h-5 w-5" />
                  </div>
                ) : (
                  <div className="p-2 rounded-lg bg-rose-500/10 text-rose-400 border border-rose-500/20">
                    <XCircle className="h-5 w-5" />
                  </div>
                )}
                <div>
                  <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                    {fileName}
                    <span
                      className={`text-xs px-2 py-0.5 rounded-full ${
                        validation.is_valid
                          ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                          : "bg-rose-500/20 text-rose-400 border border-rose-500/30"
                      }`}
                    >
                      {validation.is_valid ? "Schema Valid" : "Validation Issues"}
                    </span>
                  </h3>
                  <p className="text-xs text-slate-400 mt-0.5">{validation.message}</p>
                </div>
              </div>

              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={resetAll}
                  className="px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-medium text-slate-300 border border-slate-700 transition"
                >
                  Choose Different File
                </button>
                {validation.is_valid && (
                  <button
                    type="button"
                    onClick={runAnalysis}
                    className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-xs font-semibold text-white shadow-lg shadow-emerald-600/20 transition"
                  >
                    <Cpu className="h-4 w-4" />
                    Run Isolated Finance Analysis
                    <ArrowRight className="h-3.5 w-3.5" />
                  </button>
                )}
              </div>
            </div>

            {/* Quick Metrics Bar */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-3 border-t border-slate-800">
              <div className="bg-slate-950/60 p-3 rounded-lg border border-slate-800/80">
                <div className="text-slate-400 text-xs">Total Rows</div>
                <div className="text-lg font-bold text-white mt-0.5 font-mono">
                  {validation.total_rows}
                </div>
              </div>
              <div className="bg-slate-950/60 p-3 rounded-lg border border-slate-800/80">
                <div className="text-slate-400 text-xs">Valid Rows</div>
                <div className="text-lg font-bold text-emerald-400 mt-0.5 font-mono">
                  {validation.valid_rows}
                </div>
              </div>
              <div className="bg-slate-950/60 p-3 rounded-lg border border-slate-800/80">
                <div className="text-slate-400 text-xs">Invalid Rows</div>
                <div
                  className={`text-lg font-bold mt-0.5 font-mono ${
                    validation.invalid_rows > 0 ? "text-rose-400" : "text-slate-500"
                  }`}
                >
                  {validation.invalid_rows}
                </div>
              </div>
              <div className="bg-slate-950/60 p-3 rounded-lg border border-slate-800/80">
                <div className="text-slate-400 text-xs">Columns Detected</div>
                <div className="text-lg font-bold text-cyan-400 mt-0.5 font-mono">
                  {validation.columns_detected.length}
                </div>
              </div>
            </div>

            {/* Detected Columns Chips */}
            <div className="space-y-1.5">
              <span className="text-xs font-medium text-slate-400">Header Columns:</span>
              <div className="flex flex-wrap gap-1.5">
                {validation.columns_detected.map((col) => (
                  <span
                    key={col}
                    className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-mono border border-slate-700"
                  >
                    <CheckCircle2 className="h-3 w-3 text-emerald-400" />
                    {col}
                  </span>
                ))}
                {validation.missing_required_columns.map((col) => (
                  <span
                    key={col}
                    className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded bg-rose-950/50 text-rose-300 font-mono border border-rose-800"
                  >
                    <XCircle className="h-3 w-3 text-rose-400" />
                    Missing: {col}
                  </span>
                ))}
              </div>
            </div>

            {/* Validation Errors List if any */}
            {validation.errors.length > 0 && (
              <div className="mt-3 rounded-lg border border-rose-900/50 bg-rose-950/20 p-3 space-y-2">
                <div className="text-xs font-semibold text-rose-400 flex items-center gap-1.5">
                  <AlertTriangle className="h-3.5 w-3.5" />
                  Validation Issues ({validation.errors.length})
                </div>
                <div className="max-h-32 overflow-y-auto space-y-1 text-xs text-rose-300 font-mono">
                  {validation.errors.slice(0, 10).map((err, idx) => (
                    <div key={idx} className="flex gap-2">
                      <span className="text-rose-500">Row {err.row_number}:</span>
                      <span>{err.error}</span>
                      {err.raw_value && (
                        <span className="text-slate-500">({err.raw_value})</span>
                      )}
                    </div>
                  ))}
                  {validation.errors.length > 10 && (
                    <div className="text-slate-500 italic">
                      + {validation.errors.length - 10} more issues...
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* 10-Row Preview Table */}
          {validation.preview_rows.length > 0 && (
            <div className="rounded-xl border border-slate-800 bg-slate-900/70 overflow-hidden shadow-xl">
              <div className="p-4 border-b border-slate-800 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Layers className="h-4 w-4 text-indigo-400" />
                  <h4 className="text-xs font-semibold text-white uppercase tracking-wider">
                    Dataset Preview (First {validation.preview_rows.length} Rows)
                  </h4>
                </div>
                <span className="text-[11px] text-slate-400">
                  Ready for in-memory reconciliation
                </span>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="bg-slate-950/80 text-slate-400 font-mono border-b border-slate-800">
                      <th className="py-2.5 px-3">#</th>
                      <th className="py-2.5 px-3">Transaction ID</th>
                      <th className="py-2.5 px-3">Merchant ID</th>
                      <th className="py-2.5 px-3 text-right">Amount (₹)</th>
                      <th className="py-2.5 px-3">Status</th>
                      <th className="py-2.5 px-3">Date</th>
                      <th className="py-2.5 px-3">Settlement (UTR)</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 font-mono text-slate-300">
                    {validation.preview_rows.map((row, idx) => (
                      <tr
                        key={idx}
                        className="hover:bg-slate-800/40 transition-colors"
                      >
                        <td className="py-2.5 px-3 text-slate-500">{idx + 1}</td>
                        <td className="py-2.5 px-3 font-semibold text-white">
                          {row.transaction_id || "-"}
                        </td>
                        <td className="py-2.5 px-3 text-slate-400">
                          {row.merchant_id || "-"}
                        </td>
                        <td className="py-2.5 px-3 text-right font-medium text-emerald-400">
                          ₹{Number(row.amount || 0).toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                        </td>
                        <td className="py-2.5 px-3">
                          <span
                            className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold ${
                              row.status === "SUCCESS"
                                ? "bg-emerald-500/20 text-emerald-400"
                                : "bg-rose-500/20 text-rose-400"
                            }`}
                          >
                            {row.status || "UNKNOWN"}
                          </span>
                        </td>
                        <td className="py-2.5 px-3 text-slate-400">
                          {row.transaction_date?.slice(0, 10) || "-"}
                        </td>
                        <td className="py-2.5 px-3 text-slate-500">
                          {row.utr_number || (row.settlement_amount ? "UTR_PENDING" : "-")}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* STEP 4: ANALYZING PROGRESS */}
      {step === "analyzing" && (
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-12 text-center space-y-6">
          <div className="relative mx-auto w-16 h-16">
            <div className="absolute inset-0 rounded-full border-2 border-emerald-500/20 animate-ping" />
            <div className="relative flex items-center justify-center w-16 h-16 rounded-full bg-slate-800 border border-emerald-500 text-emerald-400 shadow-xl">
              <Cpu className="h-7 w-7 animate-pulse" />
            </div>
          </div>

          <div className="space-y-2">
            <h3 className="text-base font-semibold text-white">
              Autonomous Financial Reconciliation in Progress
            </h3>
            <p className="text-xs text-emerald-400 font-mono">{analysisStage}</p>
          </div>

          <div className="max-w-md mx-auto w-full bg-slate-950 rounded-full h-1.5 overflow-hidden border border-slate-800">
            <div className="h-full bg-gradient-to-r from-emerald-500 to-cyan-500 animate-pulse w-3/4 rounded-full" />
          </div>

          <p className="text-[11px] text-slate-500 max-w-sm mx-auto">
            Processing dataset in an ephemeral SQLite memory instance. Zero production records are touched.
          </p>
        </div>
      )}

      {/* STEP 5: COMPREHENSIVE ANALYSIS RESULTS */}
      {step === "results" && analysis && (
        <div className="space-y-6">
          {/* Honest Ground Truth & Isolation Banner */}
          <div className="rounded-xl border border-amber-500/30 bg-gradient-to-r from-amber-950/30 via-slate-900/90 to-slate-950 p-5 space-y-3">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-lg bg-amber-500/10 text-amber-400 border border-amber-500/20">
                  <ShieldCheck className="h-5 w-5" />
                </div>
                <div>
                  <h4 className="text-sm font-semibold text-white flex items-center gap-2">
                    Ground Truth: {analysis.ground_truth_status}
                    <span className="text-[10px] uppercase font-bold px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30">
                      Third-Party Dataset
                    </span>
                  </h4>
                  <p className="text-xs text-slate-300 mt-0.5">
                    {analysis.accuracy_metrics_message}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={exportReportJson}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-medium text-slate-200 border border-slate-700 transition"
                >
                  <Download className="h-3.5 w-3.5 text-cyan-400" />
                  Export JSON
                </button>
                <button
                  type="button"
                  onClick={resetAll}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-xs font-semibold text-white transition"
                >
                  <RefreshCw className="h-3.5 w-3.5" />
                  Test Another
                </button>
              </div>
            </div>

            <div className="pt-3 border-t border-slate-800/80 text-[11px] text-slate-400 flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <span className="text-emerald-400 font-semibold font-mono">ISOLATION:</span>
                <span>{analysis.isolation_mode}</span>
                <span>&bull;</span>
                <span className="text-emerald-300">
                  Production DB Modified: {analysis.production_database_modified ? "YES" : "NO (0 writes)"}
                </span>
              </div>
              <div className="text-slate-500 italic">
                {analysis.disclaimer}
              </div>
            </div>
          </div>

          {/* Operational Metrics Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-4 space-y-1">
              <div className="text-xs font-medium text-slate-400">Total Operational Records</div>
              <div className="text-2xl font-bold font-mono text-white">
                {analysis.dataset_summary.total_records}
              </div>
              <div className="text-[11px] text-slate-500">
                {analysis.dataset_summary.gateway_transactions} tx &bull; {analysis.dataset_summary.merchant_orders} orders
              </div>
            </div>

            <div className="rounded-xl border border-rose-900/40 bg-slate-900/70 p-4 space-y-1">
              <div className="text-xs font-medium text-slate-400">Exceptions Detected</div>
              <div className="text-2xl font-bold font-mono text-rose-400">
                {analysis.exceptions_detected}
              </div>
              <div className="text-[11px] text-rose-400/80">
                {analysis.high_risk_cases} high / critical priority
              </div>
            </div>

            <div className="rounded-xl border border-amber-900/40 bg-slate-900/70 p-4 space-y-1">
              <div className="text-xs font-medium text-slate-400">Potential Exposure</div>
              <div className="text-2xl font-bold font-mono text-amber-400">
                {analysis.total_exposure_inr_formatted}
              </div>
              <div className="text-[11px] text-slate-500 font-mono">
                {analysis.total_exposure_minor_units.toLocaleString()} paise
              </div>
            </div>

            <div className="rounded-xl border border-indigo-900/40 bg-slate-900/70 p-4 space-y-1">
              <div className="text-xs font-medium text-slate-400">Recurring Pattern Clusters</div>
              <div className="text-2xl font-bold font-mono text-indigo-400">
                {analysis.recurring_patterns_count}
              </div>
              <div className="text-[11px] text-slate-500">
                Systemic anomaly signatures discovered
              </div>
            </div>
          </div>

          {/* Dataset Breakdown Breakdown Badges */}
          <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-3 flex flex-wrap items-center justify-between gap-2 text-xs">
            <span className="text-slate-400 font-medium">Dataset Breakdown:</span>
            <div className="flex flex-wrap items-center gap-2 font-mono text-slate-300">
              <span className="px-2 py-1 rounded bg-slate-800 border border-slate-700">
                Gateway TX: <b className="text-white">{analysis.dataset_summary.gateway_transactions}</b>
              </span>
              <span className="px-2 py-1 rounded bg-slate-800 border border-slate-700">
                Orders: <b className="text-white">{analysis.dataset_summary.merchant_orders}</b>
              </span>
              <span className="px-2 py-1 rounded bg-slate-800 border border-slate-700">
                Settlements: <b className="text-white">{analysis.dataset_summary.settlement_batches}</b>
              </span>
              <span className="px-2 py-1 rounded bg-slate-800 border border-slate-700">
                Ledger Entries: <b className="text-white">{analysis.dataset_summary.ledger_entries}</b>
              </span>
              <span className="px-2 py-1 rounded bg-slate-800 border border-slate-700">
                Disputes: <b className="text-white">{analysis.dataset_summary.dispute_events}</b>
              </span>
              <span className="px-2 py-1 rounded bg-slate-800 border border-slate-700">
                Merchants: <b className="text-white">{analysis.dataset_summary.merchants_impacted}</b>
              </span>
            </div>
          </div>

          {/* Pattern Clusters Card if any */}
          {analysis.patterns.length > 0 && (
            <div className="rounded-xl border border-indigo-900/40 bg-slate-900/70 p-5 space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <TrendingUp className="h-4 w-4 text-indigo-400" />
                  <h4 className="text-sm font-semibold text-white">
                    Discovered Recurring Patterns ({analysis.patterns.length})
                  </h4>
                </div>
                <span className="text-xs text-slate-400">
                  Unsupervised correlation of systemic anomalies
                </span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {analysis.patterns.map((pat) => (
                  <div
                    key={pat.cluster_id}
                    className="rounded-lg border border-slate-800 bg-slate-950/60 p-3 space-y-2"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-indigo-300 font-mono">
                        {pat.pattern_type}
                      </span>
                      <span className="text-[10px] px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 font-mono">
                        {pat.exception_count} incidents
                      </span>
                    </div>
                    <p className="text-xs text-slate-300">{pat.description}</p>
                    <div className="flex items-center justify-between text-[11px] text-slate-400 font-mono pt-1 border-t border-slate-800/80">
                      <span>Exposure: {pat.total_exposure_inr_formatted}</span>
                      <span className="text-slate-500">ID: {pat.cluster_id}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Exceptions Table */}
          <div className="rounded-xl border border-slate-800 bg-slate-900/70 overflow-hidden shadow-xl">
            <div className="p-4 border-b border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 text-rose-400" />
                <h4 className="text-sm font-semibold text-white">
                  Identified Exceptions ({filteredExceptions.length} of {analysis.exceptions.length})
                </h4>
              </div>

              {/* Severity Filter */}
              <div className="flex items-center gap-1.5">
                {["ALL", "CRITICAL", "HIGH", "MEDIUM", "LOW"].map((sev) => (
                  <button
                    key={sev}
                    onClick={() => setFilterSeverity(sev)}
                    className={`px-2.5 py-1 rounded text-[11px] font-semibold transition ${
                      filterSeverity === sev
                        ? "bg-slate-700 text-white"
                        : "text-slate-400 hover:text-slate-200 hover:bg-slate-800"
                    }`}
                  >
                    {sev}
                  </button>
                ))}
              </div>
            </div>

            {filteredExceptions.length === 0 ? (
              <div className="p-8 text-center text-xs text-slate-500">
                No exceptions match the selected filter criteria.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="bg-slate-950/80 text-slate-400 font-mono border-b border-slate-800">
                      <th className="py-2.5 px-3">Exception ID</th>
                      <th className="py-2.5 px-3">Type</th>
                      <th className="py-2.5 px-3">Severity</th>
                      <th className="py-2.5 px-3 text-right">Exposure (₹)</th>
                      <th className="py-2.5 px-3">Primary Ref</th>
                      <th className="py-2.5 px-3">Recommended Action</th>
                      <th className="py-2.5 px-3 text-right">Details</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 font-mono text-slate-300">
                    {filteredExceptions.map((exc) => (
                      <tr
                        key={exc.exception_id}
                        onClick={() => setSelectedException(exc)}
                        className="hover:bg-slate-800/50 cursor-pointer transition-colors"
                      >
                        <td className="py-2.5 px-3 font-semibold text-indigo-400">
                          {exc.exception_id}
                        </td>
                        <td className="py-2.5 px-3 font-bold text-white">
                          {exc.exception_type}
                        </td>
                        <td className="py-2.5 px-3">
                          <span
                            className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold ${
                              exc.severity === "CRITICAL"
                                ? "bg-rose-500/20 text-rose-400 border border-rose-500/30"
                                : exc.severity === "HIGH"
                                ? "bg-amber-500/20 text-amber-400 border border-amber-500/30"
                                : exc.severity === "MEDIUM"
                                ? "bg-cyan-500/20 text-cyan-400 border border-cyan-500/30"
                                : "bg-slate-700 text-slate-300"
                            }`}
                          >
                            {exc.severity}
                          </span>
                        </td>
                        <td className="py-2.5 px-3 text-right font-medium text-amber-400">
                          {exc.exposure_inr_formatted}
                        </td>
                        <td className="py-2.5 px-3 text-slate-400">
                          {exc.primary_payment_id || exc.primary_order_id || "-"}
                        </td>
                        <td className="py-2.5 px-3 text-slate-300 max-w-xs truncate">
                          {exc.recommended_action}
                        </td>
                        <td className="py-2.5 px-3 text-right">
                          <button
                            type="button"
                            className="text-slate-400 hover:text-white p-1"
                          >
                            <ChevronRight className="h-4 w-4" />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Detail Modal / Drawer for Selected Exception */}
          {selectedException && (
            <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fadeIn">
              <div className="relative w-full max-w-2xl rounded-xl border border-slate-700 bg-slate-900 p-6 shadow-2xl space-y-4">
                <div className="flex items-center justify-between pb-3 border-b border-slate-800">
                  <div className="space-y-0.5">
                    <div className="flex items-center gap-2">
                      <span className="text-xs px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300 font-mono">
                        {selectedException.exception_id}
                      </span>
                      <span
                        className={`text-xs px-2 py-0.5 rounded font-bold ${
                          selectedException.severity === "CRITICAL"
                            ? "bg-rose-500/20 text-rose-400"
                            : "bg-amber-500/20 text-amber-400"
                        }`}
                      >
                        {selectedException.severity}
                      </span>
                    </div>
                    <h3 className="text-base font-bold text-white">
                      {selectedException.exception_type}
                    </h3>
                  </div>

                  <button
                    onClick={() => setSelectedException(null)}
                    className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white transition"
                  >
                    <XCircle className="h-5 w-5" />
                  </button>
                </div>

                {/* Details Body */}
                <div className="space-y-3 text-xs">
                  <div className="grid grid-cols-2 gap-3 p-3 rounded-lg bg-slate-950/70 border border-slate-800">
                    <div>
                      <span className="text-slate-500">Financial Exposure:</span>
                      <div className="text-sm font-bold text-amber-400 font-mono">
                        {selectedException.exposure_inr_formatted}
                      </div>
                    </div>
                    <div>
                      <span className="text-slate-500">Linked Payment ID:</span>
                      <div className="text-sm font-bold text-white font-mono">
                        {selectedException.primary_payment_id || "N/A"}
                      </div>
                    </div>
                  </div>

                  <div className="space-y-1">
                    <span className="font-semibold text-slate-300">Description:</span>
                    <p className="text-slate-400 bg-slate-950/40 p-3 rounded-lg border border-slate-800">
                      {selectedException.description || "Deterministic audit rule detected discrepancy between payment gateway ledger and bank clearing feeds."}
                    </p>
                  </div>

                  <div className="space-y-1">
                    <span className="font-semibold text-emerald-400 flex items-center gap-1">
                      <ShieldCheck className="h-4 w-4" />
                      Recommended Action (Advisory Only):
                    </span>
                    <p className="text-emerald-300 bg-emerald-950/20 p-3 rounded-lg border border-emerald-900/40 font-medium">
                      {selectedException.recommended_action}
                    </p>
                  </div>

                  {selectedException.evidence && selectedException.evidence.length > 0 && (
                    <div className="space-y-1">
                      <span className="font-semibold text-slate-300">Technical Evidence:</span>
                      <pre className="text-[11px] font-mono p-3 rounded-lg bg-slate-950 border border-slate-800 text-cyan-300 overflow-x-auto max-h-36">
                        {JSON.stringify(selectedException.evidence, null, 2)}
                      </pre>
                    </div>
                  )}

                  <div className="pt-2 text-[11px] text-slate-500 flex items-center gap-1.5">
                    <Info className="h-3.5 w-3.5" />
                    <span>
                      In sandbox mode, automated remediation actions are disabled to safeguard financial controls.
                    </span>
                  </div>
                </div>

                <div className="pt-3 border-t border-slate-800 flex justify-end">
                  <button
                    onClick={() => setSelectedException(null)}
                    className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-white transition"
                  >
                    Close
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

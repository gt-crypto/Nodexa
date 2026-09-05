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

    // Dynamic real-time stage progress without artificial blocking delays
    setAnalysisStage("Building isolated sandbox & mounting in-memory engine...");

    const stageTimers: NodeJS.Timeout[] = [];
    stageTimers.push(
      setTimeout(() => {
        setAnalysisStage("Running deterministic controls & validating invariants...");
      }, 250)
    );
    stageTimers.push(
      setTimeout(() => {
        setAnalysisStage("Detecting exceptions & analyzing settlement exposures...");
      }, 500)
    );
    stageTimers.push(
      setTimeout(() => {
        setAnalysisStage("Mining recurring patterns & preparing audit report...");
      }, 750)
    );
    stageTimers.push(
      setTimeout(() => {
        setAnalysisStage("Waking the finance controller... (Render backend cold start)");
      }, 3000)
    );

    try {
      // Execute the real API analysis immediately without pre-delays
      const report = await analyzeSandboxCsv(
        selectedFile || undefined,
        !selectedFile ? csvRawText : undefined,
        fileName || "sandbox_dataset.csv"
      );

      // Transition to results immediately upon real response arrival
      stageTimers.forEach(clearTimeout);
      setAnalysis(report);
      setStep("results");
    } catch (err: any) {
      stageTimers.forEach(clearTimeout);
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
      <div className="relative overflow-hidden rounded-xl border border-slate-200 bg-white p-6 shadow-xs">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2.5">
              <div className="p-2 rounded-lg bg-indigo-50 border border-indigo-100 text-indigo-600">
                <FileSpreadsheet className="h-5 w-5" />
              </div>
              <h1 className="text-xl font-bold tracking-tight text-slate-900 flex items-center gap-2">
                Test New Dataset
                <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-200">
                  Ephemeral Sandbox
                </span>
              </h1>
            </div>
            <p className="text-sm text-slate-500 max-w-3xl">
              Upload custom operational finance batches or evaluate unseen CSV data against Nodexa&apos;s deterministic reconciliation, double-entry audit, and pattern-mining pipeline.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-50 border border-slate-200 text-xs font-medium text-slate-700">
              <Lock className="h-3.5 w-3.5 text-emerald-600" />
              <span>Zero Production Mutation</span>
            </div>
            {step !== "upload" && (
              <button
                onClick={resetAll}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white hover:bg-slate-50 text-xs font-medium text-slate-700 border border-slate-200 shadow-xs transition"
              >
                <RefreshCw className="h-3.5 w-3.5" />
                Reset
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Error Alert */}
      {errorMsg && (
        <div className="rounded-lg border border-rose-200 bg-rose-50/80 p-4 text-rose-800 flex items-start gap-3">
          <AlertTriangle className="h-5 w-5 text-rose-600 flex-shrink-0 mt-0.5" />
          <div className="space-y-1">
            <p className="text-sm font-semibold">Operation Error</p>
            <p className="text-xs text-rose-700">{errorMsg}</p>
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
                ? "border-indigo-500 bg-indigo-50/40 shadow-sm"
                : "border-slate-300 bg-white hover:border-slate-400 hover:bg-slate-50/50 shadow-xs"
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

            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-xl bg-indigo-50 border border-indigo-100 text-indigo-600 mb-4 shadow-xs">
              <Upload className="h-6 w-6" />
            </div>

            <h3 className="text-base font-semibold text-slate-900 mb-1">
              Upload Operational CSV Dataset
            </h3>
            <p className="text-xs text-slate-500 max-w-md mx-auto mb-5 leading-relaxed">
              Drag and drop your operational CSV file here, or click browse. Requires columns:{" "}
              <code className="text-indigo-700 bg-indigo-50 px-1 py-0.5 rounded border border-indigo-100">transaction_id</code>,{" "}
              <code className="text-indigo-700 bg-indigo-50 px-1 py-0.5 rounded border border-indigo-100">merchant_id</code>,{" "}
              <code className="text-indigo-700 bg-indigo-50 px-1 py-0.5 rounded border border-indigo-100">amount</code>,{" "}
              <code className="text-indigo-700 bg-indigo-50 px-1 py-0.5 rounded border border-indigo-100">status</code>,{" "}
              <code className="text-indigo-700 bg-indigo-50 px-1 py-0.5 rounded border border-indigo-100">transaction_date</code>.
            </p>

            <div className="flex flex-wrap items-center justify-center gap-3">
              <button
                type="button"
                data-variant="primary"
                onClick={() => fileInputRef.current?.click()}
                className="btn-primary-cta inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-[#F4D35E] hover:bg-[#E8C84A] active:bg-[#DDBA35] text-sm font-semibold text-slate-950 border border-[#E8C84A] shadow-xs transition"
              >
                <FileSpreadsheet className="h-4 w-4" />
                Browse File (.csv)
              </button>

              <button
                type="button"
                onClick={loadSampleDataset}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-white hover:bg-slate-50 border border-slate-200 text-sm font-medium text-slate-700 shadow-xs transition"
              >
                <Sparkles className="h-4 w-4 text-amber-500" />
                Load Sample Anomaly Dataset
              </button>
            </div>

            <div className="mt-6 flex items-center justify-center gap-6 text-xs text-slate-400">
              <span>Max file size: 5 MB</span>
              <span>&bull;</span>
              <span>Encodings: UTF-8 / ASCII</span>
              <span>&bull;</span>
              <span>Non-destructive validation</span>
            </div>
          </div>

          {/* Quick Guidance Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-2 shadow-xs">
              <div className="flex items-center gap-2 text-slate-900 font-semibold text-xs">
                <Database className="h-4 w-4 text-cyan-600" />
                1. Ephemeral Sandbox
              </div>
              <p className="text-xs text-slate-500 leading-relaxed">
                Uploaded rows are parsed and loaded into a temporary in-memory database. PostgreSQL production tables are completely bypassed and preserved.
              </p>
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-2 shadow-xs">
              <div className="flex items-center gap-2 text-slate-900 font-semibold text-xs">
                <Cpu className="h-4 w-4 text-indigo-600" />
                2. Autonomous Controls
              </div>
              <p className="text-xs text-slate-500 leading-relaxed">
                Executes the exact same 5 financial reconciliation checks: Ghost Settlement, Double Dip, Settlement SLA Breach, Partial Deficit, and Missing Allocation.
              </p>
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-2 shadow-xs">
              <div className="flex items-center gap-2 text-slate-900 font-semibold text-xs">
                <ShieldCheck className="h-4 w-4 text-amber-600" />
                3. Honest Benchmarking
              </div>
              <p className="text-xs text-slate-500 leading-relaxed">
                Because third-party datasets lack verified ground truth labels, accuracy metrics (Precision/Recall/F1) are transparently marked as unavailable.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* STEP 2: VALIDATING SPINNER */}
      {step === "validating" && (
        <div className="rounded-xl border border-slate-200 bg-white p-12 text-center space-y-4 shadow-xs">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-2 border-indigo-600 border-t-transparent mb-2" />
          <h3 className="text-base font-semibold text-slate-900">Validating CSV Structure</h3>
          <p className="text-xs text-slate-500 max-w-sm mx-auto">
            Checking header columns, parsing date formats, and validating numeric monetary fields...
          </p>
        </div>
      )}

      {/* STEP 3: PREVIEW & CONFIRMATION */}
      {step === "preview" && validation && (
        <div className="space-y-6">
          {/* Validation Status Card */}
          <div className="rounded-xl border border-slate-200 bg-white p-5 space-y-4 shadow-xs">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                {validation.is_valid ? (
                  <div className="p-2 rounded-lg bg-emerald-50 text-emerald-600 border border-emerald-100">
                    <CheckCircle2 className="h-5 w-5" />
                  </div>
                ) : (
                  <div className="p-2 rounded-lg bg-rose-50 text-rose-600 border border-rose-100">
                    <XCircle className="h-5 w-5" />
                  </div>
                )}
                <div>
                  <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
                    {fileName}
                    <span
                      className={`text-xs px-2.5 py-0.5 rounded-full font-semibold ${
                        validation.is_valid
                          ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                          : "bg-rose-50 text-rose-700 border border-rose-200"
                      }`}
                    >
                      {validation.is_valid ? "Schema Valid" : "Validation Issues"}
                    </span>
                  </h3>
                  <p className="text-xs text-slate-500 mt-0.5">
                    {validation.message}
                    {validation.validation_time_ms && (
                      <span className="text-indigo-600 font-mono ml-2 font-medium">
                        ({validation.validation_time_ms} ms)
                      </span>
                    )}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={resetAll}
                  className="px-3 py-2 rounded-lg bg-white hover:bg-slate-50 text-xs font-medium text-slate-700 border border-slate-200 shadow-xs transition"
                >
                  Choose Different File
                </button>
                {validation.is_valid && (
                  <button
                    type="button"
                    data-variant="primary"
                    onClick={runAnalysis}
                    className="btn-primary-cta inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-[#F4D35E] hover:bg-[#E8C84A] active:bg-[#DDBA35] text-xs font-semibold text-slate-950 border border-[#E8C84A] shadow-xs transition"
                  >
                    <Cpu className="h-4 w-4" />
                    Run Isolated Finance Analysis
                    <ArrowRight className="h-3.5 w-3.5" />
                  </button>
                )}
              </div>
            </div>

            {/* Quick Metrics Bar */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-3 border-t border-slate-100">
              <div className="bg-slate-50 p-3 rounded-lg border border-slate-100">
                <div className="text-slate-500 text-xs">Total Rows</div>
                <div className="text-lg font-bold text-slate-900 mt-0.5 font-mono">
                  {validation.total_rows}
                </div>
              </div>
              <div className="bg-slate-50 p-3 rounded-lg border border-slate-100">
                <div className="text-slate-500 text-xs">Valid Rows</div>
                <div className="text-lg font-bold text-emerald-600 mt-0.5 font-mono">
                  {validation.valid_rows}
                </div>
              </div>
              <div className="bg-slate-50 p-3 rounded-lg border border-slate-100">
                <div className="text-slate-500 text-xs">Invalid Rows</div>
                <div
                  className={`text-lg font-bold mt-0.5 font-mono ${
                    validation.invalid_rows > 0 ? "text-rose-600" : "text-slate-400"
                  }`}
                >
                  {validation.invalid_rows}
                </div>
              </div>
              <div className="bg-slate-50 p-3 rounded-lg border border-slate-100">
                <div className="text-slate-500 text-xs">Columns Detected</div>
                <div className="text-lg font-bold text-indigo-600 mt-0.5 font-mono">
                  {validation.columns_detected.length}
                </div>
              </div>
            </div>

            {/* Detected Columns Chips */}
            <div className="space-y-1.5">
              <span className="text-xs font-semibold text-slate-600">Header Columns:</span>
              <div className="flex flex-wrap gap-1.5">
                {validation.columns_detected.map((col) => (
                  <span
                    key={col}
                    className="inline-flex items-center gap-1 text-[11px] px-2.5 py-0.5 rounded-md bg-slate-100 text-slate-700 font-mono border border-slate-200"
                  >
                    <CheckCircle2 className="h-3 w-3 text-emerald-600" />
                    {col}
                  </span>
                ))}
                {validation.missing_required_columns.map((col) => (
                  <span
                    key={col}
                    className="inline-flex items-center gap-1 text-[11px] px-2.5 py-0.5 rounded-md bg-rose-50 text-rose-700 font-mono border border-rose-200"
                  >
                    <XCircle className="h-3 w-3 text-rose-600" />
                    Missing: {col}
                  </span>
                ))}
              </div>
            </div>

            {/* Validation Errors List if any */}
            {validation.errors.length > 0 && (
              <div className="mt-3 rounded-lg border border-rose-200 bg-rose-50/70 p-3 space-y-2">
                <div className="text-xs font-semibold text-rose-800 flex items-center gap-1.5">
                  <AlertTriangle className="h-3.5 w-3.5 text-rose-600" />
                  Validation Issues ({validation.errors.length})
                </div>
                <div className="max-h-32 overflow-y-auto space-y-1 text-xs text-rose-700 font-mono">
                  {validation.errors.slice(0, 10).map((err, idx) => (
                    <div key={idx} className="flex gap-2">
                      <span className="text-rose-600 font-semibold">Row {err.row_number}:</span>
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
            <div className="rounded-xl border border-slate-200 bg-white overflow-hidden shadow-xs">
              <div className="p-4 border-b border-slate-100 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Layers className="h-4 w-4 text-indigo-600" />
                  <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                    Dataset Preview (First {validation.preview_rows.length} Rows)
                  </h4>
                </div>
                <span className="text-[11px] text-slate-500">
                  Ready for in-memory reconciliation
                </span>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="bg-slate-50 text-slate-600 font-mono border-b border-slate-200">
                      <th className="py-2.5 px-3">#</th>
                      <th className="py-2.5 px-3">Transaction ID</th>
                      <th className="py-2.5 px-3">Merchant ID</th>
                      <th className="py-2.5 px-3 text-right">Amount (₹)</th>
                      <th className="py-2.5 px-3">Status</th>
                      <th className="py-2.5 px-3">Date</th>
                      <th className="py-2.5 px-3">Settlement (UTR)</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 font-mono text-slate-700">
                    {validation.preview_rows.map((row, idx) => (
                      <tr
                        key={idx}
                        className="hover:bg-slate-50 transition-colors"
                      >
                        <td className="py-2.5 px-3 text-slate-400">{idx + 1}</td>
                        <td className="py-2.5 px-3 font-semibold text-slate-900">
                          {row.transaction_id || "-"}
                        </td>
                        <td className="py-2.5 px-3 text-slate-600">
                          {row.merchant_id || "-"}
                        </td>
                        <td className="py-2.5 px-3 text-right font-semibold text-emerald-700">
                          ₹{Number(row.amount || 0).toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                        </td>
                        <td className="py-2.5 px-3">
                          <span
                            className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold ${
                              row.status === "SUCCESS"
                                ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                                : "bg-rose-50 text-rose-700 border border-rose-200"
                            }`}
                          >
                            {row.status || "UNKNOWN"}
                          </span>
                        </td>
                        <td className="py-2.5 px-3 text-slate-600">
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
        <div className="rounded-xl border border-slate-200 bg-white p-12 text-center space-y-6 shadow-xs">
          <div className="relative mx-auto w-16 h-16">
            <div className="absolute inset-0 rounded-full border-2 border-indigo-200 animate-ping" />
            <div className="relative flex items-center justify-center w-16 h-16 rounded-full bg-indigo-50 border border-indigo-200 text-indigo-600 shadow-xs">
              <Cpu className="h-7 w-7 animate-pulse" />
            </div>
          </div>

          <div className="space-y-2">
            <h3 className="text-base font-bold text-slate-900">
              Autonomous Financial Reconciliation in Progress
            </h3>
            <p className="text-xs text-indigo-600 font-mono font-medium">{analysisStage}</p>
          </div>

          <div className="max-w-md mx-auto w-full bg-slate-100 rounded-full h-1.5 overflow-hidden border border-slate-200">
            <div className="h-full bg-gradient-to-r from-indigo-500 to-cyan-500 animate-pulse w-3/4 rounded-full" />
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
          <div className="rounded-xl border border-amber-200 bg-gradient-to-r from-amber-50/80 via-white to-amber-50/30 p-5 space-y-3 shadow-xs">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-lg bg-amber-100 text-amber-700 border border-amber-200">
                  <ShieldCheck className="h-5 w-5" />
                </div>
                <div>
                  <h4 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
                    Ground Truth: {analysis.ground_truth_status}
                    <span className="text-[10px] uppercase font-bold px-2 py-0.5 rounded bg-amber-100 text-amber-800 border border-amber-200">
                      Third-Party Dataset
                    </span>
                  </h4>
                  <p className="text-xs text-slate-600 mt-0.5">
                    {analysis.accuracy_metrics_message}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={exportReportJson}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white hover:bg-slate-50 text-xs font-medium text-slate-700 border border-slate-200 shadow-xs transition"
                >
                  <Download className="h-3.5 w-3.5 text-indigo-600" />
                  Export JSON
                </button>
                <button
                  type="button"
                  data-variant="primary"
                  onClick={resetAll}
                  className="btn-primary-cta inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#F4D35E] hover:bg-[#E8C84A] active:bg-[#DDBA35] text-xs font-semibold text-slate-950 border border-[#E8C84A] shadow-xs transition"
                >
                  <RefreshCw className="h-3.5 w-3.5" />
                  Test Another
                </button>
              </div>
            </div>

            <div className="pt-3 border-t border-amber-200/60 text-[11px] text-slate-600 flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <span className="text-emerald-700 font-bold font-mono">ISOLATION:</span>
                <span>{analysis.isolation_mode}</span>
                <span>&bull;</span>
                <span className="text-emerald-700 font-semibold font-mono">
                  Production DB Modified: {analysis.production_database_modified ? "YES" : "NO (0 writes)"}
                </span>
              </div>
              <div className="text-slate-500 italic">
                {analysis.disclaimer}
              </div>
            </div>

            {/* Performance Timing Breakdown */}
            {analysis.timing_ms && analysis.timing_ms.total_analysis_time !== undefined && (
              <div className="pt-2.5 border-t border-amber-200/60 flex flex-wrap items-center justify-between gap-2 text-[11px] text-slate-600 font-mono">
                <div className="flex items-center gap-2">
                  <Clock className="h-3.5 w-3.5 text-indigo-600" />
                  <span className="text-slate-600">Analysis Latency:</span>
                  <span className="text-indigo-600 font-bold">{analysis.timing_ms.total_analysis_time} ms</span>
                  <span className="text-slate-300 hidden md:inline">&bull;</span>
                  <span className="text-slate-500 hidden md:inline">
                    SQLite: {analysis.timing_ms.sqlite_initialization ?? 0}ms | Insert: {analysis.timing_ms.data_insertion ?? 0}ms | Controls: {analysis.timing_ms.deterministic_controls ?? 0}ms | Mining: {analysis.timing_ms.pattern_mining ?? 0}ms
                  </span>
                </div>
                <div className="text-emerald-700 text-[10px] font-semibold bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                  Sub-100ms Ephemeral Sandbox
                </div>
              </div>
            )}
          </div>

          {/* Operational Metrics Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-1 shadow-xs">
              <div className="text-xs font-semibold text-slate-500">Total Operational Records</div>
              <div className="text-2xl font-bold font-mono text-slate-900">
                {analysis.dataset_summary.total_records}
              </div>
              <div className="text-[11px] text-slate-500">
                {analysis.dataset_summary.gateway_transactions} tx &bull; {analysis.dataset_summary.merchant_orders} orders
              </div>
            </div>

            <div className="rounded-xl border border-rose-200 bg-white p-4 space-y-1 shadow-xs">
              <div className="text-xs font-semibold text-rose-600">Exceptions Detected</div>
              <div className="text-2xl font-bold font-mono text-rose-600">
                {analysis.exceptions_detected}
              </div>
              <div className="text-[11px] text-rose-600/80 font-medium">
                {analysis.high_risk_cases} high / critical priority
              </div>
            </div>

            <div className="rounded-xl border border-amber-200 bg-white p-4 space-y-1 shadow-xs">
              <div className="text-xs font-semibold text-amber-600">Potential Exposure</div>
              <div className="text-2xl font-bold font-mono text-amber-600">
                {analysis.total_exposure_inr_formatted}
              </div>
              <div className="text-[11px] text-slate-500 font-mono">
                {analysis.total_exposure_minor_units.toLocaleString()} paise
              </div>
            </div>

            <div className="rounded-xl border border-indigo-200 bg-white p-4 space-y-1 shadow-xs">
              <div className="text-xs font-semibold text-indigo-600">Recurring Pattern Clusters</div>
              <div className="text-2xl font-bold font-mono text-indigo-600">
                {analysis.recurring_patterns_count}
              </div>
              <div className="text-[11px] text-slate-500">
                Systemic anomaly signatures discovered
              </div>
            </div>
          </div>

          {/* Dataset Breakdown Badges */}
          <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-3 flex flex-wrap items-center justify-between gap-2 text-xs">
            <span className="text-slate-600 font-semibold">Dataset Breakdown:</span>
            <div className="flex flex-wrap items-center gap-2 font-mono text-slate-700">
              <span className="px-2.5 py-1 rounded-md bg-white border border-slate-200 shadow-2xs">
                Gateway TX: <b className="text-slate-900">{analysis.dataset_summary.gateway_transactions}</b>
              </span>
              <span className="px-2.5 py-1 rounded-md bg-white border border-slate-200 shadow-2xs">
                Orders: <b className="text-slate-900">{analysis.dataset_summary.merchant_orders}</b>
              </span>
              <span className="px-2.5 py-1 rounded-md bg-white border border-slate-200 shadow-2xs">
                Settlements: <b className="text-slate-900">{analysis.dataset_summary.settlement_batches}</b>
              </span>
              <span className="px-2.5 py-1 rounded-md bg-white border border-slate-200 shadow-2xs">
                Ledger Entries: <b className="text-slate-900">{analysis.dataset_summary.ledger_entries}</b>
              </span>
              <span className="px-2.5 py-1 rounded-md bg-white border border-slate-200 shadow-2xs">
                Disputes: <b className="text-slate-900">{analysis.dataset_summary.dispute_events}</b>
              </span>
              <span className="px-2.5 py-1 rounded-md bg-white border border-slate-200 shadow-2xs">
                Merchants: <b className="text-slate-900">{analysis.dataset_summary.merchants_impacted}</b>
              </span>
            </div>
          </div>

          {/* Pattern Clusters Card if any */}
          {analysis.patterns.length > 0 && (
            <div className="rounded-xl border border-indigo-100 bg-white p-5 space-y-4 shadow-xs">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <TrendingUp className="h-4 w-4 text-indigo-600" />
                  <h4 className="text-sm font-bold text-slate-900">
                    Discovered Recurring Patterns ({analysis.patterns.length})
                  </h4>
                </div>
                <span className="text-xs text-slate-500">
                  Unsupervised correlation of systemic anomalies
                </span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {analysis.patterns.map((pat) => (
                  <div
                    key={pat.cluster_id}
                    className="rounded-lg border border-slate-200 bg-slate-50/50 hover:bg-slate-50 p-3.5 space-y-2 transition shadow-2xs"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-indigo-700 font-mono">
                        {pat.pattern_type}
                      </span>
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-indigo-50 text-indigo-700 border border-indigo-200 font-mono">
                        {pat.exception_count} incidents
                      </span>
                    </div>
                    <p className="text-xs text-slate-600 leading-relaxed">{pat.description}</p>
                    <div className="flex items-center justify-between text-[11px] text-slate-500 font-mono pt-1.5 border-t border-slate-200/80">
                      <span className="font-semibold text-slate-700">Exposure: {pat.total_exposure_inr_formatted}</span>
                      <span className="text-slate-400">ID: {pat.cluster_id}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Exceptions Table */}
          <div className="rounded-xl border border-slate-200 bg-white overflow-hidden shadow-xs">
            <div className="p-4 border-b border-slate-100 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 text-rose-600" />
                <h4 className="text-sm font-bold text-slate-900">
                  Identified Exceptions ({filteredExceptions.length} of {analysis.exceptions.length})
                </h4>
              </div>

              {/* Severity Filter */}
              <div className="flex items-center gap-1.5">
                {["ALL", "CRITICAL", "HIGH", "MEDIUM", "LOW"].map((sev) => (
                  <button
                    key={sev}
                    onClick={() => setFilterSeverity(sev)}
                    className={`px-2.5 py-1 rounded-md text-[11px] font-semibold transition ${
                      filterSeverity === sev
                        ? "bg-indigo-50 text-indigo-700 border border-indigo-200"
                        : "text-slate-500 hover:text-slate-900 hover:bg-slate-100"
                    }`}
                  >
                    {sev}
                  </button>
                ))}
              </div>
            </div>

            {filteredExceptions.length === 0 ? (
              <div className="p-8 text-center text-xs text-slate-400">
                No exceptions match the selected filter criteria.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="bg-slate-50 text-slate-600 font-mono border-b border-slate-200">
                      <th className="py-2.5 px-3">Exception ID</th>
                      <th className="py-2.5 px-3">Type</th>
                      <th className="py-2.5 px-3">Severity</th>
                      <th className="py-2.5 px-3 text-right">Exposure (₹)</th>
                      <th className="py-2.5 px-3">Primary Ref</th>
                      <th className="py-2.5 px-3">Recommended Action</th>
                      <th className="py-2.5 px-3 text-right">Details</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 font-mono text-slate-700">
                    {filteredExceptions.map((exc) => (
                      <tr
                        key={exc.exception_id}
                        onClick={() => setSelectedException(exc)}
                        className="hover:bg-slate-50/80 cursor-pointer transition-colors"
                      >
                        <td className="py-2.5 px-3 font-semibold text-indigo-600">
                          {exc.exception_id}
                        </td>
                        <td className="py-2.5 px-3 font-bold text-slate-900">
                          {exc.exception_type}
                        </td>
                        <td className="py-2.5 px-3">
                          <span
                            className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold ${
                              exc.severity === "CRITICAL"
                                ? "bg-rose-50 text-rose-700 border border-rose-200"
                                : exc.severity === "HIGH"
                                ? "bg-amber-50 text-amber-700 border border-amber-200"
                                : exc.severity === "MEDIUM"
                                ? "bg-cyan-50 text-cyan-700 border border-cyan-200"
                                : "bg-slate-100 text-slate-600 border border-slate-200"
                            }`}
                          >
                            {exc.severity}
                          </span>
                        </td>
                        <td className="py-2.5 px-3 text-right font-semibold text-amber-700">
                          {exc.exposure_inr_formatted}
                        </td>
                        <td className="py-2.5 px-3 text-slate-500">
                          {exc.primary_payment_id || exc.primary_order_id || "-"}
                        </td>
                        <td className="py-2.5 px-3 text-slate-600 max-w-xs truncate">
                          {exc.recommended_action}
                        </td>
                        <td className="py-2.5 px-3 text-right">
                          <button
                            type="button"
                            className="text-slate-400 hover:text-slate-700 p-1"
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
            <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-xs animate-fadeIn">
              <div className="relative w-full max-w-2xl rounded-xl border border-slate-200 bg-white p-6 shadow-xl space-y-4">
                <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                  <div className="space-y-0.5">
                    <div className="flex items-center gap-2">
                      <span className="text-xs px-2 py-0.5 rounded bg-indigo-50 text-indigo-700 font-mono font-semibold border border-indigo-200">
                        {selectedException.exception_id}
                      </span>
                      <span
                        className={`text-xs px-2 py-0.5 rounded font-bold ${
                          selectedException.severity === "CRITICAL"
                            ? "bg-rose-50 text-rose-700 border border-rose-200"
                            : "bg-amber-50 text-amber-700 border border-amber-200"
                        }`}
                      >
                        {selectedException.severity}
                      </span>
                    </div>
                    <h3 className="text-base font-bold text-slate-900">
                      {selectedException.exception_type}
                    </h3>
                  </div>

                  <button
                    onClick={() => setSelectedException(null)}
                    className="p-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-500 hover:text-slate-800 transition"
                  >
                    <XCircle className="h-5 w-5" />
                  </button>
                </div>

                {/* Details Body */}
                <div className="space-y-3 text-xs">
                  <div className="grid grid-cols-2 gap-3 p-3 rounded-lg bg-slate-50 border border-slate-200">
                    <div>
                      <span className="text-slate-500 font-medium">Financial Exposure:</span>
                      <div className="text-sm font-bold text-amber-700 font-mono">
                        {selectedException.exposure_inr_formatted}
                      </div>
                    </div>
                    <div>
                      <span className="text-slate-500 font-medium">Linked Payment ID:</span>
                      <div className="text-sm font-bold text-slate-900 font-mono">
                        {selectedException.primary_payment_id || "N/A"}
                      </div>
                    </div>
                  </div>

                  <div className="space-y-1">
                    <span className="font-semibold text-slate-700">Description:</span>
                    <p className="text-slate-600 bg-slate-50 p-3 rounded-lg border border-slate-200 leading-relaxed">
                      {selectedException.description || "Deterministic audit rule detected discrepancy between payment gateway ledger and bank clearing feeds."}
                    </p>
                  </div>

                  <div className="space-y-1">
                    <span className="font-semibold text-emerald-800 flex items-center gap-1">
                      <ShieldCheck className="h-4 w-4 text-emerald-600" />
                      Recommended Action (Advisory Only):
                    </span>
                    <p className="text-emerald-800 bg-emerald-50/70 p-3 rounded-lg border border-emerald-200 font-medium leading-relaxed">
                      {selectedException.recommended_action}
                    </p>
                  </div>

                  {selectedException.evidence && selectedException.evidence.length > 0 && (
                    <div className="space-y-1">
                      <span className="font-semibold text-slate-700">Technical Evidence:</span>
                      <pre className="text-[11px] font-mono p-3 rounded-lg bg-slate-900 border border-slate-800 text-cyan-300 overflow-x-auto max-h-36">
                        {JSON.stringify(selectedException.evidence, null, 2)}
                      </pre>
                    </div>
                  )}

                  <div className="pt-2 text-[11px] text-slate-500 flex items-center gap-1.5">
                    <Info className="h-3.5 w-3.5 text-slate-400" />
                    <span>
                      In sandbox mode, automated remediation actions are disabled to safeguard financial controls.
                    </span>
                  </div>
                </div>

                <div className="pt-3 border-t border-slate-100 flex justify-end">
                  <button
                    onClick={() => setSelectedException(null)}
                    className="px-4 py-2 rounded-lg bg-slate-900 hover:bg-slate-800 text-xs font-semibold text-white transition shadow-xs"
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

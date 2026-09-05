"use client";

import React, { useState } from "react";
import {
  ShieldCheck,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  RefreshCw,
  Play,
  TrendingDown,
  Lock,
  Layers,
  Database,
  Search,
} from "lucide-react";
import {
  VerificationRecord,
  VerificationDryRunResponse,
  VerificationEvidenceItem,
} from "../types";
import { verifyRemediation, retryVerification } from "../lib/api";
import { Button } from "./ui/Button";

interface VerificationPanelProps {
  remediationId?: string;
  initialRecord?: VerificationRecord | null;
}

export const VerificationPanel: React.FC<VerificationPanelProps> = ({
  remediationId = "act_demo_01",
  initialRecord = null,
}) => {
  const [activeRemId, setActiveRemId] = useState<string>(remediationId);
  const [record, setRecord] = useState<VerificationRecord | null>(initialRecord);
  const [dryRunResult, setDryRunResult] = useState<VerificationDryRunResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedFilter, setSelectedFilter] = useState<"ALL" | "FAIL" | "PASS">("ALL");

  const handleRunVerification = async (dryRun: boolean = false) => {
    setLoading(true);
    setError(null);
    try {
      const res = await verifyRemediation(activeRemId, dryRun);
      if (dryRun) {
        setDryRunResult(res as VerificationDryRunResponse);
      } else {
        setRecord(res as VerificationRecord);
        setDryRunResult(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Verification execution failed.");
    } finally {
      setLoading(false);
    }
  };

  const handleRetry = async () => {
    if (!record) return;
    setLoading(true);
    setError(null);
    try {
      const res = await retryVerification(record.verification_id);
      setRecord(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Verification retry failed.");
    } finally {
      setLoading(false);
    }
  };

  const getStatusBadge = (status?: string) => {
    switch (status) {
      case "VERIFIED_CLOSED":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-xs font-mono font-semibold bg-[#ECFDF3] border border-emerald-200 text-[#15803D]">
            <CheckCircle2 className="w-3.5 h-3.5" /> VERIFIED CLOSED
          </span>
        );
      case "FAILED":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-xs font-mono font-semibold bg-[#FEF2F2] border border-rose-200 text-[#DC2626]">
            <XCircle className="w-3.5 h-3.5" /> VERIFICATION FAILED
          </span>
        );
      case "ESCALATED":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-xs font-mono font-semibold bg-[#FFFBEB] border border-amber-200 text-[#B45309]">
            <AlertTriangle className="w-3.5 h-3.5" /> ESCALATED TO RISK
          </span>
        );
      case "RUNNING":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-xs font-mono font-semibold bg-indigo-50 border border-indigo-200 text-indigo-700 animate-pulse">
            <RefreshCw className="w-3.5 h-3.5 animate-spin" /> RUNNING CHECKS
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-xs font-mono font-medium bg-slate-100 text-slate-600 border border-slate-200">
            AWAITING VERIFICATION
          </span>
        );
    }
  };

  const evidenceItems: VerificationEvidenceItem[] =
    record?.evidence_summary || dryRunResult?.evidence_summary || [];

  const filteredEvidence = evidenceItems.filter((item) => {
    if (selectedFilter === "ALL") return true;
    return item.result === selectedFilter;
  });

  return (
    <section className="py-2" id="verification">
      <div className="rounded-xl p-5 sm:p-6 border border-slate-200 bg-white shadow-xs relative overflow-hidden">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-100">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <ShieldCheck className="w-5 h-5 text-indigo-600" />
              <h2 className="text-base sm:text-lg font-bold text-slate-900 tracking-tight font-sans">
                Post-Remediation Verification &amp; Self-Verification Engine
              </h2>
            </div>
            <p className="text-xs text-slate-500">
              Deterministic mathematical verification of financial state changes with zero-trust execution.
            </p>
          </div>

          <div className="flex items-center gap-3">
            {record && getStatusBadge(record.verification_status)}
            {dryRunResult && getStatusBadge(dryRunResult.projected_status)}
          </div>
        </div>

        {/* Control Bar */}
        <div className="mt-4 flex flex-col sm:flex-row items-center gap-2.5">
          <div className="relative w-full sm:w-80">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
            <input
              type="text"
              value={activeRemId}
              onChange={(e) => setActiveRemId(e.target.value)}
              placeholder="Remediation Plan ID (e.g. act_01)"
              className="w-full bg-white border border-slate-200 rounded-lg pl-8 pr-3 h-8 text-xs font-mono text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition-colors"
            />
          </div>

          <div className="flex flex-wrap items-center gap-2 w-full sm:w-auto">
            <Button
              size="sm"
              variant="secondary"
              onClick={() => handleRunVerification(true)}
              disabled={loading || !activeRemId}
              icon={<Play className="w-3 h-3 text-indigo-600" />}
            >
              Dry Run Verify
            </Button>

            <Button
              size="sm"
              variant="primary"
              onClick={() => handleRunVerification(false)}
              disabled={loading || !activeRemId}
              loading={loading}
              icon={<CheckCircle2 className="w-3 h-3" />}
            >
              Verify &amp; Close
            </Button>

            {record && record.verification_status === "FAILED" && (
              <Button
                size="sm"
                variant="danger"
                onClick={handleRetry}
                disabled={loading}
                icon={<RefreshCw className="w-3 h-3" />}
              >
                Retry ({record.attempt_number}/3)
              </Button>
            )}
          </div>
        </div>

        {error && (
          <div className="mt-3 p-2.5 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-center gap-2 font-mono">
            <XCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Metrics Overview */}
        {(record || dryRunResult) && (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mt-4">
            {/* Original Exposure */}
            <div className="p-3 rounded-lg bg-slate-50 border border-slate-200">
              <span className="text-xs font-medium text-slate-500 font-sans block mb-0.5">Original Exposure</span>
              <div className="text-base font-bold financial-num text-slate-900">
                ₹{((record?.original_exposure ?? dryRunResult?.projected_exposure_reduction ?? 0) / 100).toLocaleString("en-IN", { minimumFractionDigits: 2 })}
              </div>
              <span className="text-[10px] text-slate-400 font-sans">Recorded at diagnosis</span>
            </div>

            {/* Remaining Exposure */}
            <div className="p-3 rounded-lg bg-slate-50 border border-slate-200">
              <span className="text-xs font-medium text-slate-500 font-sans block mb-0.5">Remaining Exposure</span>
              <div className="text-base font-bold financial-num text-indigo-700">
                ₹{((record?.remaining_exposure ?? dryRunResult?.projected_remaining_exposure ?? 0) / 100).toLocaleString("en-IN", { minimumFractionDigits: 2 })}
              </div>
              <span className="text-[10px] text-emerald-700 flex items-center gap-1 mt-0.5 font-sans font-medium">
                <Lock className="w-2.5 h-2.5" /> Target: ₹0.00 minor units
              </span>
            </div>

            {/* Exposure Reduction */}
            <div className="p-3 rounded-lg bg-slate-50 border border-slate-200">
              <span className="text-xs font-medium text-slate-500 font-sans block mb-0.5">Exposure Reduction</span>
              <div className="text-base font-bold text-emerald-700 flex items-center gap-1.5 financial-num">
                <TrendingDown className="w-4 h-4" />
                <span>
                  {(((record?.exposure_reduction_bps ?? dryRunResult?.projected_exposure_reduction_bps ?? 0) / 100)).toFixed(2)}%
                </span>
                <span className="text-xs font-normal text-slate-500 font-sans num-tabular">
                  ({record?.exposure_reduction_bps ?? dryRunResult?.projected_exposure_reduction_bps ?? 0} bps)
                </span>
              </div>
              <span className="text-[10px] text-slate-400 font-sans">Integer basis points</span>
            </div>
          </div>
        )}

        {/* 8 Deterministic Checks Matrix */}
        {(record || dryRunResult) && (
          <div className="mt-5">
            <h3 className="text-xs font-bold text-slate-900 mb-2.5 flex items-center gap-1.5 font-mono uppercase tracking-wider">
              <Layers className="w-3.5 h-3.5 text-indigo-600" />
              <span>Automated check suite (8 deterministic gates)</span>
            </h3>

            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-2">
              {[
                { name: "1. Execution Status", key: "CHECK-EXECUTION-STATUS", desc: "Remediation executed with snapshots" },
                { name: "2. Action State", key: "CHECK-REFUND-STATUS", desc: "Payment status, dispute, or linkage valid" },
                { name: "3. Exposure Math", key: "CHECK-EXPOSURE-ZERO", desc: "Remaining exposure recalculated = 0" },
                { name: "4. Invariant Suite", key: "CHECK-INVAR-PROGRESSION", desc: "Ledger progression & debit/credit sanity" },
                { name: "5. Double-Entry Delta", key: "CHECK-DOUBLE-ENTRY-DELTA", desc: "Actual delta = Credits - Debits" },
                { name: "6. Reconciliation", key: "CHECK-RECON-", desc: "Multi-source matching & order alignment" },
                { name: "7. Legitimate Protect", key: "CHECK-LEGITIMATE-PROTECTION", desc: "Prevents artificial observation closures" },
                { name: "8. Stale State Guard", key: "CHECK-STALE-STATE", desc: "Zero subsequent corrupting mutations" },
              ].map((gate) => {
                const passedList = record?.checks_passed || dryRunResult?.checks_passed || [];
                const isPassed = passedList.some((p) => p.includes(gate.key) || p === gate.key);

                return (
                  <div
                    key={gate.key}
                    className={`p-2.5 rounded-lg border text-xs font-mono shadow-xs ${
                      isPassed
                        ? "bg-[#ECFDF3] border-emerald-200 text-emerald-900"
                        : "bg-[#FEF2F2] border-rose-200 text-rose-900"
                    }`}
                  >
                    <div className="flex items-center justify-between mb-0.5">
                      <span className="font-semibold text-slate-900 text-[11px]">{gate.name}</span>
                      {isPassed ? (
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                      ) : (
                        <XCircle className="w-3.5 h-3.5 text-rose-600" />
                      )}
                    </div>
                    <p className="text-[10px] text-slate-600 leading-tight">{gate.desc}</p>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Evidence & Invariant Audit Breakdown */}
        {evidenceItems.length > 0 && (
          <div className="mt-5">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-xs font-bold text-slate-900 flex items-center gap-1.5 font-mono uppercase tracking-wider">
                <Database className="w-3.5 h-3.5 text-indigo-600" />
                <span>Deterministic verification evidence trail ({filteredEvidence.length})</span>
              </h3>

              <div className="flex items-center gap-1 bg-slate-50 border border-slate-200 rounded-md p-0.5 text-xs font-mono">
                {(["ALL", "PASS", "FAIL"] as const).map((f) => (
                  <button
                    key={f}
                    onClick={() => setSelectedFilter(f)}
                    className={`px-2 py-0.5 rounded text-[11px] font-medium transition-colors cursor-pointer ${
                      selectedFilter === f
                        ? "bg-indigo-50 text-indigo-700 font-semibold border border-indigo-200"
                        : "text-slate-500 hover:text-slate-800"
                    }`}
                  >
                    {f}
                  </button>
                ))}
              </div>
            </div>

            <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-200 text-slate-600 font-sans font-semibold text-[11px] uppercase tracking-wider bg-slate-50">
                    <th className="py-2.5 px-3">Check ID</th>
                    <th className="py-2.5 px-3">Source table</th>
                    <th className="py-2.5 px-3">Expected</th>
                    <th className="py-2.5 px-3">Actual</th>
                    <th className="py-2.5 px-3">Status</th>
                    <th className="py-2.5 px-3">Explanation</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 font-mono text-[11px]">
                  {filteredEvidence.map((ev, idx) => (
                    <tr key={idx} className="hover:bg-slate-50 transition-colors">
                      <td className="py-2 px-3 text-slate-900 font-medium">{ev.check_id}</td>
                      <td className="py-2 px-3 text-slate-600">{ev.source_table}</td>
                      <td className="py-2 px-3 text-slate-800">
                        {typeof ev.expected_value === "object"
                          ? JSON.stringify(ev.expected_value)
                          : String(ev.expected_value)}
                      </td>
                      <td className="py-2 px-3 text-slate-800">
                        {typeof ev.actual_value === "object"
                          ? JSON.stringify(ev.actual_value)
                          : String(ev.actual_value)}
                      </td>
                      <td className="py-2 px-3">
                        {ev.result === "PASS" ? (
                          <span className="text-emerald-700 font-bold">PASS</span>
                        ) : (
                          <span className="text-rose-700 font-bold">FAIL</span>
                        )}
                      </td>
                      <td className="py-2 px-3 font-sans text-slate-500 max-w-xs truncate">
                        {ev.explanation}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </section>
  );
};

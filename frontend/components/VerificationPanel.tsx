"use client";

import React, { useState } from "react";
import {
  ShieldCheck,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  RefreshCw,
  Play,
  ArrowRight,
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
    } catch (err: any) {
      setError(err.message || "Failed to execute verification");
    } finally {
      setLoading(false);
    }
  };

  const handleRetry = async () => {
    if (!record || !record.verification_id) return;
    setLoading(true);
    setError(null);
    try {
      const res = await retryVerification(record.verification_id, "Operator manual retry");
      setRecord(res);
    } catch (err: any) {
      setError(err.message || "Retry failed");
    } finally {
      setLoading(false);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "VERIFIED":
      case "PASSED":
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 border border-emerald-500/30 text-emerald-400">
            <CheckCircle2 className="w-3.5 h-3.5" /> VERIFIED CLOSED
          </span>
        );
      case "FAILED":
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-rose-500/10 border border-rose-500/30 text-rose-400">
            <XCircle className="w-3.5 h-3.5" /> VERIFICATION FAILED
          </span>
        );
      case "ESCALATED":
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-500/10 border border-amber-500/30 text-amber-400">
            <AlertTriangle className="w-3.5 h-3.5" /> ESCALATED TO RISK
          </span>
        );
      case "RUNNING":
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 animate-pulse">
            <RefreshCw className="w-3.5 h-3.5 animate-spin" /> RUNNING CHECKS
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-slate-800 text-slate-400 border border-slate-700">
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
    <section className="py-8" id="verification">
      <div className="glass-panel rounded-2xl p-6 sm:p-8 border border-slate-800 relative overflow-hidden">
        {/* Glow effect */}
        <div className="absolute top-0 right-0 -mr-16 -mt-16 w-64 h-64 bg-teal-500/10 rounded-full blur-3xl pointer-events-none"></div>

        {/* Header (Issue 14: H2) */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-slate-800/80">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <ShieldCheck className="w-6 h-6 text-teal-400" />
              <h2 className="text-xl sm:text-2xl font-bold text-white tracking-tight">
                Post-Remediation Verification & Self-Verification Engine
              </h2>
            </div>
            <p className="text-sm text-slate-400">
              Deterministic mathematical verification of financial state changes with zero-trust execution.
            </p>
          </div>

          <div className="flex items-center gap-3">
            {record && getStatusBadge(record.verification_status)}
            {dryRunResult && getStatusBadge(dryRunResult.projected_status)}
          </div>
        </div>

        {/* Control Bar */}
        <div className="mt-6 flex flex-col sm:flex-row items-center gap-3">
          <div className="relative w-full sm:w-80">
            <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={activeRemId}
              onChange={(e) => setActiveRemId(e.target.value)}
              placeholder="Remediation Plan ID (e.g. act_01)"
              className="w-full bg-slate-900/90 border border-slate-700/80 rounded-lg pl-9 pr-3 py-2 text-xs font-mono text-white placeholder-slate-500 focus:outline-none focus:border-teal-500"
            />
          </div>

          <div className="flex flex-wrap items-center gap-2 w-full sm:w-auto">
            <Button
              size="sm"
              variant="secondary"
              onClick={() => handleRunVerification(true)}
              disabled={loading || !activeRemId}
              icon={<Play className="w-3.5 h-3.5 text-cyan-400" />}
            >
              Dry Run Verify
            </Button>

            <Button
              size="sm"
              variant="primary"
              onClick={() => handleRunVerification(false)}
              disabled={loading || !activeRemId}
              loading={loading}
              icon={<CheckCircle2 className="w-3.5 h-3.5" />}
            >
              Verify & Close
            </Button>

            {record && record.verification_status === "FAILED" && (
              <Button
                size="sm"
                variant="danger"
                onClick={handleRetry}
                disabled={loading}
                icon={<RefreshCw className="w-3.5 h-3.5" />}
              >
                Retry ({record.attempt_number}/3)
              </Button>
            )}
          </div>
        </div>

        {error && (
          <div className="mt-4 p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
            <XCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Metrics Overview */}
        {(record || dryRunResult) && (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-6">
            {/* Original Exposure */}
            <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800">
              <span className="text-xs text-slate-400 block mb-1">Original Exposure</span>
              <div className="text-lg sm:text-xl font-bold font-mono text-white">
                ₹{((record?.original_exposure ?? dryRunResult?.projected_exposure_reduction ?? 0) / 100).toLocaleString("en-IN", { minimumFractionDigits: 2 })}
              </div>
              <span className="text-[11px] text-slate-500">Recorded at anomaly diagnosis</span>
            </div>

            {/* Remaining Exposure */}
            <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800">
              <span className="text-xs text-slate-400 block mb-1">Remaining Exposure</span>
              <div className="text-lg sm:text-xl font-bold font-mono text-teal-400">
                ₹{((record?.remaining_exposure ?? dryRunResult?.projected_remaining_exposure ?? 0) / 100).toLocaleString("en-IN", { minimumFractionDigits: 2 })}
              </div>
              <span className="text-[11px] text-emerald-400 flex items-center gap-1 mt-0.5">
                <Lock className="w-3 h-3" /> Target: ₹0.00 minor units
              </span>
            </div>

            {/* Exposure Reduction */}
            <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800">
              <span className="text-xs text-slate-400 block mb-1">Exposure Reduction</span>
              <div className="text-lg sm:text-xl font-bold font-mono text-emerald-400 flex items-center gap-2">
                <TrendingDown className="w-5 h-5" />
                <span>
                  {(((record?.exposure_reduction_bps ?? dryRunResult?.projected_exposure_reduction_bps ?? 0) / 100)).toFixed(2)}%
                </span>
                <span className="text-xs font-normal text-slate-400 font-sans">
                  ({record?.exposure_reduction_bps ?? dryRunResult?.projected_exposure_reduction_bps ?? 0} bps)
                </span>
              </div>
              <span className="text-[11px] text-slate-500">Integer deterministic basis points</span>
            </div>
          </div>
        )}

        {/* 8 Deterministic Checks Matrix (Issue 15: H3) */}
        {(record || dryRunResult) && (
          <div className="mt-8">
            <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2 font-mono">
              <Layers className="w-4 h-4 text-teal-400" />
              <span>Automated check suite (8 deterministic gates)</span>
            </h3>

            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
              {[
                { name: "1. Execution Status", key: "CHECK-EXECUTION-STATUS", desc: "Remediation was executed with snapshots" },
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
                    className={`p-3 rounded-xl border text-xs ${
                      isPassed
                        ? "bg-emerald-500/5 border-emerald-500/30 text-slate-300"
                        : "bg-rose-500/5 border-rose-500/30 text-rose-300"
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-semibold text-white">{gate.name}</span>
                      {isPassed ? (
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                      ) : (
                        <XCircle className="w-3.5 h-3.5 text-rose-400" />
                      )}
                    </div>
                    <p className="text-[11px] text-slate-400 leading-tight">{gate.desc}</p>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Evidence & Invariant Audit Breakdown (Issue 15: H3) */}
        {evidenceItems.length > 0 && (
          <div className="mt-8">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-white flex items-center gap-2 font-mono">
                <Database className="w-4 h-4 text-cyan-400" />
                <span>Deterministic verification evidence trail ({filteredEvidence.length})</span>
              </h3>

              <div className="flex items-center gap-1 bg-slate-900 border border-slate-800 rounded-lg p-1 text-xs">
                {(["ALL", "PASS", "FAIL"] as const).map((f) => (
                  <button
                    key={f}
                    onClick={() => setSelectedFilter(f)}
                    className={`px-2.5 py-1 rounded font-medium transition ${
                      selectedFilter === f
                        ? "bg-teal-500/20 text-teal-300 border border-teal-500/30"
                        : "text-slate-400 hover:text-white"
                    }`}
                  >
                    {f}
                  </button>
                ))}
              </div>
            </div>

            <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-900/60">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400 font-mono text-xs bg-slate-950/40">
                    <th className="py-2.5 px-3">Check ID</th>
                    <th className="py-2.5 px-3">Source table</th>
                    <th className="py-2.5 px-3">Expected</th>
                    <th className="py-2.5 px-3">Actual</th>
                    <th className="py-2.5 px-3">Status</th>
                    <th className="py-2.5 px-3">Explanation</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-mono text-xs">
                  {filteredEvidence.map((ev, idx) => (
                    <tr key={idx} className="hover:bg-slate-800/30 transition">
                      <td className="py-2 px-3 text-slate-300 font-medium">{ev.check_id}</td>
                      <td className="py-2 px-3 text-slate-400">{ev.source_table}</td>
                      <td className="py-2 px-3 text-slate-300">
                        {typeof ev.expected_value === "object"
                          ? JSON.stringify(ev.expected_value)
                          : String(ev.expected_value)}
                      </td>
                      <td className="py-2 px-3 text-slate-300">
                        {typeof ev.actual_value === "object"
                          ? JSON.stringify(ev.actual_value)
                          : String(ev.actual_value)}
                      </td>
                      <td className="py-2 px-3">
                        {ev.result === "PASS" ? (
                          <span className="text-emerald-400 font-semibold">PASS</span>
                        ) : (
                          <span className="text-rose-400 font-semibold">FAIL</span>
                        )}
                      </td>
                      <td className="py-2 px-3 font-sans text-slate-400 max-w-xs truncate">
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

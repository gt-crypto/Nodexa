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
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-xs font-mono font-medium bg-emerald-950/30 border border-emerald-800/40 text-emerald-300">
            <CheckCircle2 className="w-3.5 h-3.5" /> VERIFIED CLOSED
          </span>
        );
      case "FAILED":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-xs font-mono font-medium bg-rose-950/30 border border-rose-800/40 text-rose-300">
            <XCircle className="w-3.5 h-3.5" /> VERIFICATION FAILED
          </span>
        );
      case "ESCALATED":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-xs font-mono font-medium bg-amber-950/30 border border-amber-800/40 text-amber-300">
            <AlertTriangle className="w-3.5 h-3.5" /> ESCALATED TO RISK
          </span>
        );
      case "RUNNING":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-xs font-mono font-medium bg-sky-950/30 border border-sky-800/40 text-sky-300 animate-pulse">
            <RefreshCw className="w-3.5 h-3.5 animate-spin" /> RUNNING CHECKS
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-xs font-mono font-medium bg-slate-900 text-slate-400 border border-slate-800">
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
      <div className="rounded-xl p-5 sm:p-6 border border-slate-800/80 bg-[#0d121d] shadow-sm relative overflow-hidden">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-800/80">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <ShieldCheck className="w-5 h-5 text-sky-400" />
              <h2 className="text-base sm:text-lg font-semibold text-white tracking-tight font-sans">
                Post-Remediation Verification &amp; Self-Verification Engine
              </h2>
            </div>
            <p className="text-xs text-slate-400">
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
            <Search className="w-3.5 h-3.5 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
            <input
              type="text"
              value={activeRemId}
              onChange={(e) => setActiveRemId(e.target.value)}
              placeholder="Remediation Plan ID (e.g. act_01)"
              className="w-full bg-[#090d16] border border-slate-700/80 rounded-lg pl-8 pr-3 h-8 text-xs font-mono text-white placeholder-slate-500 focus:outline-none focus:border-sky-500 focus:ring-1 focus:ring-sky-500 transition-colors"
            />
          </div>

          <div className="flex flex-wrap items-center gap-2 w-full sm:w-auto">
            <Button
              size="sm"
              variant="secondary"
              onClick={() => handleRunVerification(true)}
              disabled={loading || !activeRemId}
              icon={<Play className="w-3 h-3 text-sky-400" />}
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
          <div className="mt-3 p-2.5 rounded-lg bg-rose-950/30 border border-rose-800/40 text-rose-300 text-xs flex items-center gap-2 font-mono">
            <XCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Metrics Overview */}
        {(record || dryRunResult) && (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mt-4">
            {/* Original Exposure */}
            <div className="p-3 rounded-lg bg-[#090d16] border border-slate-800/80">
              <span className="text-xs font-medium text-slate-400 font-sans block mb-0.5">Original Exposure</span>
              <div className="text-base font-bold financial-num text-white">
                ₹{((record?.original_exposure ?? dryRunResult?.projected_exposure_reduction ?? 0) / 100).toLocaleString("en-IN", { minimumFractionDigits: 2 })}
              </div>
              <span className="text-[10px] text-slate-500 font-sans">Recorded at diagnosis</span>
            </div>

            {/* Remaining Exposure */}
            <div className="p-3 rounded-lg bg-[#090d16] border border-slate-800/80">
              <span className="text-xs font-medium text-slate-400 font-sans block mb-0.5">Remaining Exposure</span>
              <div className="text-base font-bold financial-num text-sky-400">
                ₹{((record?.remaining_exposure ?? dryRunResult?.projected_remaining_exposure ?? 0) / 100).toLocaleString("en-IN", { minimumFractionDigits: 2 })}
              </div>
              <span className="text-[10px] text-emerald-400 flex items-center gap-1 mt-0.5 font-sans font-medium">
                <Lock className="w-2.5 h-2.5" /> Target: ₹0.00 minor units
              </span>
            </div>

            {/* Exposure Reduction */}
            <div className="p-3 rounded-lg bg-[#090d16] border border-slate-800/80">
              <span className="text-xs font-medium text-slate-400 font-sans block mb-0.5">Exposure Reduction</span>
              <div className="text-base font-bold text-emerald-400 flex items-center gap-1.5 financial-num">
                <TrendingDown className="w-4 h-4" />
                <span>
                  {(((record?.exposure_reduction_bps ?? dryRunResult?.projected_exposure_reduction_bps ?? 0) / 100)).toFixed(2)}%
                </span>
                <span className="text-xs font-normal text-slate-400 font-sans num-tabular">
                  ({record?.exposure_reduction_bps ?? dryRunResult?.projected_exposure_reduction_bps ?? 0} bps)
                </span>
              </div>
              <span className="text-[10px] text-slate-500 font-sans">Integer basis points</span>
            </div>
          </div>
        )}

        {/* 8 Deterministic Checks Matrix */}
        {(record || dryRunResult) && (
          <div className="mt-5">
            <h3 className="text-xs font-semibold text-white mb-2.5 flex items-center gap-1.5 font-mono uppercase tracking-wider">
              <Layers className="w-3.5 h-3.5 text-sky-400" />
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
                    className={`p-2.5 rounded-lg border text-xs font-mono ${
                      isPassed
                        ? "bg-[#090d16] border-emerald-800/40 text-slate-300"
                        : "bg-[#090d16] border-rose-800/40 text-rose-300"
                    }`}
                  >
                    <div className="flex items-center justify-between mb-0.5">
                      <span className="font-semibold text-white text-[11px]">{gate.name}</span>
                      {isPassed ? (
                        <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                      ) : (
                        <XCircle className="w-3 h-3 text-rose-400" />
                      )}
                    </div>
                    <p className="text-[10px] text-slate-400 leading-tight">{gate.desc}</p>
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
              <h3 className="text-xs font-semibold text-white flex items-center gap-1.5 font-mono uppercase tracking-wider">
                <Database className="w-3.5 h-3.5 text-sky-400" />
                <span>Deterministic verification evidence trail ({filteredEvidence.length})</span>
              </h3>

              <div className="flex items-center gap-1 bg-[#090d16] border border-slate-800 rounded-md p-0.5 text-xs font-mono">
                {(["ALL", "PASS", "FAIL"] as const).map((f) => (
                  <button
                    key={f}
                    onClick={() => setSelectedFilter(f)}
                    className={`px-2 py-0.5 rounded text-[11px] font-medium transition-colors cursor-pointer ${
                      selectedFilter === f
                        ? "bg-sky-950/40 text-sky-300 border border-sky-800/50"
                        : "text-slate-400 hover:text-white"
                    }`}
                  >
                    {f}
                  </button>
                ))}
              </div>
            </div>

            <div className="overflow-x-auto rounded-lg border border-slate-800/80 bg-[#090d16]">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400 font-sans font-semibold text-[11px] uppercase tracking-wider bg-[#070a10]">
                    <th className="py-2 px-3">Check ID</th>
                    <th className="py-2 px-3">Source table</th>
                    <th className="py-2 px-3">Expected</th>
                    <th className="py-2 px-3">Actual</th>
                    <th className="py-2 px-3">Status</th>
                    <th className="py-2 px-3">Explanation</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-mono text-[11px]">
                  {filteredEvidence.map((ev, idx) => (
                    <tr key={idx} className="hover:bg-slate-800/20 transition-colors">
                      <td className="py-1.5 px-3 text-slate-300 font-medium">{ev.check_id}</td>
                      <td className="py-1.5 px-3 text-slate-400">{ev.source_table}</td>
                      <td className="py-1.5 px-3 text-slate-300">
                        {typeof ev.expected_value === "object"
                          ? JSON.stringify(ev.expected_value)
                          : String(ev.expected_value)}
                      </td>
                      <td className="py-1.5 px-3 text-slate-300">
                        {typeof ev.actual_value === "object"
                          ? JSON.stringify(ev.actual_value)
                          : String(ev.actual_value)}
                      </td>
                      <td className="py-1.5 px-3">
                        {ev.result === "PASS" ? (
                          <span className="text-emerald-400 font-semibold">PASS</span>
                        ) : (
                          <span className="text-rose-400 font-semibold">FAIL</span>
                        )}
                      </td>
                      <td className="py-1.5 px-3 font-sans text-slate-400 max-w-xs truncate">
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

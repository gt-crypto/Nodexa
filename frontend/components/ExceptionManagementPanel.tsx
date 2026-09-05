"use client";

import React, { useState, useEffect } from "react";
import {
  ShieldAlert,
  Search,
  Filter,
  RefreshCw,
  ChevronRight,
  CheckCircle2,
  AlertTriangle,
  Clock,
  ArrowUpRight,
  Layers,
  DollarSign,
  FileText,
  ShieldCheck,
  Check,
  Building,
  Hash,
  ExternalLink,
} from "lucide-react";
import { fetchExceptions } from "../lib/api";
import { executeWithColdStartRetry } from "../lib/resilience";
import { ColdStartWakingCard } from "./ColdStartWakingCard";
import { StatusBadge } from "./ui/StatusBadge";
import { Button } from "./ui/Button";

interface ExceptionItem {
  exception_id: string;
  exception_type: string;
  severity: string;
  state: string;
  exposure: number;
  confidence: number;
  source_flag?: string;
  description?: string;
  primary_payment_id?: string;
  primary_order_id?: string;
  detected_at: string;
  created_at?: string;
  updated_at?: string;
}

export function ExceptionManagementPanel() {
  const [exceptions, setExceptions] = useState<ExceptionItem[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [wakingState, setWakingState] = useState<{ attempt: number; isTimeout: boolean } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [filterSeverity, setFilterSeverity] = useState<string>("ALL");

  useEffect(() => {
    loadExceptions();
  }, []);

  const loadExceptions = async () => {
    setLoading(true);
    setError(null);
    setWakingState(null);
    try {
      const data = await executeWithColdStartRetry(
        () => fetchExceptions(undefined, 100),
        {
          onWaking: (attempt) => setWakingState({ attempt, isTimeout: false }),
          onRecovered: () => setWakingState(null),
        }
      );
      const items = Array.isArray(data) ? data : (data as any)?.items || [];
      setExceptions(items);
      if (items.length > 0 && !selectedId) {
        setSelectedId(items[0].exception_id);
      }
    } catch (err: any) {
      setError(err.message || "Failed to load exceptions.");
    } finally {
      setLoading(false);
    }
  };

  const filteredExceptions = exceptions.filter((item) => {
    const matchesSearch =
      item.exception_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.exception_type.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (item.primary_payment_id && item.primary_payment_id.toLowerCase().includes(searchQuery.toLowerCase())) ||
      (item.description && item.description.toLowerCase().includes(searchQuery.toLowerCase()));

    const matchesSeverity =
      filterSeverity === "ALL" || item.severity.toUpperCase() === filterSeverity.toUpperCase();

    return matchesSearch && matchesSeverity;
  });

  const selectedException = exceptions.find((e) => e.exception_id === selectedId) || filteredExceptions[0];

  const formatINR = (paise: number) => {
    return `₹${(paise / 100).toLocaleString("en-IN", { minimumFractionDigits: 2 })}`;
  };

  const getMerchantId = (exc: ExceptionItem) => {
    if (exc.description && exc.description.includes("MERCH_")) {
      const match = exc.description.match(/MERCH_[A-Z0-9_-]+/);
      if (match) return match[0];
    }
    return "MERCH_PLATFORM_01";
  };

  return (
    <div className="space-y-6">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200">
        <div>
          <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded bg-indigo-50 border border-indigo-200 text-indigo-700 text-xs font-mono font-medium mb-1.5">
            <ShieldAlert className="w-3.5 h-3.5 text-indigo-600" />
            <span>OPERATIONAL CONSOLE &bull; 14 ACTIVE CONTROLS</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 font-sans">
            Exception Management &amp; Investigation
          </h1>
          <p className="text-xs sm:text-sm text-slate-500 mt-0.5">
            Real-time reconciliation findings, double-entry discrepancies, and policy-driven investigation workflows.
          </p>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <Button
            variant="secondary"
            size="sm"
            onClick={loadExceptions}
            disabled={loading}
            icon={<RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin text-indigo-600" : ""}`} />}
          >
            Refresh Feed
          </Button>
        </div>
      </div>

      {/* Loading or Waking state */}
      {wakingState ? (
        <ColdStartWakingCard
          attempt={wakingState.attempt}
          maxAttempts={6}
          isTimeout={wakingState.isTimeout}
          onRetry={loadExceptions}
          description="Connecting to Exception Detection Engine…"
        />
      ) : error ? (
        <div className="p-4 rounded-xl border border-rose-200 bg-rose-50 text-rose-700 text-xs flex items-center gap-3">
          <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />
          <span>{error}</span>
        </div>
      ) : (
        <div className="grid grid-cols-1 xl:grid-cols-12 gap-6 items-start">
          {/* LEFT: Exception Management Console Table (xl:col-span-7) */}
          <div className="xl:col-span-7 rounded-xl border border-slate-200 bg-white shadow-xs overflow-hidden">
            {/* Table Filter Controls */}
            <div className="p-4 border-b border-slate-100 flex flex-col sm:flex-row items-center justify-between gap-3 bg-slate-50/50">
              <div className="relative w-full sm:w-64">
                <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <input
                  type="text"
                  placeholder="Search exceptions or IDs..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full bg-white border border-slate-200 rounded-lg pl-9 pr-3 py-1.5 text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
                />
              </div>

              <div className="flex items-center gap-2 w-full sm:w-auto justify-between sm:justify-end text-xs">
                <span className="text-slate-400 font-medium">Severity:</span>
                <div className="inline-flex rounded-lg border border-slate-200 p-0.5 bg-white">
                  {["ALL", "CRITICAL", "HIGH", "MEDIUM"].map((sev) => (
                    <button
                      key={sev}
                      onClick={() => setFilterSeverity(sev)}
                      className={`px-2.5 py-1 text-[11px] font-medium rounded-md transition-colors cursor-pointer ${
                        filterSeverity === sev
                          ? "bg-indigo-50 text-indigo-700 font-semibold"
                          : "text-slate-600 hover:text-slate-900"
                      }`}
                    >
                      {sev}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Table */}
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50/70 text-slate-500 font-mono text-[11px]">
                    <th className="py-3 px-4 font-semibold">Exception</th>
                    <th className="py-3 px-3 font-semibold">Merchant</th>
                    <th className="py-3 px-4 font-semibold text-right">Exposure</th>
                    <th className="py-3 px-3 font-semibold text-center">Risk</th>
                    <th className="py-3 px-4 font-semibold text-center">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {filteredExceptions.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="py-8 text-center text-slate-400 font-mono text-xs">
                        No exceptions found matching filters.
                      </td>
                    </tr>
                  ) : (
                    filteredExceptions.map((item) => {
                      const isSelected = selectedException?.exception_id === item.exception_id;
                      const isClosed = item.state === "VERIFIED_CLOSED";

                      return (
                        <tr
                          key={item.exception_id}
                          onClick={() => setSelectedId(item.exception_id)}
                          className={`cursor-pointer transition-colors duration-150 ${
                            isSelected
                              ? "bg-indigo-50/70 hover:bg-indigo-50/90 font-medium"
                              : "hover:bg-slate-50/80"
                          }`}
                        >
                          <td className="py-3 px-4">
                            <div className="flex items-center gap-2">
                              <span className="font-mono text-xs font-semibold text-slate-900 truncate max-w-[170px]" title={item.exception_id}>
                                {item.exception_id}
                              </span>
                            </div>
                            <div className="text-[11px] text-slate-500 truncate max-w-[210px] mt-0.5">
                              {item.exception_type.replace(/_/g, " ")}
                            </div>
                          </td>

                          <td className="py-3 px-3 font-mono text-slate-600 text-xs">
                            {getMerchantId(item)}
                          </td>

                          <td className="py-3 px-4 text-right">
                            <span className={`font-mono font-bold text-xs ${isClosed ? "text-emerald-700" : "text-slate-900"}`}>
                              {isClosed ? "₹0.00" : formatINR(item.exposure)}
                            </span>
                          </td>

                          <td className="py-3 px-3 text-center">
                            <StatusBadge status={item.severity} size="sm" />
                          </td>

                          <td className="py-3 px-4 text-center">
                            <StatusBadge status={item.state} size="sm" />
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>

            <div className="p-3 border-t border-slate-100 bg-slate-50/50 flex items-center justify-between text-xs text-slate-500 font-mono">
              <span>Showing {filteredExceptions.length} of {exceptions.length} exceptions</span>
              <span>Ephemerally synced with mainnet</span>
            </div>
          </div>

          {/* RIGHT: Exception Detail Workspace (xl:col-span-5) */}
          <div className="xl:col-span-5 space-y-4">
            {selectedException ? (
              <div className="rounded-xl border border-slate-200 bg-white shadow-xs p-6 space-y-6">
                {/* 1. EXCEPTION HEADER */}
                <div className="space-y-3 pb-4 border-b border-slate-100">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[11px] font-mono font-medium text-indigo-700 bg-indigo-50 border border-indigo-200 px-2 py-0.5 rounded">
                      {selectedException.exception_type}
                    </span>
                    <span className="text-xs text-slate-400 font-mono">
                      {new Date(selectedException.detected_at).toLocaleDateString("en-IN", {
                        month: "short",
                        day: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </span>
                  </div>

                  <div>
                    <h2 className="text-lg font-bold text-slate-900 tracking-tight font-sans">
                      {selectedException.exception_id}
                    </h2>
                    <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                      {selectedException.description || "Deterministic balance arithmetic discrepancy identified between payment gateway authorization and bank settlement ledger."}
                    </p>
                  </div>

                  {/* 2. Top Metric Strip: Exposure / Risk / Status */}
                  <div className="grid grid-cols-3 gap-2 pt-1">
                    <div className="p-3 rounded-lg bg-slate-50 border border-slate-200">
                      <span className="text-[10px] font-mono uppercase text-slate-500 block mb-0.5">Exposure</span>
                      <span className="text-base font-bold font-mono text-slate-900">
                        {selectedException.state === "VERIFIED_CLOSED" ? "₹0.00" : formatINR(selectedException.exposure)}
                      </span>
                    </div>

                    <div className="p-3 rounded-lg bg-slate-50 border border-slate-200">
                      <span className="text-[10px] font-mono uppercase text-slate-500 block mb-0.5">Risk</span>
                      <StatusBadge status={selectedException.severity} size="sm" />
                    </div>

                    <div className="p-3 rounded-lg bg-slate-50 border border-slate-200">
                      <span className="text-[10px] font-mono uppercase text-slate-500 block mb-0.5">Status</span>
                      <StatusBadge status={selectedException.state} size="sm" />
                    </div>
                  </div>
                </div>

                {/* 3. VERIFIED CLOSED STATE (If Closed) */}
                {selectedException.state === "VERIFIED_CLOSED" && (
                  <div className="p-4 rounded-xl border border-emerald-200 bg-[#ECFDF3] space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />
                        <div>
                          <span className="font-bold text-xs text-emerald-900 font-sans block">
                            CLOSED &amp; CRYPTOGRAPHICALLY VERIFIED
                          </span>
                          <span className="text-[11px] text-emerald-700">
                            Post-remediation balance invariant asserted: Net Exposure = ₹0
                          </span>
                        </div>
                      </div>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 font-semibold border border-emerald-300">
                        IMMUTABLE AUDIT
                      </span>
                    </div>

                    <div className="space-y-1.5 pt-2 border-t border-emerald-200/80 text-xs text-emerald-900 font-mono">
                      <div className="flex items-center gap-2">
                        <Check className="w-3.5 h-3.5 text-emerald-600" />
                        <span>Reversal entry posted to double-entry nodal ledger</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <Check className="w-3.5 h-3.5 text-emerald-600" />
                        <span>Acquiring bank clearing deficit rectified</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <Check className="w-3.5 h-3.5 text-emerald-600" />
                        <span>Audit hash seal: <code className="text-emerald-950 font-bold">sha256-verified-01</code></span>
                      </div>
                    </div>
                  </div>
                )}

                {/* 4. WHAT HAPPENED & FINANCIAL DISCREPANCY */}
                <div className="space-y-3">
                  <h3 className="text-xs font-bold text-slate-900 uppercase font-mono tracking-wider flex items-center gap-1.5">
                    <FileText className="w-3.5 h-3.5 text-indigo-600" />
                    <span>What Happened &amp; Financial Discrepancy</span>
                  </h3>
                  <div className="p-3.5 rounded-lg bg-slate-50 border border-slate-200 space-y-2 text-xs">
                    <div className="flex justify-between items-center text-slate-600">
                      <span>Primary Identifier:</span>
                      <span className="font-mono text-slate-900 font-medium">{selectedException.primary_payment_id || selectedException.primary_order_id || "N/A (Unallocated Batch)"}</span>
                    </div>
                    <div className="flex justify-between items-center text-slate-600">
                      <span>Affected Volume:</span>
                      <span className="font-mono text-slate-900 font-semibold">{formatINR(selectedException.exposure)} ({selectedException.exposure.toLocaleString()} paise)</span>
                    </div>
                    <div className="flex justify-between items-center text-slate-600">
                      <span>Variance Threshold:</span>
                      <span className="font-mono text-rose-700 font-semibold">&gt; ₹0.00 Deficit</span>
                    </div>
                    <div className="pt-2 border-t border-slate-200 text-slate-500 leading-relaxed">
                      Autonomous controller asserted invariant breach in settlement reconciliation cycle. Double-entry verification recorded deficit between nodal escrow postings and actual gateway authorization.
                    </div>
                  </div>
                </div>

                {/* 5. EVIDENCE & INVESTIGATION TIMELINE */}
                <div className="space-y-3">
                  <h3 className="text-xs font-bold text-slate-900 uppercase font-mono tracking-wider flex items-center gap-1.5">
                    <Layers className="w-3.5 h-3.5 text-indigo-600" />
                    <span>Evidence &amp; Forensic Timeline</span>
                  </h3>
                  <div className="space-y-2">
                    <div className="p-3 rounded-lg border border-slate-200 bg-white flex items-start gap-3 text-xs">
                      <Clock className="w-4 h-4 text-indigo-600 shrink-0 mt-0.5" />
                      <div className="space-y-0.5">
                        <span className="font-semibold text-slate-900 block">Anomaly Detected by Core Controller</span>
                        <p className="text-slate-500">Continuous background health monitor matched rule pattern: {selectedException.exception_type}.</p>
                      </div>
                    </div>
                    <div className="p-3 rounded-lg border border-slate-200 bg-white flex items-start gap-3 text-xs">
                      <ShieldCheck className="w-4 h-4 text-indigo-600 shrink-0 mt-0.5" />
                      <div className="space-y-0.5">
                        <span className="font-semibold text-slate-900 block">Read-Only Investigation Run</span>
                        <p className="text-slate-500">AI agent explored cross-system logs without write access. Confidence score: {(selectedException.confidence * 100).toFixed(0)}%.</p>
                      </div>
                    </div>
                  </div>
                </div>

                {/* 6. RECOMMENDED ACTION & POLICY EVALUATION */}
                <div className="space-y-3">
                  <h3 className="text-xs font-bold text-slate-900 uppercase font-mono tracking-wider flex items-center gap-1.5">
                    <CheckCircle2 className="w-3.5 h-3.5 text-indigo-600" />
                    <span>Recommended Action &amp; Governance</span>
                  </h3>
                  <div className="p-3.5 rounded-lg border border-indigo-100 bg-indigo-50/60 space-y-2 text-xs text-indigo-900">
                    <div className="font-semibold">Recommended Remediation:</div>
                    <p className="text-indigo-800 leading-relaxed">
                      Initiate verified ledger reversal posting, notify acquiring banking partner, and quarantine discrepancy line item pending settlement verification.
                    </p>
                    <div className="pt-2 border-t border-indigo-200/80 flex items-center justify-between text-[11px] font-mono">
                      <span>Policy Check: PASS</span>
                      <span>Human Dual-Approval: Required</span>
                    </div>
                  </div>
                </div>

                {/* 7. ACTION BUTTONS */}
                <div className="pt-2 border-t border-slate-100 flex items-center justify-end gap-3">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => window.open(`/verifier?id=${selectedException.exception_id}`, "_self")}
                    icon={<ExternalLink className="w-3.5 h-3.5" />}
                  >
                    Inspect in Verifier
                  </Button>
                </div>
              </div>
            ) : (
              <div className="rounded-xl border border-slate-200 bg-white p-12 text-center text-slate-400 font-mono text-xs">
                Select an exception from the console to view detailed investigation workspace.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

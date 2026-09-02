"use client";

import React, { useState, useEffect } from "react";
import {
  ShieldAlert,
  ShieldCheck,
  Scale,
  ArrowRight,
  RefreshCw,
  AlertTriangle,
  CheckCircle,
  XCircle,
  HelpCircle,
  Lock,
  Layers,
  FileSearch,
  Zap,
} from "lucide-react";
import { VerifierOpinion, ExceptionSummary } from "../types";
import { fetchVerifierOpinion, evaluateVerifierOpinion, fetchExceptions } from "../lib/api";

export function VerifierPanel() {
  const [exceptionId, setExceptionId] = useState("");
  const [recentExceptions, setRecentExceptions] = useState<ExceptionSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [opinion, setOpinion] = useState<VerifierOpinion | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadRecentExceptions();
  }, []);

  const loadRecentExceptions = async () => {
    try {
      const excs = await fetchExceptions(undefined, 10);
      setRecentExceptions(excs || []);
      if (excs && excs.length > 0 && !exceptionId) {
        setExceptionId(excs[0].exception_id);
      }
    } catch (e) {
      console.error("Failed to load exceptions for verifier picker:", e);
    }
  };

  const handleFetchOpinion = async (targetId?: string, forceFresh: boolean = false) => {
    const idToFetch = (targetId || exceptionId).trim();
    if (!idToFetch) return;

    setLoading(true);
    setError(null);

    try {
      let data: VerifierOpinion;
      if (forceFresh) {
        data = await evaluateVerifierOpinion(idToFetch);
      } else {
        data = await fetchVerifierOpinion(idToFetch);
      }
      setOpinion(data);
      if (targetId) setExceptionId(targetId);
    } catch (err: any) {
      setError(err.message || "Failed to retrieve verifier opinion.");
      setOpinion(null);
    } finally {
      setLoading(false);
    }
  };

  const getVerdictStyle = (verdict?: string) => {
    switch (verdict) {
      case "AGREE":
        return {
          bg: "bg-emerald-500/10 border-emerald-500/30 text-emerald-300",
          icon: <CheckCircle className="w-5 h-5 text-emerald-400" />,
          badge: "bg-emerald-500/20 text-emerald-300 border-emerald-500/40",
          desc: "Verifier concurs with primary assessment based on supporting operational evidence.",
        };
      case "TIGHTEN":
        return {
          bg: "bg-amber-500/10 border-amber-500/30 text-amber-300",
          icon: <AlertTriangle className="w-5 h-5 text-amber-400" />,
          badge: "bg-amber-500/20 text-amber-300 border-amber-500/40",
          desc: "Verifier detected risk exposure / evidence gaps and elevated decision conservatism.",
        };
      case "DISPUTE":
        return {
          bg: "bg-rose-500/10 border-rose-500/30 text-rose-300",
          icon: <XCircle className="w-5 h-5 text-rose-400" />,
          badge: "bg-rose-500/20 text-rose-300 border-rose-500/40",
          desc: "Verifier discovered contradictory records and blocked/restricted the action.",
        };
      case "ABSTAIN":
      default:
        return {
          bg: "bg-slate-500/10 border-slate-500/30 text-slate-300",
          icon: <HelpCircle className="w-5 h-5 text-slate-400" />,
          badge: "bg-slate-500/20 text-slate-300 border-slate-500/40",
          desc: "Insufficient independent evidence to formulate confident dissenting opinion.",
        };
    }
  };

  const getPolicyBadge = (policy?: string) => {
    if (!policy) return <span className="text-slate-500">N/A</span>;
    if (policy.includes("ALLOW")) {
      return (
        <span className="px-2.5 py-1 rounded-md text-xs font-mono bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
          {policy}
        </span>
      );
    }
    if (policy.includes("APPROVAL") || policy.includes("REVIEW") || policy.includes("ESCALATION")) {
      return (
        <span className="px-2.5 py-1 rounded-md text-xs font-mono bg-amber-500/20 text-amber-300 border border-amber-500/40">
          {policy}
        </span>
      );
    }
    return (
      <span className="px-2.5 py-1 rounded-md text-xs font-mono bg-rose-500/20 text-rose-300 border border-rose-500/40">
        {policy}
      </span>
    );
  };

  const verdictStyle = getVerdictStyle(opinion?.verdict);

  return (
    <section className="glass-panel rounded-2xl p-6 sm:p-8 border border-slate-800/80 shadow-2xl relative overflow-hidden">
      {/* Background Ambient Glow */}
      <div className="absolute -top-24 -right-24 w-72 h-72 bg-amber-500/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute -bottom-24 -left-24 w-72 h-72 bg-rose-500/10 rounded-full blur-3xl pointer-events-none" />

      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6 pb-6 border-b border-slate-800">
        <div>
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs font-mono mb-2">
            <Scale className="w-3.5 h-3.5 text-amber-400" />
            Tier-1 Adversarial Verifier Active (v2.0)
          </div>
          <h2 className="text-2xl font-bold text-white flex items-center gap-2">
            Adversarial Second-Opinion Safety Layer
          </h2>
          <p className="text-sm text-slate-400 mt-1 max-w-2xl">
            Independent challenger evaluating operational exceptions against contradictory evidence and enforcing deterministic conservative policy composition.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-900/80 border border-slate-800 text-xs text-slate-400 font-mono">
            <Lock className="w-3.5 h-3.5 text-teal-400" />
            <span>Strictly Read-Only Boundary</span>
          </div>
        </div>
      </div>

      {/* Exception Picker & Action Bar */}
      <div className="space-y-4 mb-6">
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <FileSearch className="absolute left-3.5 top-3.5 w-4 h-4 text-slate-500" />
            <input
              type="text"
              placeholder="Enter Exception ID (e.g., EXC-GHOST-001, EXC-REFUND-002)..."
              value={exceptionId}
              onChange={(e) => setExceptionId(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleFetchOpinion()}
              className="w-full bg-slate-900/90 border border-slate-700/80 rounded-xl pl-10 pr-4 py-2.5 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-amber-400/70 focus:ring-1 focus:ring-amber-400/30 font-mono"
            />
          </div>

          <button
            onClick={() => handleFetchOpinion(undefined, false)}
            disabled={loading || !exceptionId.trim()}
            className="inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-400 hover:to-orange-500 text-white font-medium text-sm transition-all duration-200 shadow-lg shadow-amber-500/20 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? (
              <RefreshCw className="w-4 h-4 animate-spin" />
            ) : (
              <Scale className="w-4 h-4" />
            )}
            <span>Evaluate Verifier</span>
          </button>

          <button
            onClick={() => handleFetchOpinion(undefined, true)}
            disabled={loading || !exceptionId.trim()}
            title="Re-run fresh independent adversarial assessment"
            className="inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-slate-800/80 hover:bg-slate-700/80 border border-slate-700 text-slate-300 font-medium text-sm transition-all duration-200 disabled:opacity-50"
          >
            <Zap className="w-4 h-4 text-amber-400" />
            <span>Fresh Audit</span>
          </button>
        </div>

        {/* Quick select recent exceptions */}
        {recentExceptions.length > 0 && (
          <div className="flex items-center gap-2 overflow-x-auto pb-1 text-xs font-mono scrollbar-none">
            <span className="text-slate-500 shrink-0">Quick inspect:</span>
            {recentExceptions.slice(0, 6).map((exc) => (
              <button
                key={exc.exception_id}
                onClick={() => {
                  setExceptionId(exc.exception_id);
                  handleFetchOpinion(exc.exception_id);
                }}
                className={`px-2.5 py-1 rounded-lg border transition-all shrink-0 ${
                  exceptionId === exc.exception_id
                    ? "bg-amber-500/20 border-amber-500/50 text-amber-300 font-semibold"
                    : "bg-slate-900/60 border-slate-800 text-slate-400 hover:border-slate-700 hover:text-slate-200"
                }`}
              >
                {exc.exception_id}
                {exc.source_flag === "live-injected" && (
                  <span className="ml-1 text-[10px] text-cyan-400 font-bold">• live</span>
                )}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Error state */}
      {error && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-sm flex items-start gap-3 mb-6">
          <AlertTriangle className="w-5 h-5 shrink-0 text-rose-400 mt-0.5" />
          <div>
            <p className="font-semibold">Verifier Query Failed</p>
            <p className="text-xs text-rose-300/80 mt-0.5">{error}</p>
          </div>
        </div>
      )}

      {/* Results View */}
      {opinion ? (
        <div className="space-y-6">
          {/* Main Verdict Card */}
          <div className={`p-6 rounded-2xl border ${verdictStyle.bg} relative overflow-hidden`}>
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-4">
              <div className="flex items-center gap-3">
                {verdictStyle.icon}
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono uppercase tracking-wider text-slate-400">
                      Independent Verdict
                    </span>
                    <span className={`px-2.5 py-0.5 rounded-full text-xs font-bold font-mono uppercase ${verdictStyle.badge}`}>
                      {opinion.verdict}
                    </span>
                    <span className="text-xs font-mono text-slate-400">
                      (Confidence: <strong className="text-white">{opinion.confidence}</strong>)
                    </span>
                  </div>
                  <p className="text-xs text-slate-300 mt-0.5">{verdictStyle.desc}</p>
                </div>
              </div>

              <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-900/80 border border-slate-800 text-xs font-mono text-slate-400">
                <span>Opinion ID:</span>
                <span className="text-amber-300 font-semibold">{opinion.opinion_id}</span>
              </div>
            </div>

            {/* Policy Restrictiveness Composition Matrix */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-4 border-t border-slate-800/80">
              <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800">
                <span className="text-[11px] font-mono text-slate-400 uppercase block mb-1">
                  Primary Policy Decision
                </span>
                <div className="flex items-center gap-2">
                  {getPolicyBadge(opinion.original_policy_decision)}
                </div>
              </div>

              <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800">
                <span className="text-[11px] font-mono text-slate-400 uppercase block mb-1">
                  Verifier Recommendation
                </span>
                <div className="flex items-center gap-2">
                  {getPolicyBadge(opinion.recommended_action)}
                </div>
              </div>

              <div className="p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/30">
                <span className="text-[11px] font-mono text-amber-300 uppercase block mb-1 flex items-center justify-between">
                  <span>Composed Final Policy</span>
                  <ShieldCheck className="w-3.5 h-3.5 text-amber-400" />
                </span>
                <div className="flex items-center gap-2">
                  {getPolicyBadge(opinion.final_policy_decision)}
                  {opinion.final_policy_decision !== opinion.original_policy_decision && (
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-orange-500/20 text-orange-300 border border-orange-500/40">
                      TIGHTENED
                    </span>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Reasoning & Grounding Details */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Reasoning breakdown */}
            <div className="p-5 rounded-xl bg-slate-900/60 border border-slate-800 space-y-3">
              <h4 className="text-xs font-mono font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-2">
                <Layers className="w-4 h-4 text-amber-400" />
                Adversarial Evidence Synthesis
              </h4>
              <p className="text-sm text-slate-300 leading-relaxed bg-slate-950/60 p-4 rounded-lg border border-slate-800/60 font-sans">
                {opinion.reasoning_summary}
              </p>
            </div>

            {/* Invariant & Evidence Refs */}
            <div className="p-5 rounded-xl bg-slate-900/60 border border-slate-800 space-y-3">
              <h4 className="text-xs font-mono font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-teal-400" />
                Conservative Policy Invariant Guarantee
              </h4>

              <div className="p-3.5 rounded-lg bg-teal-500/10 border border-teal-500/30 text-xs text-teal-200 font-mono">
                <p className="font-semibold mb-1">
                  ✓ FINAL_RESTRICTIVENESS ≥ ORIGINAL_RESTRICTIVENESS
                </p>
                <p className="text-[11px] text-teal-300/80">
                  The verifier can only strengthen risk controls. It is mathematically barred from loosening a policy or bypassing human approvals.
                </p>
              </div>

              <div>
                <span className="text-[11px] font-mono text-slate-400 uppercase block mb-1.5">
                  Grounded Evidence References ({opinion.evidence_refs.length}):
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {opinion.evidence_refs.map((ref, idx) => (
                    <span
                      key={idx}
                      className="px-2 py-0.5 rounded bg-slate-800 border border-slate-700 text-slate-300 text-xs font-mono"
                    >
                      {ref}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="py-12 text-center rounded-xl bg-slate-900/40 border border-slate-800/60">
          <Scale className="w-10 h-10 text-slate-600 mx-auto mb-3" />
          <p className="text-sm text-slate-400 font-medium">No verifier opinion loaded.</p>
          <p className="text-xs text-slate-500 mt-1 max-w-md mx-auto">
            Select an exception above or click "Evaluate Verifier" to trigger an independent adversarial second opinion.
          </p>
        </div>
      )}
    </section>
  );
}

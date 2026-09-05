"use client";

import React, { useState, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import {
  Scale,
  ShieldCheck,
  AlertTriangle,
  CheckCircle,
  XCircle,
  HelpCircle,
  RefreshCw,
  Zap,
  Lock,
  FileSearch,
  Layers,
} from "lucide-react";
import { VerifierOpinion } from "../types";
import { fetchVerifierOpinion, evaluateVerifierOpinion, fetchExceptions } from "../lib/api";
import { executeWithColdStartRetry } from "../lib/resilience";
import { ColdStartWakingCard } from "./ColdStartWakingCard";
import { Button } from "./ui/Button";
import { SectionHeading } from "./ui/SectionHeading";

export function VerifierPanel() {
  const searchParams = useSearchParams();
  const queryId = searchParams?.get("id") || searchParams?.get("exception_id") || "";
  const [exceptionId, setExceptionId] = useState<string>(queryId);
  const [opinion, setOpinion] = useState<VerifierOpinion | null>(null);
  const [loading, setLoading] = useState(false);
  const [wakingState, setWakingState] = useState<{ attempt: number; isTimeout: boolean } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [recentExceptions, setRecentExceptions] = useState<Array<{ exception_id: string; source_flag?: string }>>([]);

  // Auto-fetch seeded or injected exceptions on mount to populate picker, prioritizing queryId
  useEffect(() => {
    async function loadRecent() {
      try {
        const data = await executeWithColdStartRetry(
          () => fetchExceptions(undefined, 8),
          {
            onWaking: (attempt) => setWakingState({ attempt, isTimeout: false }),
            onRecovered: () => setWakingState(null),
          }
        );
        const items = Array.isArray(data) ? data : (data as any)?.items || [];
        if (Array.isArray(items) && items.length > 0) {
          setRecentExceptions(items);
        }

        const targetId = queryId || (Array.isArray(items) && items.length > 0 ? items[0]?.exception_id : "");
        if (targetId) {
          setExceptionId(targetId);
          handleFetchOpinion(targetId);
        }
        setWakingState(null);
      } catch {
        const fallback = queryId || "EXC-GHOST-001";
        setExceptionId(fallback);
        handleFetchOpinion(fallback);
      }
    }
    loadRecent();
  }, [queryId]);

  const handleFetchOpinion = async (idToFetch?: string, fresh?: boolean) => {
    const targetId = (idToFetch || exceptionId).trim();
    if (!targetId) return;

    setLoading(true);
    setError(null);
    try {
      const data = fresh
        ? await evaluateVerifierOpinion(targetId)
        : await fetchVerifierOpinion(targetId);
      setOpinion(data);
      if (idToFetch) setExceptionId(idToFetch);
    } catch (err: any) {
      setError(err.message || "Failed to load verifier opinion.");
      setOpinion(null);
    } finally {
      setLoading(false);
    }
  };

  const getVerdictStyle = (verdict?: string) => {
    switch (verdict) {
      case "CONCUR":
        return {
          bg: "bg-[#ECFDF3] border-emerald-200 text-emerald-900",
          icon: <CheckCircle className="w-5 h-5 text-emerald-600" />,
          badge: "bg-emerald-100 text-emerald-800 border-emerald-300",
          desc: "Verifier concurs with primary assessment based on supporting operational evidence.",
        };
      case "TIGHTEN":
        return {
          bg: "bg-[#FFFBEB] border-amber-200 text-amber-900",
          icon: <AlertTriangle className="w-5 h-5 text-amber-600" />,
          badge: "bg-amber-100 text-amber-800 border-amber-300",
          desc: "Verifier detected risk exposure / evidence gaps and elevated decision conservatism.",
        };
      case "DISPUTE":
        return {
          bg: "bg-[#FEF2F2] border-rose-200 text-rose-900",
          icon: <XCircle className="w-5 h-5 text-rose-600" />,
          badge: "bg-rose-100 text-rose-800 border-rose-300",
          desc: "Verifier discovered contradictory records and blocked/restricted the action.",
        };
      case "ABSTAIN":
      default:
        return {
          bg: "bg-slate-50 border-slate-200 text-slate-800",
          icon: <HelpCircle className="w-5 h-5 text-slate-500" />,
          badge: "bg-slate-200 text-slate-700 border-slate-300",
          desc: "Insufficient independent evidence to formulate confident dissenting opinion.",
        };
    }
  };

  const getPolicyBadge = (policy?: string) => {
    if (!policy) return <span className="text-slate-400">N/A</span>;
    if (policy.includes("ALLOW")) {
      return (
        <span className="px-2 py-0.5 rounded text-xs font-mono bg-emerald-50 text-emerald-700 border border-emerald-200 font-semibold">
          {policy}
        </span>
      );
    }
    if (policy.includes("APPROVAL") || policy.includes("REVIEW") || policy.includes("ESCALATION")) {
      return (
        <span className="px-2 py-0.5 rounded text-xs font-mono bg-amber-50 text-amber-800 border border-amber-200 font-semibold">
          {policy}
        </span>
      );
    }
    return (
      <span className="px-2 py-0.5 rounded text-xs font-mono bg-rose-50 text-rose-700 border border-rose-200 font-semibold">
        {policy}
      </span>
    );
  };

  const verdictStyle = getVerdictStyle(opinion?.verdict);

  return (
    <section
      id="verifier"
      className="rounded-xl p-5 sm:p-6 border border-slate-200 bg-white shadow-xs relative overflow-hidden"
    >
      {/* Header */}
      <SectionHeading
        icon={<Scale className="w-5 h-5 text-indigo-600" />}
        title="Adversarial Second-Opinion Safety Layer"
        badge={{
          text: "Tier-1 Adversarial Verifier Active",
          icon: <Scale className="w-3 h-3 text-indigo-600" />,
          color: "bg-indigo-50 border-indigo-200 text-indigo-700",
        }}
        description="Independent challenger evaluating operational exceptions against contradictory evidence and enforcing deterministic conservative policy composition."
        action={
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-slate-50 border border-slate-200 text-xs text-slate-600 font-mono">
            <Lock className="w-3 h-3 text-indigo-600" />
            <span>Strictly read-only boundary</span>
          </div>
        }
      />

      {/* Exception Picker & Action Bar */}
      <div className="space-y-3 mb-5">
        <div className="flex flex-col sm:flex-row gap-2">
          <div className="relative flex-1 min-w-0">
            <FileSearch className="absolute left-3 top-2.5 w-4 h-4 text-slate-400" />
            <input
              type="text"
              placeholder="Enter exception ID (e.g. EXC-GHOST-001)..."
              value={exceptionId}
              onChange={(e) => setExceptionId(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleFetchOpinion()}
              className="w-full bg-white border border-slate-200 rounded-lg pl-9 pr-3 h-9 text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 font-mono transition-colors"
            />
          </div>

          <Button
            variant="primary"
            size="sm"
            onClick={() => handleFetchOpinion()}
            disabled={loading || !exceptionId.trim()}
            icon={<Zap className="w-3.5 h-3.5" />}
          >
            {loading ? "Inspecting…" : "Evaluate verifier"}
          </Button>

          <Button
            variant="secondary"
            size="sm"
            onClick={() => handleFetchOpinion(undefined, true)}
            disabled={loading || !exceptionId.trim()}
            title="Re-run fresh LLM adversarial inspection"
            icon={<RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin text-indigo-600" : ""}`} />}
          >
            Fresh audit
          </Button>
        </div>

        {/* Quick select recent exceptions */}
        {recentExceptions.length > 0 && (
          <div className="space-y-1 pt-0.5">
            <span className="text-[11px] font-mono text-slate-500 block font-medium">
              Quick inspect recent exceptions:
            </span>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-1.5">
              {recentExceptions.slice(0, 8).map((exc) => {
                const isSelected = exceptionId === exc.exception_id;
                return (
                  <button
                    key={exc.exception_id}
                    onClick={() => {
                      setExceptionId(exc.exception_id);
                      handleFetchOpinion(exc.exception_id);
                    }}
                    title={exc.exception_id}
                    className={`flex items-center justify-between gap-1.5 p-2 rounded-lg border text-xs font-mono transition-colors text-left min-w-0 cursor-pointer ${
                      isSelected
                        ? "bg-indigo-50 border-indigo-200 text-indigo-900 font-semibold shadow-xs"
                        : "bg-slate-50/60 border-slate-200 text-slate-600 hover:border-slate-300 hover:text-slate-900 hover:bg-slate-100"
                    }`}
                  >
                    <span className="truncate flex-1 min-w-0" title={exc.exception_id}>
                      {exc.exception_id}
                    </span>
                    {exc.source_flag === "live-injected" && (
                      <span className="shrink-0 px-1 py-0.2 rounded text-[9px] bg-indigo-50 text-indigo-700 font-bold border border-indigo-200">
                        live
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* Error / Waking state */}
      {wakingState ? (
        <div className="mb-5">
          <ColdStartWakingCard
            attempt={wakingState.attempt}
            maxAttempts={6}
            isTimeout={wakingState.isTimeout}
            onRetry={() => handleFetchOpinion()}
            description="Connecting to Adversarial Verifier…"
            compact
          />
        </div>
      ) : error ? (
        <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-start gap-2.5 mb-5">
          <AlertTriangle className="w-4 h-4 shrink-0 text-rose-600 mt-0.5" />
          <div>
            <p className="font-semibold">Verifier inspection error</p>
            <p className="text-rose-600 mt-0.5">{error}</p>
          </div>
        </div>
      ) : null}

      {/* Opinion Results Display */}
      {loading ? (
        <div className="py-12 text-center text-slate-500 font-mono text-xs">
          <RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2 text-indigo-600" />
          Running independent adversarial verification analysis...
        </div>
      ) : opinion ? (
        <div className="space-y-4">
          {/* Verdict Banner */}
          <div className={`p-4 rounded-xl border ${verdictStyle.bg} transition-colors shadow-xs`}>
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-3">
              <div className="flex items-center gap-2.5">
                {verdictStyle.icon}
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] font-mono text-slate-600 uppercase tracking-wider font-semibold">
                      Adversarial Verdict:
                    </span>
                    <span className={`px-2 py-0.5 rounded text-[11px] font-mono font-bold border ${verdictStyle.badge}`}>
                      {opinion.verdict}
                    </span>
                  </div>
                  <p className="text-xs text-slate-700 mt-0.5 font-medium">{verdictStyle.desc}</p>
                </div>
              </div>

              <div className="text-right font-mono text-xs text-slate-500 shrink-0">
                <span>Opinion ID: </span>
                <span className="text-indigo-700 font-semibold">{opinion.opinion_id}</span>
              </div>
            </div>

            {/* Policy Restrictiveness Composition Matrix */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-3 border-t border-slate-200/80">
              <div className="p-3 rounded-lg bg-white border border-slate-200 shadow-xs">
                <span className="text-[11px] font-mono text-slate-500 block mb-1">
                  Primary policy decision
                </span>
                <div className="flex items-center gap-2">
                  {getPolicyBadge(opinion.original_policy_decision)}
                </div>
              </div>

              <div className="p-3 rounded-lg bg-white border border-slate-200 shadow-xs">
                <span className="text-[11px] font-mono text-slate-500 block mb-1">
                  Verifier recommendation
                </span>
                <div className="flex items-center gap-2">
                  {getPolicyBadge(opinion.recommended_action)}
                </div>
              </div>

              <div className="p-3 rounded-lg bg-indigo-50/70 border border-indigo-200 shadow-xs">
                <span className="text-[11px] font-mono text-indigo-900 block mb-1 flex items-center justify-between font-semibold">
                  <span>Composed final policy</span>
                  <ShieldCheck className="w-3.5 h-3.5 text-indigo-600" />
                </span>
                <div className="flex items-center gap-2">
                  {getPolicyBadge(opinion.final_policy_decision)}
                  {opinion.final_policy_decision !== opinion.original_policy_decision && (
                    <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-amber-100 text-amber-800 border border-amber-300 font-bold">
                      TIGHTENED
                    </span>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Reasoning & Grounding Details */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Reasoning breakdown */}
            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-2">
              <h3 className="text-[11px] font-mono font-semibold text-slate-700 uppercase tracking-wider flex items-center gap-2">
                <Layers className="w-3.5 h-3.5 text-indigo-600" />
                Adversarial Evidence Synthesis
              </h3>
              <p className="text-xs text-slate-700 leading-relaxed bg-white p-3 rounded-lg border border-slate-200 font-sans">
                {opinion.reasoning_summary}
              </p>
            </div>

            {/* Invariant & Evidence Refs */}
            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-2.5">
              <h3 className="text-[11px] font-mono font-semibold text-slate-700 uppercase tracking-wider flex items-center gap-2">
                <ShieldCheck className="w-3.5 h-3.5 text-indigo-600" />
                Conservative Policy Invariant Guarantee
              </h3>

              <div className="p-2.5 rounded-lg bg-indigo-50 border border-indigo-200 text-xs text-indigo-900 font-mono">
                <p className="font-semibold mb-0.5">
                  &bull; FINAL_RESTRICTIVENESS &ge; ORIGINAL_RESTRICTIVENESS
                </p>
                <p className="text-[11px] text-indigo-700">
                  The verifier can only strengthen risk controls. It is mathematically barred from loosening a policy or bypassing human approvals.
                </p>
              </div>

              <div>
                <span className="text-[11px] font-mono text-slate-500 block mb-1">
                  Grounded Evidence References ({opinion.evidence_refs.length}):
                </span>
                <div className="flex flex-wrap gap-1">
                  {opinion.evidence_refs.map((ref, idx) => (
                    <span
                      key={idx}
                      className="px-1.5 py-0.5 rounded bg-white border border-slate-200 text-slate-700 text-xs font-mono"
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
        <div className="py-10 text-center rounded-xl bg-slate-50 border border-slate-200">
          <Scale className="w-8 h-8 text-slate-400 mx-auto mb-2" />
          <p className="text-xs text-slate-500 font-mono">
            Select an exception ID above and click <span className="text-indigo-600 font-semibold">Evaluate verifier</span> to review the independent safety assessment.
          </p>
        </div>
      )}
    </section>
  );
}

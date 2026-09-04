"use client";

import React, { useState, useEffect } from "react";
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
  const [exceptionId, setExceptionId] = useState<string>("");
  const [opinion, setOpinion] = useState<VerifierOpinion | null>(null);
  const [loading, setLoading] = useState(false);
  const [wakingState, setWakingState] = useState<{ attempt: number; isTimeout: boolean } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [recentExceptions, setRecentExceptions] = useState<Array<{ exception_id: string; source_flag?: string }>>([]);

  // Auto-fetch seeded or injected exceptions on mount to populate picker
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
          // Default to the first exception if not set
          if (!exceptionId && items[0]?.exception_id) {
            setExceptionId(items[0].exception_id);
            handleFetchOpinion(items[0].exception_id);
          }
        }
        setWakingState(null);
      } catch {
        // Fallback to demo default
        const fallback = "EXC-GHOST-001";
        setExceptionId(fallback);
        handleFetchOpinion(fallback);
      }
    }
    loadRecent();
  }, []);

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
          bg: "bg-emerald-950/20 border-emerald-800/40 text-emerald-300",
          icon: <CheckCircle className="w-4 h-4 text-emerald-400" />,
          badge: "bg-emerald-950/30 text-emerald-300 border-emerald-800/40",
          desc: "Verifier concurs with primary assessment based on supporting operational evidence.",
        };
      case "TIGHTEN":
        return {
          bg: "bg-amber-950/20 border-amber-800/40 text-amber-300",
          icon: <AlertTriangle className="w-4 h-4 text-amber-400" />,
          badge: "bg-amber-950/30 text-amber-300 border-amber-800/40",
          desc: "Verifier detected risk exposure / evidence gaps and elevated decision conservatism.",
        };
      case "DISPUTE":
        return {
          bg: "bg-rose-950/20 border-rose-800/40 text-rose-300",
          icon: <XCircle className="w-4 h-4 text-rose-400" />,
          badge: "bg-rose-950/30 text-rose-300 border-rose-800/40",
          desc: "Verifier discovered contradictory records and blocked/restricted the action.",
        };
      case "ABSTAIN":
      default:
        return {
          bg: "bg-slate-900 border-slate-800 text-slate-300",
          icon: <HelpCircle className="w-4 h-4 text-slate-400" />,
          badge: "bg-slate-800 text-slate-300 border-slate-700",
          desc: "Insufficient independent evidence to formulate confident dissenting opinion.",
        };
    }
  };

  const getPolicyBadge = (policy?: string) => {
    if (!policy) return <span className="text-slate-500">N/A</span>;
    if (policy.includes("ALLOW")) {
      return (
        <span className="px-2 py-0.5 rounded text-xs font-mono bg-emerald-950/30 text-emerald-300 border border-emerald-800/40 font-medium">
          {policy}
        </span>
      );
    }
    if (policy.includes("APPROVAL") || policy.includes("REVIEW") || policy.includes("ESCALATION")) {
      return (
        <span className="px-2 py-0.5 rounded text-xs font-mono bg-amber-950/30 text-amber-300 border border-amber-800/40 font-medium">
          {policy}
        </span>
      );
    }
    return (
      <span className="px-2 py-0.5 rounded text-xs font-mono bg-rose-950/30 text-rose-300 border border-rose-800/40 font-medium">
        {policy}
      </span>
    );
  };

  const verdictStyle = getVerdictStyle(opinion?.verdict);

  return (
    <section
      id="verifier"
      className="rounded-xl p-5 sm:p-6 border border-slate-800/80 bg-[#0d121d] shadow-sm relative overflow-hidden"
    >
      {/* Header */}
      <SectionHeading
        icon={<Scale className="w-5 h-5 text-sky-400" />}
        title="Adversarial Second-Opinion Safety Layer"
        badge={{
          text: "Tier-1 Adversarial Verifier Active (v2.0)",
          icon: <Scale className="w-3 h-3 text-sky-400" />,
          color: "bg-sky-950/30 border-sky-800/40 text-sky-300",
        }}
        description="Independent challenger evaluating operational exceptions against contradictory evidence and enforcing deterministic conservative policy composition."
        action={
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-[#090d16] border border-slate-800 text-xs text-slate-400 font-mono">
            <Lock className="w-3 h-3 text-sky-400" />
            <span>Strictly read-only boundary</span>
          </div>
        }
      />

      {/* Exception Picker & Action Bar */}
      <div className="space-y-3 mb-5">
        <div className="flex flex-col sm:flex-row gap-2">
          <div className="relative flex-1 min-w-0">
            <FileSearch className="absolute left-3 top-2.5 w-4 h-4 text-slate-500" />
            <input
              type="text"
              placeholder="Enter exception ID (e.g. EXC-GHOST-001)..."
              value={exceptionId}
              onChange={(e) => setExceptionId(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleFetchOpinion()}
              className="w-full bg-[#090d16] border border-slate-700/80 rounded-lg pl-9 pr-3 h-9 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-sky-500 focus:ring-1 focus:ring-sky-500 font-mono transition-colors"
            />
          </div>

          <Button
            onClick={() => handleFetchOpinion(undefined, false)}
            disabled={loading || !exceptionId.trim()}
            variant="primary"
            size="md"
            icon={loading ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Scale className="w-3.5 h-3.5" />}
            className="shrink-0"
          >
            Evaluate verifier
          </Button>

          <Button
            onClick={() => handleFetchOpinion(undefined, true)}
            disabled={loading || !exceptionId.trim()}
            variant="secondary"
            size="md"
            icon={<Zap className="w-3.5 h-3.5 text-amber-400" />}
            title="Re-run fresh independent adversarial assessment"
            className="shrink-0"
          >
            Fresh audit
          </Button>
        </div>

        {/* Quick select recent exceptions */}
        {recentExceptions.length > 0 && (
          <div className="space-y-1 pt-0.5">
            <span className="text-[11px] font-mono text-slate-400 block font-medium">
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
                        ? "bg-sky-950/40 border-sky-800/60 text-sky-200 font-medium"
                        : "bg-[#090d16] border-slate-800/80 text-slate-400 hover:border-slate-700 hover:text-slate-200"
                    }`}
                  >
                    <span className="truncate flex-1 min-w-0" title={exc.exception_id}>
                      {exc.exception_id}
                    </span>
                    {exc.source_flag === "live-injected" && (
                      <span className="shrink-0 px-1 py-0.2 rounded text-[9px] bg-sky-950/40 text-sky-300 font-bold border border-sky-800/40">
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
        <div className="p-3 rounded-lg bg-rose-950/30 border border-rose-800/40 text-rose-300 text-xs flex items-start gap-2.5 mb-5">
          <AlertTriangle className="w-4 h-4 shrink-0 text-rose-400 mt-0.5" />
          <div>
            <p className="font-semibold">Verifier inspection error</p>
            <p className="text-rose-300/80 mt-0.5">{error}</p>
          </div>
        </div>
      ) : null}

      {/* Opinion Results Display */}
      {loading ? (
        <div className="py-12 text-center text-slate-400 font-mono text-xs">
          <RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2 text-sky-400" />
          Running independent adversarial verification analysis...
        </div>
      ) : opinion ? (
        <div className="space-y-4">
          {/* Verdict Banner */}
          <div className={`p-4 rounded-xl border ${verdictStyle.bg} transition-colors`}>
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-3">
              <div className="flex items-center gap-2.5">
                {verdictStyle.icon}
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] font-mono text-slate-400 uppercase tracking-wider">
                      Adversarial Verdict:
                    </span>
                    <span className={`px-2 py-0.5 rounded text-[11px] font-mono font-bold border ${verdictStyle.badge}`}>
                      {opinion.verdict}
                    </span>
                  </div>
                  <p className="text-xs text-slate-200 mt-0.5">{verdictStyle.desc}</p>
                </div>
              </div>

              <div className="text-right font-mono text-xs text-slate-400 shrink-0">
                <span>Opinion ID: </span>
                <span className="text-sky-300 font-medium">{opinion.opinion_id}</span>
              </div>
            </div>

            {/* Policy Restrictiveness Composition Matrix */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-3 border-t border-slate-800/80">
              <div className="p-3 rounded-lg bg-[#090d16] border border-slate-800">
                <span className="text-[11px] font-mono text-slate-400 block mb-1">
                  Primary policy decision
                </span>
                <div className="flex items-center gap-2">
                  {getPolicyBadge(opinion.original_policy_decision)}
                </div>
              </div>

              <div className="p-3 rounded-lg bg-[#090d16] border border-slate-800">
                <span className="text-[11px] font-mono text-slate-400 block mb-1">
                  Verifier recommendation
                </span>
                <div className="flex items-center gap-2">
                  {getPolicyBadge(opinion.recommended_action)}
                </div>
              </div>

              <div className="p-3 rounded-lg bg-sky-950/20 border border-sky-800/40">
                <span className="text-[11px] font-mono text-sky-300 block mb-1 flex items-center justify-between">
                  <span>Composed final policy</span>
                  <ShieldCheck className="w-3.5 h-3.5 text-sky-400" />
                </span>
                <div className="flex items-center gap-2">
                  {getPolicyBadge(opinion.final_policy_decision)}
                  {opinion.final_policy_decision !== opinion.original_policy_decision && (
                    <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-orange-950/30 text-orange-300 border border-orange-800/40 font-bold">
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
            <div className="p-4 rounded-xl bg-[#090d16] border border-slate-800/80 space-y-2">
              <h3 className="text-[11px] font-mono font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-2">
                <Layers className="w-3.5 h-3.5 text-sky-400" />
                Adversarial Evidence Synthesis
              </h3>
              <p className="text-xs text-slate-300 leading-relaxed bg-[#0d121d] p-3 rounded-lg border border-slate-800/80 font-sans">
                {opinion.reasoning_summary}
              </p>
            </div>

            {/* Invariant & Evidence Refs */}
            <div className="p-4 rounded-xl bg-[#090d16] border border-slate-800/80 space-y-2.5">
              <h3 className="text-[11px] font-mono font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-2">
                <ShieldCheck className="w-3.5 h-3.5 text-sky-400" />
                Conservative Policy Invariant Guarantee
              </h3>

              <div className="p-2.5 rounded-lg bg-sky-950/30 border border-sky-800/40 text-xs text-sky-200 font-mono">
                <p className="font-medium mb-0.5">
                  &bull; FINAL_RESTRICTIVENESS &ge; ORIGINAL_RESTRICTIVENESS
                </p>
                <p className="text-[11px] text-sky-300/80">
                  The verifier can only strengthen risk controls. It is mathematically barred from loosening a policy or bypassing human approvals.
                </p>
              </div>

              <div>
                <span className="text-[11px] font-mono text-slate-400 block mb-1">
                  Grounded Evidence References ({opinion.evidence_refs.length}):
                </span>
                <div className="flex flex-wrap gap-1">
                  {opinion.evidence_refs.map((ref, idx) => (
                    <span
                      key={idx}
                      className="px-1.5 py-0.5 rounded bg-[#0d121d] border border-slate-700 text-slate-300 text-xs font-mono"
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
        <div className="py-10 text-center rounded-xl bg-[#090d16] border border-slate-800/80">
          <Scale className="w-8 h-8 text-slate-600 mx-auto mb-2" />
          <p className="text-xs text-slate-400 font-mono">
            Select an exception ID above and click <span className="text-sky-300">Evaluate verifier</span> to review the independent safety assessment.
          </p>
        </div>
      )}
    </section>
  );
}

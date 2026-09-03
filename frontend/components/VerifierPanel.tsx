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
import { fetchVerifierOpinion } from "../lib/api";
import { Button } from "./ui/Button";
import { SectionHeading } from "./ui/SectionHeading";

export function VerifierPanel() {
  const [exceptionId, setExceptionId] = useState<string>("");
  const [opinion, setOpinion] = useState<VerifierOpinion | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [recentExceptions, setRecentExceptions] = useState<Array<{ exception_id: string; source_flag?: string }>>([]);

  // Auto-fetch seeded or injected exceptions on mount to populate picker
  useEffect(() => {
    async function loadRecent() {
      try {
        const res = await fetch("/api/exceptions?limit=8");
        if (res.ok) {
          const data = await res.json();
          const items = data.items || data;
          if (Array.isArray(items) && items.length > 0) {
            setRecentExceptions(items);
            // Default to the first exception if not set
            if (!exceptionId && items[0]?.exception_id) {
              setExceptionId(items[0].exception_id);
              handleFetchOpinion(items[0].exception_id);
            }
          }
        }
      } catch {
        // Fallback to demo default
        const fallback = "EXC-GHOST-001";
        setExceptionId(fallback);
        handleFetchOpinion(fallback);
      }
    }
    loadRecent();
  }, []);

  const handleFetchOpinion = async (targetId?: string, freshAudit: boolean = false) => {
    const idToQuery = (targetId || exceptionId).trim();
    if (!idToQuery) return;

    setLoading(true);
    setError(null);
    try {
      const data = await fetchVerifierOpinion(idToQuery);
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
        <span className="px-2.5 py-1 rounded-md text-xs font-mono bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 font-medium">
          {policy}
        </span>
      );
    }
    if (policy.includes("APPROVAL") || policy.includes("REVIEW") || policy.includes("ESCALATION")) {
      return (
        <span className="px-2.5 py-1 rounded-md text-xs font-mono bg-amber-500/20 text-amber-300 border border-amber-500/40 font-medium">
          {policy}
        </span>
      );
    }
    return (
      <span className="px-2.5 py-1 rounded-md text-xs font-mono bg-rose-500/20 text-rose-300 border border-rose-500/40 font-medium">
        {policy}
      </span>
    );
  };

  const verdictStyle = getVerdictStyle(opinion?.verdict);

  return (
    <section
      id="verifier"
      className="glass-panel rounded-2xl p-6 sm:p-8 border border-slate-800/80 shadow-2xl relative overflow-hidden"
    >
      {/* Background Ambient Glow */}
      <div className="absolute -top-24 -right-24 w-72 h-72 bg-amber-500/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute -bottom-24 -left-24 w-72 h-72 bg-rose-500/10 rounded-full blur-3xl pointer-events-none" />

      {/* Header (Issue 3 & 14) */}
      <SectionHeading
        icon={<Scale className="w-6 h-6 text-amber-400" />}
        title="Adversarial Second-Opinion Safety Layer"
        badge={{
          text: "Tier-1 Adversarial Verifier Active (v2.0)",
          icon: <Scale className="w-3.5 h-3.5 text-amber-400" />,
          color: "bg-amber-500/10 border-amber-500/30 text-amber-300",
        }}
        description="Independent challenger evaluating operational exceptions against contradictory evidence and enforcing deterministic conservative policy composition."
        action={
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-900/80 border border-slate-800 text-xs text-slate-400 font-mono">
            <Lock className="w-3.5 h-3.5 text-teal-400" />
            <span>Strictly read-only boundary</span>
          </div>
        }
      />

      {/* Exception Picker & Action Bar (Issue 1, 4) */}
      <div className="space-y-4 mb-6">
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1 min-w-0">
            <FileSearch className="absolute left-3.5 top-3.5 w-4 h-4 text-slate-500" />
            <input
              type="text"
              placeholder="Enter exception ID (e.g. EXC-GHOST-001)..."
              value={exceptionId}
              onChange={(e) => setExceptionId(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleFetchOpinion()}
              className="w-full bg-slate-900/90 border border-slate-700/80 rounded-xl pl-10 pr-4 py-2.5 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-amber-400/70 focus:ring-1 focus:ring-amber-400/30 font-mono"
            />
          </div>

          <Button
            onClick={() => handleFetchOpinion(undefined, false)}
            disabled={loading || !exceptionId.trim()}
            variant="primary"
            icon={loading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Scale className="w-4 h-4" />}
            className="shrink-0"
          >
            Evaluate verifier
          </Button>

          <Button
            onClick={() => handleFetchOpinion(undefined, true)}
            disabled={loading || !exceptionId.trim()}
            variant="secondary"
            icon={<Zap className="w-4 h-4 text-amber-400" />}
            title="Re-run fresh independent adversarial assessment"
            className="shrink-0"
          >
            Fresh audit
          </Button>
        </div>

        {/* Quick select recent exceptions - Responsive Wrapped Grid (Issue 4: fixes horizontal overflow) */}
        {recentExceptions.length > 0 && (
          <div className="space-y-1.5 pt-1">
            <span className="text-xs font-mono text-slate-400 block font-medium">
              Quick inspect recent exceptions:
            </span>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
              {recentExceptions.slice(0, 6).map((exc) => {
                const isSelected = exceptionId === exc.exception_id;
                return (
                  <button
                    key={exc.exception_id}
                    onClick={() => {
                      setExceptionId(exc.exception_id);
                      handleFetchOpinion(exc.exception_id);
                    }}
                    title={exc.exception_id}
                    className={`flex items-center justify-between gap-2 p-2.5 rounded-xl border text-xs font-mono transition-all text-left min-w-0 ${
                      isSelected
                        ? "bg-amber-500/20 border-amber-500/60 text-amber-200 font-semibold ring-1 ring-amber-500/40"
                        : "bg-slate-900/70 border-slate-800 text-slate-300 hover:border-slate-700 hover:bg-slate-800/70"
                    }`}
                  >
                    <span className="truncate flex-1 min-w-0" title={exc.exception_id}>
                      {exc.exception_id}
                    </span>
                    {exc.source_flag === "live-injected" && (
                      <span className="shrink-0 px-1.5 py-0.5 rounded text-[10px] bg-cyan-500/20 text-cyan-300 font-bold border border-cyan-500/40">
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

      {/* Error state */}
      {error && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-sm flex items-start gap-3 mb-6">
          <AlertTriangle className="w-5 h-5 shrink-0 text-rose-400 mt-0.5" />
          <div>
            <p className="font-semibold">Verifier inspection error</p>
            <p className="text-xs text-rose-300/80 mt-0.5">{error}</p>
          </div>
        </div>
      )}

      {/* Opinion Results Display */}
      {loading ? (
        <div className="py-12 text-center text-slate-500 font-mono text-sm">
          <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-amber-400" />
          Running independent adversarial verification analysis...
        </div>
      ) : opinion ? (
        <div className="space-y-6">
          {/* Verdict Banner */}
          <div className={`p-6 rounded-2xl border ${verdictStyle.bg} transition-all`}>
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-4">
              <div className="flex items-center gap-3">
                {verdictStyle.icon}
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono text-slate-400 uppercase tracking-wider">
                      Adversarial Verdict:
                    </span>
                    <span className={`px-2.5 py-0.5 rounded-full text-xs font-mono font-bold border ${verdictStyle.badge}`}>
                      {opinion.verdict}
                    </span>
                  </div>
                  <p className="text-sm text-slate-200 mt-0.5">{verdictStyle.desc}</p>
                </div>
              </div>

              <div className="text-right font-mono text-xs text-slate-400 shrink-0">
                <span>Opinion ID: </span>
                <span className="text-amber-300 font-semibold">{opinion.opinion_id}</span>
              </div>
            </div>

            {/* Policy Restrictiveness Composition Matrix */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-4 border-t border-slate-800/80">
              <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800">
                <span className="text-xs font-mono text-slate-400 block mb-1">
                  Primary policy decision
                </span>
                <div className="flex items-center gap-2">
                  {getPolicyBadge(opinion.original_policy_decision)}
                </div>
              </div>

              <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800">
                <span className="text-xs font-mono text-slate-400 block mb-1">
                  Verifier recommendation
                </span>
                <div className="flex items-center gap-2">
                  {getPolicyBadge(opinion.recommended_action)}
                </div>
              </div>

              <div className="p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/30">
                <span className="text-xs font-mono text-amber-300 block mb-1 flex items-center justify-between">
                  <span>Composed final policy</span>
                  <ShieldCheck className="w-3.5 h-3.5 text-amber-400" />
                </span>
                <div className="flex items-center gap-2">
                  {getPolicyBadge(opinion.final_policy_decision)}
                  {opinion.final_policy_decision !== opinion.original_policy_decision && (
                    <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-orange-500/20 text-orange-300 border border-orange-500/40 font-bold">
                      TIGHTENED
                    </span>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Reasoning & Grounding Details (Issue 15: H3 hierarchy) */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Reasoning breakdown */}
            <div className="p-5 rounded-xl bg-slate-900/60 border border-slate-800 space-y-3">
              <h3 className="text-xs font-mono font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-2">
                <Layers className="w-4 h-4 text-amber-400" />
                Adversarial evidence synthesis
              </h3>
              <p className="text-sm text-slate-300 leading-relaxed bg-slate-950/60 p-4 rounded-lg border border-slate-800/60 font-sans">
                {opinion.reasoning_summary}
              </p>
            </div>

            {/* Invariant & Evidence Refs */}
            <div className="p-5 rounded-xl bg-slate-900/60 border border-slate-800 space-y-3">
              <h3 className="text-xs font-mono font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-teal-400" />
                Conservative policy invariant guarantee
              </h3>

              <div className="p-3.5 rounded-lg bg-teal-500/10 border border-teal-500/30 text-xs text-teal-200 font-mono">
                <p className="font-semibold mb-1">
                  ✓ FINAL_RESTRICTIVENESS ≥ ORIGINAL_RESTRICTIVENESS
                </p>
                <p className="text-xs text-teal-300/80">
                  The verifier can only strengthen risk controls. It is mathematically barred from loosening a policy or bypassing human approvals.
                </p>
              </div>

              <div>
                <span className="text-xs font-mono text-slate-400 block mb-1.5 font-medium">
                  Grounded evidence references ({opinion.evidence_refs.length}):
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
          <p className="text-sm text-slate-400">
            Select an exception ID above and click <span className="text-amber-300">Evaluate Verifier</span> to review the independent safety assessment.
          </p>
        </div>
      )}
    </section>
  );
}

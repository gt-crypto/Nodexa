"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  Zap,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  RefreshCw,
  ExternalLink,
  ChevronRight,
  Terminal,
  Shield,
  Activity,
  Database,
  Cpu,
  Search,
  Clock,
  Radio,
  Layers,
  ArrowRight,
  BadgeAlert,
} from "lucide-react";
import {
  SupportedFamily,
  InjectionResponse,
  InjectionStageEvent,
  InjectedCaseSummary,
} from "../types";
import {
  fetchSupportedFamilies,
  injectAnomaly,
  fetchInjectedCases,
  fetchExceptions,
  createInjectionStream,
  BACKEND_URL,
} from "../lib/api";
import { executeWithColdStartRetry } from "../lib/resilience";
import { ColdStartWakingCard } from "./ColdStartWakingCard";
import { Button } from "./ui/Button";
import { SectionHeading } from "./ui/SectionHeading";

// ─── Stage Metadata ────────────────────────────────────────────────────────

const STAGE_META: Record<
  string,
  { label: string; icon: React.ReactNode; color: string }
> = {
  INJECTION_ACCEPTED: {
    label: "Accepted",
    icon: <Radio className="w-3.5 h-3.5" />,
    color: "text-indigo-600",
  },
  RECORDS_GENERATED: {
    label: "Operational Records Generated",
    icon: <Database className="w-3.5 h-3.5" />,
    color: "text-cyan-600",
  },
  CONTROLS_RUNNING: {
    label: "Deterministic Controls Executing",
    icon: <Cpu className="w-3.5 h-3.5" />,
    color: "text-indigo-600",
  },
  DETECTION_RUNNING: {
    label: "Exception Detection Running",
    icon: <Search className="w-3.5 h-3.5" />,
    color: "text-indigo-600",
  },
  EXCEPTION_DETECTED: {
    label: "Exception Detected",
    icon: <AlertTriangle className="w-3.5 h-3.5" />,
    color: "text-amber-600",
  },
  NO_EXCEPTION_REQUIRED: {
    label: "Verified Clean (Legitimate Case)",
    icon: <CheckCircle2 className="w-3.5 h-3.5" />,
    color: "text-emerald-600",
  },
  INVESTIGATION_RUNNING: {
    label: "AI Investigation Running",
    icon: <Activity className="w-3.5 h-3.5" />,
    color: "text-cyan-600",
  },
  INVESTIGATION_COMPLETED: {
    label: "Investigation Completed",
    icon: <CheckCircle2 className="w-3.5 h-3.5" />,
    color: "text-emerald-600",
  },
  RISK_EVALUATION_RUNNING: {
    label: "Risk Assessment Running",
    icon: <Layers className="w-3.5 h-3.5" />,
    color: "text-amber-600",
  },
  RISK_EVALUATED: {
    label: "Risk Evaluated",
    icon: <CheckCircle2 className="w-3.5 h-3.5" />,
    color: "text-emerald-600",
  },
  POLICY_EVALUATION_RUNNING: {
    label: "Policy Evaluation Running",
    icon: <Shield className="w-3.5 h-3.5" />,
    color: "text-rose-600",
  },
  POLICY_DECIDED: {
    label: "Policy Decision Issued",
    icon: <CheckCircle2 className="w-3.5 h-3.5" />,
    color: "text-emerald-600",
  },
  AUDIT_RECORDED: {
    label: "Audit Record Persisted",
    icon: <Terminal className="w-3.5 h-3.5" />,
    color: "text-slate-500",
  },
  INJECTION_COMPLETE: {
    label: "Injection Complete",
    icon: <CheckCircle2 className="w-3.5 h-3.5" />,
    color: "text-emerald-600",
  },
  ERROR: {
    label: "Error",
    icon: <XCircle className="w-3.5 h-3.5" />,
    color: "text-rose-600",
  },
};

// ─── Severity Badge ────────────────────────────────────────────────────────

function SeverityBadge({ severity }: { severity: string }) {
  const map: Record<string, string> = {
    CRITICAL: "bg-rose-50 border-rose-200 text-rose-700",
    HIGH: "bg-amber-50 border-amber-200 text-amber-700",
    MEDIUM: "bg-cyan-50 border-cyan-200 text-cyan-700",
    LOW: "bg-slate-100 border-slate-200 text-slate-600",
  };
  return (
    <span
      className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold font-mono border ${
        map[severity] || map.LOW
      }`}
    >
      {severity}
    </span>
  );
}

// ─── Family Card with Clear Affordance (Issue 16) ────────────────────────────

function FamilyCard({
  family,
  selected,
  onClick,
}: {
  family: SupportedFamily;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      id={`family-card-${family.family}`}
      onClick={onClick}
      className={`w-full text-left p-3.5 rounded-xl border transition-all duration-150 cursor-pointer flex flex-col justify-between focus:outline-none focus:ring-2 focus:ring-indigo-500/30 ${
        selected
          ? "bg-indigo-50/70 border-indigo-500 ring-1 ring-indigo-500/30 shadow-xs"
          : "bg-white border-slate-200 hover:border-slate-300 hover:bg-slate-50/60 shadow-2xs"
      }`}
    >
      <div>
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-xs font-bold font-mono text-slate-900 tracking-tight">
            {family.family.replace(/_/g, " ")}
          </span>
          <SeverityBadge severity={family.severity} />
        </div>
        <p className="text-[11px] text-slate-500 leading-relaxed mb-2.5">
          {family.description}
        </p>
      </div>

      <div className="flex items-center justify-between pt-2 border-t border-slate-100 min-h-[30px]">
        <div className="flex items-center gap-1.5 flex-wrap">
          <span
            className={`text-[10px] px-1.5 py-0.5 rounded font-mono font-medium ${
              family.category === "ANOMALY"
                ? "bg-rose-50 text-rose-700 border border-rose-200"
                : "bg-emerald-50 text-emerald-700 border border-emerald-200"
            }`}
          >
            {family.category}
          </span>
          {family.is_legitimate && (
            <span className="px-1.5 py-0.5 rounded text-[10px] font-mono text-slate-600 bg-slate-100 border border-slate-200">
              Edge case
            </span>
          )}
        </div>

        {/* Explicit Affordance */}
        {selected ? (
          <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded bg-indigo-100 text-indigo-700 border border-indigo-200 font-mono shrink-0">
            <CheckCircle2 className="w-3 h-3 text-indigo-600" />
            Selected
          </span>
        ) : (
          <span className="inline-flex items-center text-[11px] font-medium px-1.5 py-0.5 text-slate-400 hover:text-indigo-600 font-mono shrink-0">
            Select →
          </span>
        )}
      </div>
    </button>
  );
}

// ─── Progress Stream ───────────────────────────────────────────────────────

function ProgressLog({ stages }: { stages: InjectionStageEvent[] }) {
  const bottomRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [stages.length]);

  return (
    <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-3.5 max-h-48 overflow-y-auto font-mono text-xs space-y-1.5">
      {stages.map((st, i) => {
        const meta = STAGE_META[st.stage] || {
          label: st.stage,
          icon: <Activity className="w-3 h-3" />,
          color: "text-slate-500",
        };
        return (
          <div key={i} className="flex items-start gap-2 leading-relaxed">
            <span className="text-slate-400 shrink-0 num-tabular">
              {new Date(st.timestamp).toLocaleTimeString()}
            </span>
            <span className={`shrink-0 mt-0.5 ${meta.color}`}>{meta.icon}</span>
            <span className={`font-semibold shrink-0 ${meta.color}`}>
              {meta.label}
            </span>
            {st.message && (
              <span className="text-slate-600 truncate">{st.message}</span>
            )}
          </div>
        );
      })}
      <div ref={bottomRef} />
    </div>
  );
}

// ─── Result Card ───────────────────────────────────────────────────────────

function InjectionResultCard({
  result,
  onOpenException,
}: {
  result: InjectionResponse;
  onOpenException: (id: string) => void;
}) {
  const exposure = result.exposure ?? 0;
  return (
    <div className="mt-4 p-4 rounded-xl bg-white border border-indigo-200 shadow-xs space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
        <h3 className="text-sm font-bold text-slate-900">
          Live Injection Complete
        </h3>
        <span className="ml-auto inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-[10px] font-bold bg-indigo-50 border border-indigo-200 text-indigo-700 font-mono">
          <Radio className="w-2.5 h-2.5" /> LIVE-INJECTED
        </span>
      </div>

      {/* ID Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-xs font-mono">
        <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200">
          <p className="text-slate-500 mb-0.5 text-[10px] font-medium">Injection ID</p>
          <p className="text-indigo-600 truncate font-semibold" title={result.injection_id}>{result.injection_id}</p>
        </div>
        <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200">
          <p className="text-slate-500 mb-0.5 text-[10px] font-medium">Exception ID</p>
          <p className="text-amber-700 font-mono text-xs select-all truncate tracking-tight font-semibold" title={result.linked_exception_id ?? "—"}>
            {result.linked_exception_id ?? "—"}
          </p>
        </div>
        <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200">
          <p className="text-slate-500 mb-0.5 text-[10px] font-medium">Family</p>
          <p className="text-slate-900 truncate font-medium">{result.exception_family}</p>
        </div>
        <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200">
          <p className="text-slate-500 mb-0.5 text-[10px] font-medium">Exposure</p>
          <p className="text-rose-600 font-bold num-tabular">
            ₹{((exposure) / 100).toLocaleString("en-IN", { minimumFractionDigits: 2 })}
          </p>
        </div>
        <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200">
          <p className="text-slate-500 mb-0.5 text-[10px] font-medium">State</p>
          <p className="text-slate-700">{result.exception_state ?? "—"}</p>
        </div>
        <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200">
          <p className="text-slate-500 mb-0.5 text-[10px] font-medium">Source Flag</p>
          <p className="text-indigo-600 font-semibold">{result.source_flag}</p>
        </div>
      </div>

      {/* Generated IDs */}
      <div className="text-xs font-mono">
        <p className="text-slate-500 mb-1.5 text-[10px] font-medium">Generated identifiers:</p>
        <div className="flex flex-wrap gap-1.5">
          {Object.entries(result.generated_record_identifiers).flatMap(
            ([, ids]) =>
              (ids as string[]).map((id) => (
                <span
                  key={id}
                  className="px-2 py-0.5 rounded bg-slate-100 border border-slate-200 text-slate-700 text-[11px]"
                >
                  {id}
                </span>
              ))
          )}
        </div>
      </div>

      {/* Open Exception Button */}
      {result.linked_exception_id && (
        <Button
          id={`open-exception-${result.linked_exception_id}`}
          onClick={() => onOpenException(result.linked_exception_id!)}
          variant="primary"
          icon={<ExternalLink className="w-3.5 h-3.5" />}
          className="w-full"
        >
          Open exception in verification engine
        </Button>
      )}
    </div>
  );
}

// ─── History Table ────────────────────────────────────────────────────────

function HistoryTable({
  cases,
  onSelect,
}: {
  cases: InjectedCaseSummary[];
  onSelect: (id: string) => void;
}) {
  if (cases.length === 0) return null;
  return (
    <div className="mt-5">
      <h3 className="text-xs font-bold text-slate-900 mb-2.5 flex items-center gap-1.5 font-sans">
        <Clock className="w-3.5 h-3.5 text-slate-500" />
        <span>Injection History ({cases.length})</span>
      </h3>
      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-2xs">
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="border-b border-slate-200 text-slate-600 text-[11px] uppercase tracking-wider bg-slate-50 font-sans font-semibold">
              <th className="py-2.5 px-3">Injection ID</th>
              <th className="py-2.5 px-3">Family</th>
              <th className="py-2.5 px-3">Exception ID</th>
              <th className="py-2.5 px-3">Status</th>
              <th className="py-2.5 px-3 text-right">Triggered At</th>
              <th className="py-2.5 px-3">Source Flag</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {cases.map((c) => (
              <tr
                key={c.injection_id}
                className="hover:bg-slate-50 transition cursor-pointer"
                onClick={() =>
                  c.linked_exception_id && onSelect(c.linked_exception_id)
                }
              >
                <td className="py-2.5 px-3 text-indigo-600 font-semibold font-mono text-xs">{c.injection_id}</td>
                <td className="py-2.5 px-3 text-slate-900 font-sans font-medium">{c.exception_family}</td>
                <td className="py-2.5 px-3 text-amber-700 font-semibold font-mono text-xs">
                  {c.linked_exception_id ?? "—"}
                </td>
                <td className="py-2.5 px-3">
                  <span className="px-2 py-0.5 rounded text-[11px] font-sans font-medium bg-slate-100 text-slate-700 border border-slate-200">
                    {c.status}
                  </span>
                </td>
                <td className="py-2.5 px-3 text-slate-500 text-right num-tabular font-sans text-xs">
                  {c.triggered_at ? new Date(c.triggered_at).toLocaleTimeString() : "—"}
                </td>
                <td className="py-2.5 px-3 text-indigo-600 font-mono text-xs">{c.source_flag}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ─── Main Component ────────────────────────────────────────────────────────

export const LiveInjectionConsole: React.FC = () => {
  const [families, setFamilies] = useState<SupportedFamily[]>([]);
  const [selectedFamily, setSelectedFamily] = useState<string>("");
  const [operatorId, setOperatorId] = useState<string>("demo-operator");
  const [streamMode, setStreamMode] = useState<boolean>(true);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [stages, setStages] = useState<InjectionStageEvent[]>([]);
  const [result, setResult] = useState<InjectionResponse | null>(null);
  const [history, setHistory] = useState<InjectedCaseSummary[]>([]);
  const [highlightedExceptionId, setHighlightedExceptionId] = useState<
    string | null
  >(null);

  const [wakingState, setWakingState] = useState<{ attempt: number; isTimeout: boolean } | null>(null);

  const loadHistory = useCallback(async () => {
    try {
      const res = await fetchInjectedCases();
      setHistory(Array.isArray(res) ? res : (res as any)?.cases || []);
    } catch {
      // Backend may not be ready yet
    }
  }, []);

  useEffect(() => {
    async function init() {
      try {
        const [resFam, resHist] = await Promise.all([
          executeWithColdStartRetry(
            () => fetchSupportedFamilies(),
            {
              onWaking: (attempt) => setWakingState({ attempt, isTimeout: false }),
              onRecovered: () => setWakingState(null),
            }
          ).catch((err) => {
            if (wakingState && wakingState.attempt >= 6) {
              setWakingState({ attempt: 6, isTimeout: true });
            }
            return [];
          }),
          fetchInjectedCases().catch(() => []),
        ]);
        const famList = Array.isArray(resFam) ? resFam : (resFam as any)?.families || [];
        setFamilies(famList);
        if (famList.length) {
          setSelectedFamily(famList[0].family);
        }
        setHistory(Array.isArray(resHist) ? resHist : (resHist as any)?.cases || []);
        if (famList.length > 0) {
          setWakingState(null);
        }
      } catch {
        // Handled gracefully
      }
    }
    init();
  }, []);

  const handleOpenException = useCallback((excId: string) => {
    setHighlightedExceptionId(excId);
    const el = document.getElementById("verification-engine");
    if (el) {
      el.scrollIntoView({ behavior: "smooth" });
    }
  }, []);

  const handleInjectSSE = useCallback(async () => {
    if (!selectedFamily) return;
    setLoading(true);
    setError(null);
    setStages([]);
    setResult(null);

    const idempotencyKey = `web-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    const es = createInjectionStream(selectedFamily, operatorId, idempotencyKey);
    let isCompleted = false;

    // The backend streams SSE payloads via standard unnamed data messages
    es.onmessage = (ev: MessageEvent) => {
      try {
        const data = JSON.parse(ev.data);
        if (data.stage === "ERROR") {
          setError(data.message || data.error || "Injection failed");
          es.close();
          setLoading(false);
          return;
        }

        if (data.stage === "INJECTION_COMPLETE") {
          isCompleted = true;
          setStages((prev) => [...prev, data]);
          const resultData: InjectionResponse = data.data || data;
          setResult(resultData);
          loadHistory();
          es.close();
          setLoading(false);
          return;
        }

        // Add intermediate pipeline execution stage
        setStages((prev) => [...prev, data]);
      } catch (err) {
        console.error("Failed to parse SSE payload:", err);
      }
    };

    // Support custom named events if emitted
    es.addEventListener("stage", (ev: MessageEvent) => {
      try {
        const data: InjectionStageEvent = JSON.parse(ev.data);
        setStages((prev) => [...prev, data]);
      } catch {}
    });

    es.addEventListener("complete", (ev: MessageEvent) => {
      try {
        isCompleted = true;
        const data: InjectionResponse = JSON.parse(ev.data);
        setResult(data);
        loadHistory();
      } catch {}
      es.close();
      setLoading(false);
    });

    es.addEventListener("error_event", (ev: MessageEvent) => {
      try {
        const data = JSON.parse(ev.data);
        setError(data.error || data.message || "Injection failed");
      } catch {}
      es.close();
      setLoading(false);
    });

    es.onerror = () => {
      // Normal close after completion triggers EOF in EventSource - ignore if completed
      if (!isCompleted) {
        setError("Connection to injection stream lost");
      }
      es.close();
      setLoading(false);
    };
  }, [selectedFamily, operatorId, loadHistory]);

  const handleInjectSync = useCallback(async () => {
    if (!selectedFamily) return;
    setLoading(true);
    setError(null);
    setStages([]);
    setResult(null);

    try {
      const data = await injectAnomaly(selectedFamily, operatorId);
      setStages(data.stages || []);
      setResult(data);
      loadHistory();
    } catch (e: any) {
      setError(e.message || "Injection failed");
    } finally {
      setLoading(false);
    }
  }, [selectedFamily, operatorId, loadHistory]);

  const handleInject = streamMode ? handleInjectSSE : handleInjectSync;

  return (
    <section className="py-6" id="injection">
      <div className="rounded-xl p-5 sm:p-6 border border-slate-200 bg-white shadow-xs relative overflow-hidden">
        {/* Brand Accent Bar */}
        <div className="absolute top-0 left-0 right-0 h-0.5 bg-gradient-to-r from-indigo-500/80 via-cyan-400/60 to-transparent" />

        {/* Section Header */}
        <SectionHeading
          icon={<Zap className="w-5 h-5 text-indigo-600" />}
          title="Digital-Twin Live Anomaly Injection"
          badge={{
            text: "Tier-1 Digital Twin Active",
            icon: <Radio className="w-3.5 h-3.5 text-indigo-600" />,
            color: "bg-indigo-50 border-indigo-200 text-indigo-700",
          }}
          description="Inject a fresh synthetic anomaly at runtime. The case enters the exact same canonical pipeline as seeded data — deterministic controls → detection → AI investigation → risk → policy → audit. No shortcuts, zero benchmark contamination."
          action={
            <div
              role="radiogroup"
              aria-label="Injection execution mode"
              className="flex items-center gap-1 text-xs font-mono bg-slate-100 p-1 rounded-lg border border-slate-200"
            >
              <button
                role="radio"
                aria-checked={streamMode}
                onClick={() => setStreamMode(true)}
                className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition-all duration-150 focus:outline-none focus:ring-1 focus:ring-indigo-500 cursor-pointer ${
                  streamMode
                    ? "bg-white text-slate-900 font-bold shadow-xs"
                    : "text-slate-500 hover:text-slate-900"
                }`}
              >
                SSE stream
              </button>
              <button
                role="radio"
                aria-checked={!streamMode}
                onClick={() => setStreamMode(false)}
                className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition-all duration-150 focus:outline-none focus:ring-1 focus:ring-indigo-500 cursor-pointer ${
                  !streamMode
                    ? "bg-white text-slate-900 font-bold shadow-xs"
                    : "text-slate-500 hover:text-slate-900"
                }`}
              >
                Synchronous
              </button>
            </div>
          }
        />

        {/* Safety Notice */}
        <div className="mt-3.5 flex items-start gap-2.5 p-3 rounded-lg bg-amber-50 border border-amber-200 text-xs text-amber-800 leading-relaxed">
          <BadgeAlert className="w-4 h-4 shrink-0 mt-0.5 text-amber-600" />
          <span>
            This creates a <strong>brand-new synthetic case</strong> with
            runtime-generated identifiers (prefixed <code>INJ…</code>). It is
            tagged <code>source_flag=live-injected</code> and{" "}
            <strong>never</strong> enters the benchmark ground truth or affects
            scoring.
          </span>
        </div>

        {/* Family Selector */}
        <div className="mt-5">
          <h3 className="text-xs font-bold text-slate-700 mb-2.5 font-mono uppercase tracking-wider">
            Select Anomaly Family
          </h3>
          {wakingState ? (
            <div className="py-2">
              <ColdStartWakingCard
                attempt={wakingState.attempt}
                maxAttempts={6}
                isTimeout={wakingState.isTimeout}
                description="Connecting to Live Anomaly Injection Engine…"
                compact
              />
            </div>
          ) : families.length === 0 ? (
            <div className="text-xs text-slate-500 font-mono">
              Loading families… (requires backend connection)
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-2.5">
              {families.map((f) => (
                <FamilyCard
                  key={f.family}
                  family={f}
                  selected={selectedFamily === f.family}
                  onClick={() => setSelectedFamily(f.family)}
                />
              ))}
            </div>
          )}
        </div>

        {/* Operator ID + Inject Button */}
        <div className="mt-4 flex flex-wrap items-center gap-2.5">
          <div className="relative w-full sm:w-64">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 text-xs font-mono font-medium">
              Operator:
            </span>
            <input
              id="operator-id-input"
              type="text"
              value={operatorId}
              onChange={(e) => setOperatorId(e.target.value)}
              placeholder="demo-operator"
              className="w-full bg-white border border-slate-300 rounded-lg pl-20 pr-3 py-1.5 text-xs font-mono text-slate-900 placeholder-slate-400 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 shadow-2xs"
            />
          </div>

          <Button
            id="inject-anomaly-btn"
            onClick={handleInject}
            disabled={loading || !selectedFamily}
            variant="primary"
            loading={loading}
            icon={<Zap className="w-3.5 h-3.5" />}
          >
            {loading ? "Injecting…" : "Inject live anomaly"}
          </Button>
        </div>

        {/* Error State */}
        {error && (
          <div className="mt-3.5 flex items-start gap-2 p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-xs">
            <XCircle className="w-4 h-4 shrink-0 mt-0.5 text-rose-600" />
            <span>{error}</span>
          </div>
        )}

        {/* Progress Log */}
        {stages.length > 0 && <ProgressLog stages={stages} />}

        {/* Result Card */}
        {result && (
          <InjectionResultCard
            result={result}
            onOpenException={handleOpenException}
          />
        )}

        {/* Highlighted Exception Notice */}
        {highlightedExceptionId && (
          <div className="mt-3.5 flex items-center gap-2.5 p-3 rounded-lg bg-indigo-50 border border-indigo-200 text-indigo-700 text-xs font-mono">
            <ArrowRight className="w-3.5 h-3.5 shrink-0 text-indigo-600" />
            <span>
              Exception{" "}
              <strong className="text-slate-900 font-bold">{highlightedExceptionId}</strong>{" "}
              → Enter this ID in the verification engine below to inspect the
              full lifecycle.
            </span>
          </div>
        )}

        {/* Injection History */}
        <HistoryTable cases={history} onSelect={handleOpenException} />
      </div>
    </section>
  );
};

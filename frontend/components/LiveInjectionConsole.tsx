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
} from "../lib/api";
import { Button } from "./ui/Button";
import { SectionHeading } from "./ui/SectionHeading";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000";

// ─── Stage Metadata ────────────────────────────────────────────────────────

const STAGE_META: Record<
  string,
  { label: string; icon: React.ReactNode; color: string }
> = {
  INJECTION_ACCEPTED: {
    label: "Accepted",
    icon: <Radio className="w-3.5 h-3.5" />,
    color: "text-teal-400",
  },
  RECORDS_GENERATED: {
    label: "Operational Records Generated",
    icon: <Database className="w-3.5 h-3.5" />,
    color: "text-cyan-400",
  },
  CONTROLS_RUNNING: {
    label: "Deterministic Controls Executing",
    icon: <Cpu className="w-3.5 h-3.5" />,
    color: "text-blue-400",
  },
  DETECTION_RUNNING: {
    label: "Exception Detection Running",
    icon: <Search className="w-3.5 h-3.5" />,
    color: "text-purple-400",
  },
  EXCEPTION_DETECTED: {
    label: "Exception Detected",
    icon: <AlertTriangle className="w-3.5 h-3.5" />,
    color: "text-amber-400",
  },
  NO_EXCEPTION_REQUIRED: {
    label: "Verified Clean (Legitimate Case)",
    icon: <CheckCircle2 className="w-3.5 h-3.5" />,
    color: "text-emerald-400",
  },
  INVESTIGATION_RUNNING: {
    label: "AI Investigation Running",
    icon: <Activity className="w-3.5 h-3.5" />,
    color: "text-violet-400",
  },
  INVESTIGATION_COMPLETED: {
    label: "Investigation Completed",
    icon: <CheckCircle2 className="w-3.5 h-3.5" />,
    color: "text-emerald-400",
  },
  RISK_EVALUATION_RUNNING: {
    label: "Risk Assessment Running",
    icon: <Layers className="w-3.5 h-3.5" />,
    color: "text-orange-400",
  },
  RISK_EVALUATED: {
    label: "Risk Evaluated",
    icon: <CheckCircle2 className="w-3.5 h-3.5" />,
    color: "text-emerald-400",
  },
  POLICY_EVALUATION_RUNNING: {
    label: "Policy Evaluation Running",
    icon: <Shield className="w-3.5 h-3.5" />,
    color: "text-rose-400",
  },
  POLICY_DECIDED: {
    label: "Policy Decision Issued",
    icon: <CheckCircle2 className="w-3.5 h-3.5" />,
    color: "text-emerald-400",
  },
  AUDIT_RECORDED: {
    label: "Audit Record Persisted",
    icon: <Terminal className="w-3.5 h-3.5" />,
    color: "text-slate-300",
  },
  INJECTION_COMPLETE: {
    label: "Injection Complete",
    icon: <CheckCircle2 className="w-3.5 h-3.5" />,
    color: "text-emerald-400",
  },
  ERROR: {
    label: "Error",
    icon: <XCircle className="w-3.5 h-3.5" />,
    color: "text-rose-400",
  },
};

// ─── Severity Badge ────────────────────────────────────────────────────────

function SeverityBadge({ severity }: { severity: string }) {
  const map: Record<string, string> = {
    CRITICAL: "bg-rose-500/15 border-rose-500/30 text-rose-300",
    HIGH: "bg-orange-500/15 border-orange-500/30 text-orange-300",
    MEDIUM: "bg-amber-500/15 border-amber-500/30 text-amber-300",
    LOW: "bg-slate-700/40 border-slate-600/40 text-slate-400",
  };
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-bold font-mono border ${
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
      className={`w-full text-left p-4 rounded-xl border transition-all duration-150 cursor-pointer flex flex-col justify-between focus:outline-none focus:ring-2 focus:ring-teal-500/40 ${
        selected
          ? "bg-teal-500/15 border-teal-400/60 ring-1 ring-teal-400/30 shadow-md shadow-teal-500/10"
          : "bg-slate-900/70 border-slate-750 hover:border-teal-500/40 hover:bg-slate-800/70"
      }`}
    >
      <div>
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-bold font-mono text-white tracking-tight">
            {family.family.replace(/_/g, " ")}
          </span>
          <SeverityBadge severity={family.severity} />
        </div>
        <p className="text-xs text-slate-300 leading-relaxed mb-3">
          {family.description}
        </p>
      </div>

      <div className="flex items-center justify-between pt-2.5 border-t border-slate-800/80 min-h-[36px]">
        <div className="flex items-center gap-1.5 flex-wrap">
          <span
            className={`text-xs px-2 py-0.5 rounded font-mono font-medium ${
              family.category === "ANOMALY"
                ? "bg-rose-900/30 text-rose-300 border border-rose-800/50"
                : "bg-emerald-900/30 text-emerald-300 border border-emerald-800/50"
            }`}
          >
            {family.category}
          </span>
          {family.is_legitimate && (
            <span className="px-1.5 py-0.5 rounded text-[11px] font-mono text-slate-400 bg-slate-800/80 border border-slate-700/60">
              Edge case
            </span>
          )}
        </div>

        {/* Explicit Affordance (Issue 16 & Major Issue 2) */}
        {selected ? (
          <span className="inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-1 rounded-full bg-teal-500/25 text-teal-300 border border-teal-400/40 font-mono shrink-0">
            <CheckCircle2 className="w-3.5 h-3.5 text-teal-300" />
            Selected
          </span>
        ) : (
          <span className="inline-flex items-center text-xs font-medium px-2 py-1 text-slate-400 hover:text-teal-300 font-mono shrink-0">
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
    <div className="mt-4 rounded-xl border border-slate-700/60 bg-slate-950/70 p-3.5 max-h-48 overflow-y-auto font-mono text-xs space-y-2">
      {stages.map((st, i) => {
        const meta = STAGE_META[st.stage] || {
          label: st.stage,
          icon: <Activity className="w-3.5 h-3.5" />,
          color: "text-slate-400",
        };
        return (
          <div key={i} className="flex items-start gap-2 leading-relaxed">
            <span className="text-slate-600 shrink-0">
              {new Date(st.timestamp).toLocaleTimeString()}
            </span>
            <span className={`shrink-0 mt-0.5 ${meta.color}`}>{meta.icon}</span>
            <span className={`font-semibold shrink-0 ${meta.color}`}>
              {meta.label}
            </span>
            {st.message && (
              <span className="text-slate-300 truncate">{st.message}</span>
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
    <div className="mt-5 p-5 rounded-xl bg-slate-950/80 border border-teal-500/30 space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
        <h3 className="text-base font-bold text-white">
          Live injection complete
        </h3>
        <span className="ml-auto inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-teal-500/20 border border-teal-400/40 text-teal-300 animate-pulse font-mono">
          <Radio className="w-3 h-3" /> LIVE-INJECTED
        </span>
      </div>

      {/* ID Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5 text-xs font-mono">
        <div className="p-2.5 rounded-lg bg-slate-900/70 border border-slate-800">
          <p className="text-slate-400 mb-0.5 font-medium">Injection ID</p>
          <p className="text-teal-300 truncate" title={result.injection_id}>{result.injection_id}</p>
        </div>
        <div className="p-2.5 rounded-lg bg-slate-900/70 border border-slate-800">
          <p className="text-slate-400 mb-0.5 font-medium">Exception ID</p>
          <p className="text-amber-300 font-mono text-xs select-all truncate tracking-tight" title={result.linked_exception_id ?? "—"}>
            {result.linked_exception_id ?? "—"}
          </p>
        </div>
        <div className="p-2.5 rounded-lg bg-slate-900/70 border border-slate-800">
          <p className="text-slate-400 mb-0.5 font-medium">Family</p>
          <p className="text-white truncate">{result.exception_family}</p>
        </div>
        <div className="p-2.5 rounded-lg bg-slate-900/70 border border-slate-800">
          <p className="text-slate-400 mb-0.5 font-medium">Exposure</p>
          <p className="text-rose-300 font-bold">
            ₹{((exposure) / 100).toLocaleString("en-IN", { minimumFractionDigits: 2 })}
          </p>
        </div>
        <div className="p-2.5 rounded-lg bg-slate-900/70 border border-slate-800">
          <p className="text-slate-400 mb-0.5 font-medium">State</p>
          <p className="text-slate-200">{result.exception_state ?? "—"}</p>
        </div>
        <div className="p-2.5 rounded-lg bg-slate-900/70 border border-slate-800">
          <p className="text-slate-400 mb-0.5 font-medium">Source flag</p>
          <p className="text-teal-400">{result.source_flag}</p>
        </div>
      </div>

      {/* Generated IDs */}
      <div className="text-xs font-mono">
        <p className="text-slate-400 mb-1.5 font-medium">Generated identifiers:</p>
        <div className="flex flex-wrap gap-1.5">
          {Object.entries(result.generated_record_identifiers).flatMap(
            ([, ids]) =>
              (ids as string[]).map((id) => (
                <span
                  key={id}
                  className="px-2 py-0.5 rounded bg-slate-800/80 border border-slate-700 text-slate-300"
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
          icon={<ExternalLink className="w-4 h-4" />}
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
    <div className="mt-6">
      <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
        <Clock className="w-4 h-4 text-slate-400" />
        <span>Injection history ({cases.length})</span>
      </h3>
      <div className="overflow-x-auto rounded-xl border border-slate-800/70 bg-slate-900/50">
        <table className="w-full text-left text-xs font-mono">
          <thead>
            <tr className="border-b border-slate-800 text-slate-400 text-xs bg-slate-950/40">
              <th className="py-2.5 px-3">Injection ID</th>
              <th className="py-2.5 px-3">Family</th>
              <th className="py-2.5 px-3">Exception ID</th>
              <th className="py-2.5 px-3">Status</th>
              <th className="py-2.5 px-3">Triggered at</th>
              <th className="py-2.5 px-3">Source flag</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/50">
            {cases.map((c) => (
              <tr
                key={c.injection_id}
                className="hover:bg-slate-800/30 transition cursor-pointer"
                onClick={() =>
                  c.linked_exception_id && onSelect(c.linked_exception_id)
                }
              >
                <td className="py-2.5 px-3 text-teal-300">{c.injection_id}</td>
                <td className="py-2.5 px-3 text-slate-300">{c.exception_family}</td>
                <td className="py-2.5 px-3 text-amber-300 font-semibold">
                  {c.linked_exception_id ?? "—"}
                </td>
                <td className="py-2.5 px-3">
                  <span className="px-2 py-0.5 rounded text-xs bg-slate-800 text-slate-300 border border-slate-700">
                    {c.status}
                  </span>
                </td>
                <td className="py-2.5 px-3 text-slate-400">
                  {c.triggered_at ? new Date(c.triggered_at).toLocaleTimeString() : "—"}
                </td>
                <td className="py-2.5 px-3 text-teal-400">{c.source_flag}</td>
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
        const res = await fetchSupportedFamilies();
        const famList = Array.isArray(res) ? res : (res as any)?.families || [];
        setFamilies(famList);
        if (famList.length) {
          setSelectedFamily(famList[0].family);
        }
      } catch {
        // Handled gracefully
      }
      loadHistory();
    }
    init();
  }, [loadHistory]);

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
    const url = `${BACKEND_URL}/demo/inject/stream?family=${encodeURIComponent(
      selectedFamily
    )}&operator=${encodeURIComponent(operatorId)}&key=${idempotencyKey}`;

    const es = new EventSource(url);

    es.addEventListener("stage", (ev: MessageEvent) => {
      try {
        const data: InjectionStageEvent = JSON.parse(ev.data);
        setStages((prev) => [...prev, data]);
      } catch {}
    });

    es.addEventListener("complete", (ev: MessageEvent) => {
      try {
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
        setError(data.error || "Injection failed");
      } catch {}
      es.close();
      setLoading(false);
    });

    es.onerror = () => {
      setError("Connection to injection stream lost");
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
    <section className="py-8" id="injection">
      <div className="glass-panel rounded-2xl p-6 sm:p-8 border border-slate-800 relative overflow-hidden">
        {/* Glow effect */}
        <div className="absolute top-0 left-0 -ml-20 -mt-20 w-72 h-72 bg-teal-500/8 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute bottom-0 right-0 -mr-20 -mb-20 w-64 h-64 bg-violet-500/6 rounded-full blur-3xl pointer-events-none" />

        {/* Section Header (Issue 3 & Issue 14: Semantic H2) */}
        <SectionHeading
          icon={<Zap className="w-6 h-6 text-teal-400" />}
          title="Digital-Twin Live Anomaly Injection"
          badge={{
            text: "Tier-1 Digital Twin Active (v2.0)",
            icon: <Radio className="w-3.5 h-3.5 text-teal-400" />,
            color: "bg-teal-500/10 border-teal-500/30 text-teal-300",
          }}
          description="Inject a fresh synthetic anomaly at runtime. The case enters the exact same canonical pipeline as seeded data — deterministic controls → detection → AI investigation → risk → policy → audit. No shortcuts, zero benchmark contamination."
          action={
            <div
              role="radiogroup"
              aria-label="Injection execution mode"
              className="flex items-center gap-1 text-xs font-mono bg-slate-900/90 p-1 rounded-xl border border-slate-800"
            >
              <button
                role="radio"
                aria-checked={streamMode}
                onClick={() => setStreamMode(true)}
                className={`px-3 py-1.5 rounded-lg font-medium transition-all duration-150 focus:outline-none focus:ring-2 focus:ring-teal-500/40 cursor-pointer ${
                  streamMode
                    ? "bg-teal-500 text-slate-950 font-bold shadow-sm shadow-teal-500/20"
                    : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/60"
                }`}
              >
                SSE stream
              </button>
              <button
                role="radio"
                aria-checked={!streamMode}
                onClick={() => setStreamMode(false)}
                className={`px-3 py-1.5 rounded-lg font-medium transition-all duration-150 focus:outline-none focus:ring-2 focus:ring-teal-500/40 cursor-pointer ${
                  !streamMode
                    ? "bg-teal-500 text-slate-950 font-bold shadow-sm shadow-teal-500/20"
                    : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/60"
                }`}
              >
                Synchronous
              </button>
            </div>
          }
        />

        {/* Safety Notice */}
        <div className="mt-4 flex items-start gap-2.5 p-3.5 rounded-xl bg-amber-500/5 border border-amber-500/20 text-xs text-amber-300/90 leading-relaxed">
          <BadgeAlert className="w-4 h-4 shrink-0 mt-0.5 text-amber-400" />
          <span>
            This creates a <strong>brand-new synthetic case</strong> with
            runtime-generated identifiers (prefixed <code>INJ…</code>). It is
            tagged <code>source_flag=live-injected</code> and{" "}
            <strong>never</strong> enters the benchmark ground truth or affects
            scoring.
          </span>
        </div>

        {/* Family Selector (Sentence case heading - Finding #6) */}
        <div className="mt-6">
          <h3 className="text-xs font-semibold text-slate-300 mb-3 font-mono">
            Select anomaly family
          </h3>
          {families.length === 0 ? (
            <div className="text-xs text-slate-500 font-mono">
              Loading families… (requires backend connection)
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
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

        {/* Operator ID + Inject Button (Issue 24: Constrained Operator Input Width) */}
        <div className="mt-5 flex flex-wrap items-center gap-3">
          <div className="relative w-full sm:w-72">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 text-xs font-mono font-medium">
              Operator:
            </span>
            <input
              id="operator-id-input"
              type="text"
              value={operatorId}
              onChange={(e) => setOperatorId(e.target.value)}
              placeholder="demo-operator"
              className="w-full bg-slate-900/90 border border-slate-700/80 rounded-xl pl-20 pr-3 py-2 text-xs font-mono text-white placeholder-slate-500 focus:outline-none focus:border-teal-500 focus:ring-1 focus:ring-teal-500/30"
            />
          </div>

          <Button
            id="inject-anomaly-btn"
            onClick={handleInject}
            disabled={loading || !selectedFamily}
            variant="primary"
            loading={loading}
            icon={<Zap className="w-4 h-4" />}
          >
            {loading ? "Injecting…" : "Inject live anomaly"}
          </Button>
        </div>

        {/* Error State */}
        {error && (
          <div className="mt-4 flex items-start gap-2.5 p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/25 text-rose-300 text-xs">
            <XCircle className="w-4 h-4 shrink-0 mt-0.5" />
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
          <div className="mt-4 flex items-center gap-3 p-3 rounded-xl bg-violet-500/10 border border-violet-500/25 text-violet-300 text-xs font-mono">
            <ArrowRight className="w-4 h-4 shrink-0" />
            <span>
              Exception{" "}
              <strong className="text-violet-200">{highlightedExceptionId}</strong>{" "}
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

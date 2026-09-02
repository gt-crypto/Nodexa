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

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000";

// ─── Stage Metadata ────────────────────────────────────────────────────────

const STAGE_META: Record<
  string,
  { label: string; icon: React.ReactNode; color: string }
> = {
  INJECTION_ACCEPTED: {
    label: "Accepted",
    icon: <Radio className="w-3 h-3" />,
    color: "text-teal-400",
  },
  RECORDS_GENERATED: {
    label: "Operational Records Generated",
    icon: <Database className="w-3 h-3" />,
    color: "text-cyan-400",
  },
  CONTROLS_RUNNING: {
    label: "Deterministic Controls Executing",
    icon: <Cpu className="w-3 h-3" />,
    color: "text-blue-400",
  },
  DETECTION_RUNNING: {
    label: "Exception Detection Running",
    icon: <Search className="w-3 h-3" />,
    color: "text-purple-400",
  },
  EXCEPTION_DETECTED: {
    label: "Exception Detected",
    icon: <AlertTriangle className="w-3 h-3" />,
    color: "text-amber-400",
  },
  NO_EXCEPTION_REQUIRED: {
    label: "Verified Clean (Legitimate Case)",
    icon: <CheckCircle2 className="w-3 h-3" />,
    color: "text-emerald-400",
  },
  INVESTIGATION_RUNNING: {
    label: "AI Investigation Running",
    icon: <Activity className="w-3 h-3" />,
    color: "text-violet-400",
  },
  INVESTIGATION_COMPLETED: {
    label: "Investigation Completed",
    icon: <CheckCircle2 className="w-3 h-3" />,
    color: "text-emerald-400",
  },
  RISK_EVALUATION_RUNNING: {
    label: "Risk Assessment Running",
    icon: <Layers className="w-3 h-3" />,
    color: "text-orange-400",
  },
  RISK_EVALUATED: {
    label: "Risk Evaluated",
    icon: <CheckCircle2 className="w-3 h-3" />,
    color: "text-emerald-400",
  },
  POLICY_EVALUATION_RUNNING: {
    label: "Policy Evaluation Running",
    icon: <Shield className="w-3 h-3" />,
    color: "text-rose-400",
  },
  POLICY_DECIDED: {
    label: "Policy Decision Issued",
    icon: <CheckCircle2 className="w-3 h-3" />,
    color: "text-emerald-400",
  },
  AUDIT_RECORDED: {
    label: "Audit Record Persisted",
    icon: <Terminal className="w-3 h-3" />,
    color: "text-slate-300",
  },
  INJECTION_COMPLETE: {
    label: "Injection Complete",
    icon: <CheckCircle2 className="w-3 h-3" />,
    color: "text-emerald-400",
  },
  ERROR: {
    label: "Error",
    icon: <XCircle className="w-3 h-3" />,
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
      className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold border ${map[severity] || map.LOW}`}
    >
      {severity}
    </span>
  );
}

// ─── Family Card ────────────────────────────────────────────────────────────

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
      className={`w-full text-left p-3.5 rounded-xl border transition-all duration-150 ${
        selected
          ? "bg-teal-500/10 border-teal-500/50 ring-1 ring-teal-500/30"
          : "bg-slate-900/60 border-slate-700/60 hover:border-slate-500/60 hover:bg-slate-800/60"
      }`}
    >
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-xs font-semibold font-mono text-white">
          {family.family}
        </span>
        <SeverityBadge severity={family.severity} />
      </div>
      <p className="text-[11px] text-slate-400 leading-snug">
        {family.description}
      </p>
      <div className="mt-2 flex items-center gap-2">
        <span
          className={`text-[10px] px-1.5 py-0.5 rounded font-mono ${
            family.category === "ANOMALY"
              ? "bg-rose-900/30 text-rose-400"
              : "bg-emerald-900/30 text-emerald-400"
          }`}
        >
          {family.category}
        </span>
        {family.is_legitimate && (
          <span className="text-[10px] text-slate-500">
            ✓ Legitimate edge case
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
  }, [stages]);

  if (stages.length === 0) return null;

  return (
    <div className="mt-4 rounded-xl border border-slate-700/60 bg-slate-950/70 p-3 max-h-48 overflow-y-auto font-mono text-[11px] space-y-1.5">
      {stages.map((s, i) => {
        const meta = STAGE_META[s.stage] || {
          label: s.stage,
          icon: <ChevronRight className="w-3 h-3" />,
          color: "text-slate-400",
        };
        return (
          <div key={i} className={`flex items-start gap-2 ${meta.color}`}>
            <span className="mt-0.5 shrink-0">{meta.icon}</span>
            <div className="min-w-0">
              <span className="font-semibold">[{meta.label}]</span>{" "}
              <span className="text-slate-300">{s.message}</span>
              {s.exception_id && (
                <span className="ml-2 text-teal-400">→ {s.exception_id}</span>
              )}
            </div>
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
    <div className="mt-5 rounded-xl border border-teal-500/30 bg-teal-500/5 p-4 space-y-3">
      {/* Header */}
      <div className="flex flex-wrap items-center gap-2">
        <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
        <span className="text-sm font-bold text-white">
          Live Injection Complete
        </span>
        <span className="ml-auto inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[10px] font-bold bg-teal-500/20 border border-teal-400/40 text-teal-300 animate-pulse">
          <Radio className="w-2.5 h-2.5" /> LIVE-INJECTED
        </span>
      </div>

      {/* ID Grid */}
      <div className="grid grid-cols-2 gap-2 text-[11px] font-mono">
        <div className="p-2 rounded-lg bg-slate-900/70 border border-slate-800">
          <p className="text-slate-500 mb-0.5">Injection ID</p>
          <p className="text-teal-300 truncate">{result.injection_id}</p>
        </div>
        <div className="p-2 rounded-lg bg-slate-900/70 border border-slate-800">
          <p className="text-slate-500 mb-0.5">Exception ID</p>
          <p className="text-amber-300 truncate">
            {result.linked_exception_id ?? "—"}
          </p>
        </div>
        <div className="p-2 rounded-lg bg-slate-900/70 border border-slate-800">
          <p className="text-slate-500 mb-0.5">Family</p>
          <p className="text-white truncate">{result.exception_family}</p>
        </div>
        <div className="p-2 rounded-lg bg-slate-900/70 border border-slate-800">
          <p className="text-slate-500 mb-0.5">Exposure</p>
          <p className="text-rose-300">
            ₹{((exposure) / 100).toLocaleString("en-IN", { minimumFractionDigits: 2 })}
          </p>
        </div>
        <div className="p-2 rounded-lg bg-slate-900/70 border border-slate-800">
          <p className="text-slate-500 mb-0.5">State</p>
          <p className="text-slate-200">{result.exception_state ?? "—"}</p>
        </div>
        <div className="p-2 rounded-lg bg-slate-900/70 border border-slate-800">
          <p className="text-slate-500 mb-0.5">Source Flag</p>
          <p className="text-teal-400">{result.source_flag}</p>
        </div>
      </div>

      {/* Generated IDs */}
      <div className="text-[11px] font-mono">
        <p className="text-slate-500 mb-1">Generated Identifiers</p>
        <div className="flex flex-wrap gap-1">
          {Object.entries(result.generated_record_identifiers).flatMap(
            ([, ids]) =>
              (ids as string[]).map((id) => (
                <span
                  key={id}
                  className="px-1.5 py-0.5 rounded bg-slate-800/80 border border-slate-700 text-slate-300"
                >
                  {id}
                </span>
              ))
          )}
        </div>
      </div>

      {/* Open Exception Button */}
      {result.linked_exception_id && (
        <button
          id={`open-exception-${result.linked_exception_id}`}
          onClick={() => onOpenException(result.linked_exception_id!)}
          className="w-full flex items-center justify-center gap-2 py-2 rounded-lg bg-teal-600 hover:bg-teal-500 text-white text-xs font-semibold transition-all"
        >
          <ExternalLink className="w-3.5 h-3.5" />
          Open Exception in Verification Engine
        </button>
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
      <h4 className="text-sm font-semibold text-white mb-2 flex items-center gap-2">
        <Clock className="w-4 h-4 text-slate-400" />
        Injection History ({cases.length})
      </h4>
      <div className="overflow-x-auto rounded-xl border border-slate-800/70 bg-slate-900/50">
        <table className="w-full text-left text-[11px] font-mono">
          <thead>
            <tr className="border-b border-slate-800 text-slate-500 text-[10px] bg-slate-950/40">
              <th className="py-2 px-3">INJECTION ID</th>
              <th className="py-2 px-3">FAMILY</th>
              <th className="py-2 px-3">EXCEPTION ID</th>
              <th className="py-2 px-3">STATUS</th>
              <th className="py-2 px-3">TRIGGERED AT</th>
              <th className="py-2 px-3">FLAG</th>
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
                <td className="py-2 px-3 text-teal-400">{c.injection_id}</td>
                <td className="py-2 px-3 text-white">{c.exception_family}</td>
                <td className="py-2 px-3 text-amber-300">
                  {c.linked_exception_id ?? "—"}
                </td>
                <td className="py-2 px-3">
                  <span
                    className={`${
                      c.status === "COMPLETED"
                        ? "text-emerald-400"
                        : "text-amber-400"
                    }`}
                  >
                    {c.status}
                  </span>
                </td>
                <td className="py-2 px-3 text-slate-400">
                  {new Date(c.triggered_at).toLocaleTimeString()}
                </td>
                <td className="py-2 px-3">
                  <span className="px-1.5 py-0.5 rounded bg-teal-900/30 border border-teal-500/30 text-teal-400">
                    {c.source_flag}
                  </span>
                </td>
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
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [stages, setStages] = useState<InjectionStageEvent[]>([]);
  const [result, setResult] = useState<InjectionResponse | null>(null);
  const [history, setHistory] = useState<InjectedCaseSummary[]>([]);
  const [streamMode, setStreamMode] = useState<boolean>(true);
  const [highlightedExceptionId, setHighlightedExceptionId] = useState<
    string | null
  >(null);
  const esRef = useRef<EventSource | null>(null);

  // Load supported families and history on mount
  useEffect(() => {
    fetchSupportedFamilies()
      .then((data) => {
        setFamilies(data);
        if (data.length > 0) setSelectedFamily(data[0].family);
      })
      .catch(() => {});
    loadHistory();
  }, []);

  const loadHistory = async () => {
    try {
      const data = await fetchInjectedCases(10);
      setHistory(data);
    } catch {}
  };

  const handleOpenException = (excId: string) => {
    setHighlightedExceptionId(excId);
    // Scroll to verification panel
    const el = document.getElementById("verification-panel-section");
    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const handleInjectSSE = useCallback(() => {
    if (!selectedFamily) return;
    setLoading(true);
    setError(null);
    setStages([]);
    setResult(null);

    const url = `${BACKEND_URL}/demo/inject/stream?family=${encodeURIComponent(selectedFamily)}&triggered_by=${encodeURIComponent(operatorId)}`;
    const es = new EventSource(url);
    esRef.current = es;

    es.onmessage = (evt) => {
      try {
        const data: InjectionStageEvent = JSON.parse(evt.data);
        setStages((prev) => [...prev, data]);
        if (data.stage === "INJECTION_COMPLETE" && data.data) {
          setResult(data.data);
          setLoading(false);
          es.close();
          loadHistory();
        }
        if (data.stage === "ERROR") {
          setError(data.message);
          setLoading(false);
          es.close();
        }
      } catch {}
    };

    es.onerror = () => {
      setError("Connection error during streaming. Check backend status.");
      setLoading(false);
      es.close();
    };
  }, [selectedFamily, operatorId]);

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
  }, [selectedFamily, operatorId]);

  const handleInject = streamMode ? handleInjectSSE : handleInjectSync;

  return (
    <section className="py-8" id="live-injection-console">
      <div className="glass-panel rounded-2xl p-6 sm:p-8 border border-slate-800 relative overflow-hidden">
        {/* Glow effect */}
        <div className="absolute top-0 left-0 -ml-20 -mt-20 w-72 h-72 bg-teal-500/8 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute bottom-0 right-0 -mr-20 -mb-20 w-64 h-64 bg-violet-500/6 rounded-full blur-3xl pointer-events-none" />

        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-5 border-b border-slate-800/70">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <div className="p-1.5 rounded-lg bg-teal-500/10 border border-teal-500/20">
                <Zap className="w-5 h-5 text-teal-400" />
              </div>
              <h3 className="text-xl font-bold text-white tracking-tight">
                Live Digital Twin
              </h3>
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-teal-500/15 border border-teal-500/30 text-teal-300">
                <Radio className="w-2.5 h-2.5" /> v2.0
              </span>
            </div>
            <p className="text-xs text-slate-400 max-w-xl">
              Inject a fresh synthetic anomaly at runtime. The case enters the{" "}
              <strong className="text-slate-300">exact same pipeline</strong> as
              seeded data — deterministic controls → detection → AI investigation
              → risk → policy → audit. No shortcuts, no mock exceptions.
            </p>
          </div>

          {/* Mode toggle */}
          <div className="flex items-center gap-2 text-[11px] font-mono shrink-0">
            <span className="text-slate-500">Mode:</span>
            <button
              onClick={() => setStreamMode(true)}
              className={`px-2.5 py-1 rounded border transition ${
                streamMode
                  ? "bg-teal-500/20 border-teal-500/40 text-teal-300"
                  : "bg-slate-800 border-slate-700 text-slate-400 hover:text-slate-200"
              }`}
            >
              SSE Stream
            </button>
            <button
              onClick={() => setStreamMode(false)}
              className={`px-2.5 py-1 rounded border transition ${
                !streamMode
                  ? "bg-violet-500/20 border-violet-500/40 text-violet-300"
                  : "bg-slate-800 border-slate-700 text-slate-400 hover:text-slate-200"
              }`}
            >
              Synchronous
            </button>
          </div>
        </div>

        {/* Safety Notice */}
        <div className="mt-4 flex items-start gap-2.5 p-3 rounded-xl bg-amber-500/5 border border-amber-500/20 text-[11px] text-amber-300/80">
          <BadgeAlert className="w-4 h-4 shrink-0 mt-0.5 text-amber-400" />
          <span>
            This creates a <strong>brand-new synthetic case</strong> with
            runtime-generated identifiers (prefixed <code>INJ…</code>). It is
            tagged <code>source_flag=live-injected</code> and{" "}
            <strong>never</strong> enters the benchmark ground truth or affects
            scoring.
          </span>
        </div>

        {/* Family Selector */}
        <div className="mt-6">
          <h4 className="text-xs font-semibold text-slate-300 mb-3 uppercase tracking-wider">
            Anomaly Family
          </h4>
          {families.length === 0 ? (
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
        <div className="mt-5 flex flex-col sm:flex-row items-center gap-3">
          <div className="relative flex-1 w-full">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 text-[11px] font-mono">
              Operator:
            </span>
            <input
              id="operator-id-input"
              type="text"
              value={operatorId}
              onChange={(e) => setOperatorId(e.target.value)}
              placeholder="demo-operator"
              className="w-full bg-slate-900/90 border border-slate-700/80 rounded-lg pl-20 pr-3 py-2 text-xs font-mono text-white placeholder-slate-500 focus:outline-none focus:border-teal-500"
            />
          </div>

          <button
            id="inject-anomaly-btn"
            onClick={handleInject}
            disabled={loading || !selectedFamily}
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-2.5 rounded-xl bg-gradient-to-r from-teal-600 to-cyan-600 hover:from-teal-500 hover:to-cyan-500 text-white font-semibold text-sm shadow-lg shadow-teal-900/30 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" />
                Injecting…
              </>
            ) : (
              <>
                <Zap className="w-4 h-4" />
                Inject Live Anomaly
              </>
            )}
          </button>
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
              → Enter this ID in the Verification Engine below to inspect the
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

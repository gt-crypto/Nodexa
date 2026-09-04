"use client";

import React, { useState, useEffect } from "react";
import {
  Send,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Clock,
  ShieldCheck,
  RefreshCcw,
  ExternalLink,
  Lock,
  Play,
  Radio,
  Bell,
} from "lucide-react";
import { EscalationConfigData, EscalationDeliveryItem } from "../lib/api";
import { fetchEscalationConfig, fetchEscalationDeliveries, triggerEscalationWebhook } from "../lib/api";
import { executeWithColdStartRetry } from "../lib/resilience";
import { ColdStartWakingCard } from "./ColdStartWakingCard";
import { Button } from "./ui/Button";
import { SectionHeading } from "./ui/SectionHeading";

export function EscalationWebhookPanel() {
  const [config, setConfig] = useState<EscalationConfigData | null>(null);
  const [deliveries, setDeliveries] = useState<EscalationDeliveryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [wakingState, setWakingState] = useState<{ attempt: number; isTimeout: boolean } | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Manual Trigger State
  const [testExceptionId, setTestExceptionId] = useState("");
  const [triggering, setTriggering] = useState(false);
  const [triggerResult, setTriggerResult] = useState<any | null>(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    setWakingState(null);
    try {
      const [cfg, dels] = await executeWithColdStartRetry(
        () => Promise.all([
          fetchEscalationConfig(),
          fetchEscalationDeliveries(20),
        ]),
        {
          onWaking: (attempt) => setWakingState({ attempt, isTimeout: false }),
          onRecovered: () => setWakingState(null),
        }
      );
      setConfig(cfg);
      setDeliveries(Array.isArray(dels) ? dels : (dels as any)?.deliveries || []);
      setWakingState(null);
    } catch (err: any) {
      if (wakingState && wakingState.attempt >= 6) {
        setWakingState({ attempt: 6, isTimeout: true });
      } else {
        setError(err.message || "Failed to load escalation webhook status.");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleManualTrigger = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!testExceptionId.trim()) return;

    setTriggering(true);
    setTriggerResult(null);
    try {
      const res = await triggerEscalationWebhook(testExceptionId.trim(), false);
      setTriggerResult(res);
      await loadData();
    } catch (err: any) {
      setTriggerResult({
        success: false,
        status: "ERROR",
        message: err.message || "Dispatch request failed",
      });
    } finally {
      setTriggering(false);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "DELIVERED":
        return "bg-emerald-500/15 border-emerald-500/40 text-emerald-300";
      case "FAILED":
        return "bg-rose-500/15 border-rose-500/40 text-rose-300";
      case "DISABLED":
        return "bg-slate-800 border-slate-700 text-slate-400";
      case "PENDING":
      default:
        return "bg-amber-500/15 border-amber-500/40 text-amber-300";
    }
  };

  const deliveredCount = deliveries.filter((d) => d.delivery_status === "DELIVERED").length;
  const failedCount = deliveries.filter((d) => d.delivery_status === "FAILED").length;
  const disabledCount = deliveries.filter((d) => d.delivery_status === "DISABLED").length;

  return (
    <section id="escalations" className="w-full">
      <div className="glass-panel rounded-xl p-5 sm:p-6 border border-slate-800/80 shadow-2xl relative overflow-hidden">
        {/* Subtle Brand Accent Line */}
        <div className="absolute top-0 left-0 right-0 h-0.5 bg-gradient-to-r from-sky-500/80 via-cyan-400/60 to-transparent" />

        {/* Section Header */}
        <SectionHeading
          icon={<Send className="w-5 h-5 text-sky-400" />}
          title="Escalation Webhook Dispatcher"
          badge={{
            text: "Tier-3 Incident Delivery (v2.0 HMAC Signed)",
            icon: <Bell className="w-3.5 h-3.5 text-sky-400" />,
            color: "bg-sky-500/10 border-sky-500/30 text-sky-300",
          }}
          description="Outbound notification service dispatching signed incident payloads to downstream operations centers when high-consequence exceptions require escalation."
          action={
            <Button
              variant="icon"
              onClick={loadData}
              disabled={loading}
              title="Refresh webhook status"
              aria-label="Refresh webhook status"
              icon={<RefreshCcw className={`w-3.5 h-3.5 ${loading ? "animate-spin text-sky-400" : ""}`} />}
            />
          }
        />

        {/* Panel Body */}
        <div className="space-y-5 mt-4">
          {wakingState ? (
            <ColdStartWakingCard
              attempt={wakingState.attempt}
              maxAttempts={6}
              isTimeout={wakingState.isTimeout}
              onRetry={loadData}
              description="Connecting to Escalation Webhook Dispatcher…"
              compact
            />
          ) : error ? (
            <div className="p-3.5 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-3">
              <AlertTriangle className="w-4 h-4 shrink-0 text-rose-400" />
              <span>{error}</span>
            </div>
          ) : null}

          {/* Configuration & Status Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3.5">
            {/* Dispatcher State */}
            <div className="p-4 rounded-lg bg-slate-950/70 border border-slate-800/80 flex flex-col justify-between">
              <div>
                <div className="text-[10px] font-mono uppercase tracking-wider text-slate-400 font-medium">
                  Dispatcher State
                </div>
                <div className="mt-2 flex items-center gap-2">
                  <span
                    className={`inline-block px-2.5 py-0.5 rounded text-xs font-mono font-bold border ${
                      config?.enabled
                        ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-300"
                        : "bg-slate-900 border-slate-700 text-slate-400"
                    }`}
                  >
                    {config?.enabled ? "ACTIVE (ENABLED)" : "DISABLED"}
                  </span>
                </div>
              </div>

              <div className="text-[11px] font-mono text-slate-400 mt-4 pt-3 border-t border-slate-800/80 space-y-1">
                <div className="truncate">Destination: <strong className="text-slate-200">{config?.destination_url || "NOT CONFIGURED"}</strong></div>
                <div>Auth: <strong className="text-slate-200">{config?.authentication_method || "NONE"}</strong></div>
              </div>
            </div>

            {/* Delivery Stats */}
            <div className="p-4 rounded-lg bg-slate-950/70 border border-slate-800/80 flex flex-col justify-between">
              <div>
                <div className="text-[10px] font-mono uppercase tracking-wider text-slate-400 font-medium">
                  Deliveries Logged
                </div>
                <div className="flex items-baseline gap-2 mt-1.5">
                  <span className="text-2xl sm:text-3xl font-bold text-white font-mono num-tabular">
                    {deliveries.length}
                  </span>
                  <span className="text-slate-400 font-mono text-xs">recent</span>
                </div>
              </div>

              <div className="text-[11px] font-mono text-slate-400 mt-4 pt-3 border-t border-slate-800/80 flex flex-wrap gap-x-3.5 gap-y-1">
                <span className="text-emerald-400 font-semibold num-tabular">{deliveredCount} delivered</span>
                <span className="text-rose-400 font-semibold num-tabular">{failedCount} failed</span>
                <span className="text-slate-400 num-tabular">{disabledCount} disabled</span>
              </div>
            </div>

            {/* Invariant Guarantee Box */}
            <div className="p-4 rounded-lg bg-sky-950/20 border border-sky-500/20 flex flex-col justify-between">
              <div>
                <div className="text-[10px] font-mono uppercase tracking-wider text-sky-400 font-semibold flex items-center gap-1.5">
                  <ShieldCheck className="w-3.5 h-3.5 text-sky-400" />
                  <span>Mandatory Safety Invariant</span>
                </div>
                <div className="text-xs font-bold text-white mt-1.5 font-mono">
                  WEBHOOK FAILURE != POLICY FAILURE
                </div>
              </div>

              <div className="text-[11px] text-slate-300 mt-3 pt-2.5 border-t border-sky-500/20 leading-relaxed">
                Restrictive policies remain fully enforced even if downstream delivery fails.
              </div>
            </div>
          </div>

          {/* Manual Operator Webhook Trigger Tool */}
          <div className="p-4 rounded-lg bg-slate-950/60 border border-slate-800/80 space-y-3">
            <h3 className="text-xs font-bold font-mono text-slate-300 uppercase tracking-wider flex items-center gap-2">
              <Play className="w-3.5 h-3.5 text-sky-400" />
              <span>Manual Escalation Dispatch Tester (Operator Tool)</span>
            </h3>
            <form onSubmit={handleManualTrigger} className="flex flex-col sm:flex-row gap-2.5">
              <input
                type="text"
                placeholder="Enter exception ID (e.g. EXC-GHOST_SETTLEMENT-PAY-...)"
                value={testExceptionId}
                onChange={(e) => setTestExceptionId(e.target.value)}
                className="flex-1 px-3.5 py-2 rounded-lg border border-slate-800 bg-[#070b13] text-slate-200 text-xs font-mono focus:outline-none focus:border-sky-500/60 transition"
              />
              <Button
                type="submit"
                disabled={triggering || !testExceptionId.trim()}
                variant="primary"
                loading={triggering}
                icon={<Send className="w-3.5 h-3.5" />}
                className="shrink-0"
              >
                {triggering ? "Dispatching…" : "Dispatch escalation"}
              </Button>
            </form>

            {triggerResult && (
              <div
                className={`p-3 rounded-lg border text-xs font-mono space-y-1 ${
                  triggerResult.success
                    ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-300"
                    : "bg-slate-900 border-slate-800 text-slate-300"
                }`}
              >
                <div className="font-bold">Result: {triggerResult.status}</div>
                <div>{triggerResult.message}</div>
                {triggerResult.event_id && (
                  <div className="text-slate-400 text-xs">Event ID: {triggerResult.event_id}</div>
                )}
              </div>
            )}
          </div>

          {/* Recent Deliveries Table */}
          <div className="rounded-lg bg-slate-950/60 border border-slate-800/80 overflow-hidden">
            <div className="p-3.5 sm:p-4 border-b border-slate-800/80 flex items-center justify-between">
              <h3 className="text-xs font-semibold text-slate-200 uppercase tracking-wider font-mono flex items-center gap-2">
                <Radio className="w-3.5 h-3.5 text-sky-400" />
                <span>Recent Escalation Dispatch Audit Trail</span>
              </h3>
              <span className="text-[11px] text-slate-400 font-mono">Immutable delivery state</span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-[#070b13] text-slate-400 uppercase text-[11px] font-sans font-semibold tracking-wider border-b border-slate-800/80">
                  <tr>
                    <th className="py-2.5 px-3.5">Event ID</th>
                    <th className="py-2.5 px-3.5">Exception ID</th>
                    <th className="py-2.5 px-3.5">Status</th>
                    <th className="py-2.5 px-3.5 text-right">Attempts</th>
                    <th className="py-2.5 px-3.5">Flag</th>
                    <th className="py-2.5 px-3.5 text-right">Timestamp</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-sans">
                  {deliveries.length > 0 ? (
                    deliveries.map((del) => (
                      <tr key={del.delivery_id} className="hover:bg-slate-900/40 transition">
                        <td className="py-2.5 px-3.5 text-sky-300 font-semibold font-mono text-xs">{del.event_id}</td>
                        <td className="py-2.5 px-3.5 text-slate-300 font-mono text-xs">{del.exception_id}</td>
                        <td className="py-2.5 px-3.5">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold font-mono border ${getStatusBadge(
                              del.delivery_status
                            )}`}
                          >
                            {del.delivery_status}
                          </span>
                        </td>
                        <td className="py-2.5 px-3.5 text-slate-300 text-right num-tabular">{del.attempt_count}</td>
                        <td className="py-2.5 px-3.5">
                          <span className="text-cyan-400 font-mono text-xs">{del.source_flag}</span>
                        </td>
                        <td className="py-2.5 px-3.5 text-slate-400 text-right num-tabular">
                          {new Date(del.created_at).toLocaleTimeString()}
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={6} className="py-8 text-center text-slate-400 italic font-sans">
                        No escalation webhooks dispatched yet.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

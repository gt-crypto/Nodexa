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
        return "bg-emerald-50 border-emerald-200 text-emerald-700";
      case "FAILED":
        return "bg-rose-50 border-rose-200 text-rose-700";
      case "DISABLED":
        return "bg-slate-100 border-slate-200 text-slate-600";
      case "PENDING":
      default:
        return "bg-amber-50 border-amber-200 text-amber-700";
    }
  };

  const deliveredCount = deliveries.filter((d) => d.delivery_status === "DELIVERED").length;
  const failedCount = deliveries.filter((d) => d.delivery_status === "FAILED").length;
  const disabledCount = deliveries.filter((d) => d.delivery_status === "DISABLED").length;

  return (
    <section id="escalations" className="w-full">
      <div className="rounded-xl p-5 sm:p-6 border border-slate-200 bg-white shadow-xs relative overflow-hidden">
        {/* Subtle Brand Accent Line */}
        <div className="absolute top-0 left-0 right-0 h-0.5 bg-gradient-to-r from-indigo-500/80 via-cyan-400/60 to-transparent" />

        {/* Section Header */}
        <SectionHeading
          icon={<Send className="w-5 h-5 text-indigo-600" />}
          title="Escalation Webhook Dispatcher"
          badge={{
            text: "Tier-3 Incident Delivery (HMAC Signed)",
            icon: <Bell className="w-3.5 h-3.5 text-indigo-600" />,
            color: "bg-indigo-50 border-indigo-200 text-indigo-700",
          }}
          description="Outbound notification service dispatching signed incident payloads to downstream operations centers when high-consequence exceptions require escalation."
          action={
            <Button
              variant="icon"
              onClick={loadData}
              disabled={loading}
              title="Refresh webhook status"
              aria-label="Refresh webhook status"
              icon={<RefreshCcw className={`w-3.5 h-3.5 ${loading ? "animate-spin text-indigo-600" : ""}`} />}
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
            <div className="p-3.5 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center gap-3">
              <AlertTriangle className="w-4 h-4 shrink-0 text-rose-600" />
              <span>{error}</span>
            </div>
          ) : null}

          {/* Configuration & Status Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3.5">
            {/* Dispatcher State */}
            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 flex flex-col justify-between shadow-2xs">
              <div>
                <div className="text-[10px] font-mono uppercase tracking-wider text-slate-500 font-bold">
                  Dispatcher State
                </div>
                <div className="mt-2 flex items-center gap-2">
                  <span
                    className={`inline-block px-2.5 py-0.5 rounded text-xs font-mono font-bold border ${
                      config?.enabled
                        ? "bg-emerald-50 border-emerald-200 text-emerald-700"
                        : "bg-slate-100 border-slate-200 text-slate-600"
                    }`}
                  >
                    {config?.enabled ? "ACTIVE (ENABLED)" : "DISABLED"}
                  </span>
                </div>
              </div>

              <div className="text-[11px] font-mono text-slate-600 mt-4 pt-3 border-t border-slate-200 space-y-1">
                <div className="truncate">Destination: <strong className="text-slate-900">{config?.destination_url || "NOT CONFIGURED"}</strong></div>
                <div>Auth: <strong className="text-slate-900">{config?.authentication_method || "NONE"}</strong></div>
              </div>
            </div>

            {/* Delivery Stats */}
            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 flex flex-col justify-between shadow-2xs">
              <div>
                <div className="text-[10px] font-mono uppercase tracking-wider text-slate-500 font-bold">
                  Deliveries Logged
                </div>
                <div className="flex items-baseline gap-2 mt-1.5">
                  <span className="text-2xl sm:text-3xl font-bold text-slate-900 font-mono num-tabular">
                    {deliveries.length}
                  </span>
                  <span className="text-slate-400 font-mono text-xs">recent</span>
                </div>
              </div>

              <div className="text-[11px] font-mono text-slate-600 mt-4 pt-3 border-t border-slate-200 flex flex-wrap gap-x-3.5 gap-y-1">
                <span className="text-emerald-700 font-bold num-tabular">{deliveredCount} delivered</span>
                <span className="text-rose-600 font-bold num-tabular">{failedCount} failed</span>
                <span className="text-slate-500 num-tabular">{disabledCount} disabled</span>
              </div>
            </div>

            {/* Invariant Guarantee Box */}
            <div className="p-4 rounded-xl bg-indigo-50/60 border border-indigo-200 flex flex-col justify-between shadow-2xs">
              <div>
                <div className="text-[10px] font-mono uppercase tracking-wider text-indigo-700 font-bold flex items-center gap-1.5">
                  <ShieldCheck className="w-3.5 h-3.5 text-indigo-600" />
                  <span>Mandatory Safety Invariant</span>
                </div>
                <div className="text-xs font-bold text-slate-900 mt-1.5 font-mono">
                  WEBHOOK FAILURE != POLICY FAILURE
                </div>
              </div>

              <div className="text-[11px] text-slate-600 mt-3 pt-2.5 border-t border-indigo-200 leading-relaxed">
                Restrictive policies remain fully enforced even if downstream delivery fails.
              </div>
            </div>
          </div>

          {/* Manual Operator Webhook Trigger Tool */}
          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-3 shadow-2xs">
            <h3 className="text-xs font-bold font-mono text-slate-900 uppercase tracking-wider flex items-center gap-2">
              <Play className="w-3.5 h-3.5 text-indigo-600" />
              <span>Manual Escalation Dispatch Tester (Operator Tool)</span>
            </h3>
            <form onSubmit={handleManualTrigger} className="flex flex-col sm:flex-row gap-2.5">
              <input
                type="text"
                placeholder="Enter exception ID (e.g. EXC-GHOST_SETTLEMENT-PAY-...)"
                value={testExceptionId}
                onChange={(e) => setTestExceptionId(e.target.value)}
                className="flex-1 px-3.5 py-2 rounded-lg border border-slate-300 bg-white text-slate-900 text-xs font-mono focus:outline-none focus:border-indigo-500 shadow-2xs transition"
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
                    ? "bg-emerald-50 border-emerald-200 text-emerald-800"
                    : "bg-white border-slate-200 text-slate-800 shadow-2xs"
                }`}
              >
                <div className="font-bold">Result: {triggerResult.status}</div>
                <div>{triggerResult.message}</div>
                {triggerResult.event_id && (
                  <div className="text-slate-500 text-xs">Event ID: {triggerResult.event_id}</div>
                )}
              </div>
            )}
          </div>

          {/* Recent Deliveries Table */}
          <div className="rounded-xl bg-white border border-slate-200 overflow-hidden shadow-2xs">
            <div className="p-3.5 sm:p-4 border-b border-slate-100 flex items-center justify-between">
              <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider font-mono flex items-center gap-2">
                <Radio className="w-3.5 h-3.5 text-indigo-600" />
                <span>Recent Escalation Dispatch Audit Trail</span>
              </h3>
              <span className="text-[11px] text-slate-500 font-mono">Immutable delivery state</span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 text-slate-600 uppercase text-[11px] font-sans font-semibold tracking-wider border-b border-slate-200">
                  <tr>
                    <th className="py-2.5 px-3.5">Event ID</th>
                    <th className="py-2.5 px-3.5">Exception ID</th>
                    <th className="py-2.5 px-3.5">Status</th>
                    <th className="py-2.5 px-3.5 text-right">Attempts</th>
                    <th className="py-2.5 px-3.5">Flag</th>
                    <th className="py-2.5 px-3.5 text-right">Timestamp</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 font-sans">
                  {deliveries.length > 0 ? (
                    deliveries.map((del) => (
                      <tr key={del.delivery_id} className="hover:bg-slate-50 transition">
                        <td className="py-2.5 px-3.5 text-indigo-600 font-semibold font-mono text-xs">{del.event_id}</td>
                        <td className="py-2.5 px-3.5 text-slate-800 font-mono text-xs">{del.exception_id}</td>
                        <td className="py-2.5 px-3.5">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold font-mono border ${getStatusBadge(
                              del.delivery_status
                            )}`}
                          >
                            {del.delivery_status}
                          </span>
                        </td>
                        <td className="py-2.5 px-3.5 text-slate-700 text-right num-tabular">{del.attempt_count}</td>
                        <td className="py-2.5 px-3.5">
                          <span className="text-indigo-600 font-mono text-xs">{del.source_flag}</span>
                        </td>
                        <td className="py-2.5 px-3.5 text-slate-500 text-right num-tabular">
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

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
import { Button } from "./ui/Button";
import { SectionHeading } from "./ui/SectionHeading";

export function EscalationWebhookPanel() {
  const [config, setConfig] = useState<EscalationConfigData | null>(null);
  const [deliveries, setDeliveries] = useState<EscalationDeliveryItem[]>([]);
  const [loading, setLoading] = useState(false);
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
    try {
      const [cfg, dels] = await Promise.all([
        fetchEscalationConfig(),
        fetchEscalationDeliveries(20),
      ]);
      setConfig(cfg);
      setDeliveries(Array.isArray(dels) ? dels : (dels as any)?.deliveries || []);
    } catch (err: any) {
      setError(err.message || "Failed to load escalation webhook status.");
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
      <div className="glass-panel rounded-2xl p-6 sm:p-8 border border-slate-800/90 shadow-2xl relative overflow-hidden">
        {/* Accent Bar */}
        <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-purple-500 via-indigo-500 to-cyan-400" />

        {/* Section Header (Issue 3 & 14) */}
        <SectionHeading
          icon={<Send className="w-6 h-6 text-purple-400" />}
          title="Escalation Webhook Dispatcher"
          badge={{
            text: "Tier-3 Incident Delivery (v2.0 HMAC Signed)",
            icon: <Bell className="w-3.5 h-3.5 text-purple-400" />,
            color: "bg-purple-500/10 border-purple-500/30 text-purple-300",
          }}
          description="Outbound notification service dispatching signed incident payloads to downstream operations centers when high-consequence exceptions require escalation."
          action={
            <Button
              variant="icon"
              onClick={loadData}
              disabled={loading}
              title="Refresh webhook status"
              aria-label="Refresh webhook status"
              icon={<RefreshCcw className={`w-4 h-4 ${loading ? "animate-spin text-purple-400" : ""}`} />}
            />
          }
        />

        {/* Panel Body */}
        <div className="space-y-6">
          {error && (
            <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-sm flex items-center gap-3">
              <AlertTriangle className="w-5 h-5 shrink-0 text-rose-400" />
              <span>{error}</span>
            </div>
          )}

          {/* Configuration & Status Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Dispatcher State */}
            <div className="p-6 rounded-2xl bg-gradient-to-br from-slate-900/90 to-slate-950 border border-slate-800 flex flex-col justify-between shadow-inner">
              <div>
                <div className="text-xs font-mono uppercase tracking-wider text-slate-400 mb-1 font-semibold">
                  Dispatcher state
                </div>
                <div className="mt-2 flex items-center gap-2">
                  <span
                    className={`inline-block px-3 py-1 rounded-full text-xs font-mono font-bold border ${
                      config?.enabled
                        ? "bg-emerald-500/15 border-emerald-500/40 text-emerald-300"
                        : "bg-slate-800 border-slate-700 text-slate-400"
                    }`}
                  >
                    {config?.enabled ? "ACTIVE (ENABLED)" : "DISABLED"}
                  </span>
                </div>
              </div>

              <div className="text-xs font-mono text-slate-400 mt-4 pt-3 border-t border-slate-800 space-y-1">
                <div>Destination: <strong className="text-slate-300">{config?.destination_url || "NOT CONFIGURED"}</strong></div>
                <div>Auth: <strong className="text-slate-300">{config?.authentication_method || "NONE"}</strong></div>
              </div>
            </div>

            {/* Delivery Stats */}
            <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 flex flex-col justify-between">
              <div>
                <div className="text-xs font-mono uppercase tracking-wider text-slate-400 mb-1 font-semibold">
                  Deliveries logged
                </div>
                <div className="flex items-baseline gap-2 mt-2">
                  <span className="text-3xl sm:text-4xl font-extrabold text-white font-mono">
                    {deliveries.length}
                  </span>
                  <span className="text-slate-500 font-mono text-xs">recent</span>
                </div>
              </div>

              <div className="text-xs font-mono text-slate-400 mt-4 pt-3 border-t border-slate-800 flex flex-wrap gap-x-4 gap-y-1">
                <span className="text-emerald-400 font-semibold">{deliveredCount} delivered</span>
                <span className="text-rose-400 font-semibold">{failedCount} failed</span>
                <span className="text-slate-500">{disabledCount} disabled</span>
              </div>
            </div>

            {/* Invariant Guarantee Box */}
            <div className="p-6 rounded-2xl bg-purple-500/10 border border-purple-500/30 flex flex-col justify-between">
              <div>
                <div className="text-xs font-mono uppercase tracking-wider text-purple-300 mb-1 font-semibold flex items-center gap-1.5">
                  <ShieldCheck className="w-4 h-4 text-purple-400" />
                  <span>Mandatory safety invariant</span>
                </div>
                <div className="text-sm font-bold text-white mt-2 font-mono">
                  WEBHOOK FAILURE != POLICY FAILURE
                </div>
              </div>

              <div className="text-xs text-slate-300 mt-4 pt-3 border-t border-purple-500/30 leading-relaxed">
                Restrictive policies remain fully enforced even if downstream delivery fails.
              </div>
            </div>
          </div>

          {/* Manual Operator Webhook Trigger Tool (Issue 15: H3) */}
          <div className="p-5 rounded-2xl bg-slate-900/50 border border-slate-800 space-y-3">
            <h3 className="text-xs font-bold font-mono text-slate-300 uppercase tracking-wider flex items-center gap-2">
              <Play className="w-4 h-4 text-purple-400" />
              <span>Manual escalation dispatch tester (operator tool)</span>
            </h3>
            <form onSubmit={handleManualTrigger} className="flex flex-col sm:flex-row gap-3">
              <input
                type="text"
                placeholder="Enter exception ID (e.g. EXC-GHOST_SETTLEMENT-PAY-...)"
                value={testExceptionId}
                onChange={(e) => setTestExceptionId(e.target.value)}
                className="flex-1 px-3.5 py-2.5 rounded-xl border border-slate-700 bg-slate-950 text-slate-200 text-xs font-mono focus:outline-none focus:border-purple-500"
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
                className={`p-3.5 rounded-xl border text-xs font-mono space-y-1 ${
                  triggerResult.success
                    ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-300"
                    : "bg-slate-800 border-slate-700 text-slate-300"
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

          {/* Recent Deliveries Table (Issue 15: H3) */}
          <div className="rounded-2xl bg-slate-900/40 border border-slate-800/80 overflow-hidden">
            <div className="p-4 sm:p-5 border-b border-slate-800 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-white uppercase tracking-wider font-mono flex items-center gap-2">
                <Radio className="w-4 h-4 text-purple-400" />
                <span>Recent escalation dispatch audit trail</span>
              </h3>
              <span className="text-xs text-slate-400 font-mono">Immutable delivery state</span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono">
                <thead className="bg-slate-950/60 text-slate-400 uppercase text-xs border-b border-slate-800">
                  <tr>
                    <th className="py-3 px-4">Event ID</th>
                    <th className="py-3 px-4">Exception ID</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4">Attempts</th>
                    <th className="py-3 px-4">Flag</th>
                    <th className="py-3 px-4">Timestamp</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {deliveries.length > 0 ? (
                    deliveries.map((del) => (
                      <tr key={del.delivery_id} className="hover:bg-slate-900/40 transition">
                        <td className="py-3 px-4 text-purple-300 font-bold">{del.event_id}</td>
                        <td className="py-3 px-4 text-slate-300">{del.exception_id}</td>
                        <td className="py-3 px-4">
                          <span
                            className={`px-2.5 py-0.5 rounded-full text-xs font-bold border ${getStatusBadge(
                              del.delivery_status
                            )}`}
                          >
                            {del.delivery_status}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-slate-300">{del.attempt_count}</td>
                        <td className="py-3 px-4">
                          <span className="text-cyan-400">{del.source_flag}</span>
                        </td>
                        <td className="py-3 px-4 text-slate-400">
                          {new Date(del.created_at).toLocaleTimeString()}
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={6} className="py-8 text-center text-slate-500 italic">
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

"use client";

import React, { useEffect, useState } from "react";
import { fetchHealthStatus } from "../lib/api";
import { executeWithColdStartRetry } from "../lib/resilience";
import { HealthCheckResponse } from "../types";
import { Server, CheckCircle2, AlertCircle, RefreshCw, Radio } from "lucide-react";
import { Button } from "./ui/Button";

export const SystemStatus: React.FC = () => {
  const [health, setHealth] = useState<HealthCheckResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [wakingAttempt, setWakingAttempt] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastChecked, setLastChecked] = useState<Date | null>(null);

  const checkHealth = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await executeWithColdStartRetry(
        () => fetchHealthStatus(),
        {
          onWaking: (attempt) => {
            setWakingAttempt(attempt);
          },
          onRecovered: () => {
            setWakingAttempt(null);
          },
        }
      );
      setHealth(data);
      setWakingAttempt(null);
      setLastChecked(new Date());
    } catch (err) {
      setWakingAttempt(null);
      setError(err instanceof Error ? err.message : "Backend unavailable (run uvicorn)");
      setHealth(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    checkHealth();
  }, []);

  return (
    <section id="overview" className="w-full">
      <div className="rounded-xl p-5 sm:p-6 border border-slate-200 bg-white shadow-xs relative overflow-hidden">
        {/* Main Card Header */}
        <header className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-100 mb-5">
          <div className="flex items-center gap-3.5 min-w-0">
            <div className="p-2.5 rounded-lg bg-indigo-50 border border-indigo-100 text-indigo-600 shrink-0">
              <Server className="w-4 h-4" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-3 flex-wrap">
                <h2 className="text-base font-bold text-slate-900 tracking-tight font-sans">
                  Controller Engine Status
                </h2>
                <span className="hidden sm:inline-block text-xs font-mono px-2.5 py-0.5 rounded bg-indigo-50 text-indigo-700 border border-indigo-200">
                  HEALTH ENGINE
                </span>
              </div>
              <p className="text-xs text-slate-500 mt-0.5">
                Live operational health probe: <code className="font-mono text-slate-700">GET /health</code>
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0 self-start sm:self-center">
            <Button
              onClick={checkHealth}
              disabled={loading}
              variant="secondary"
              size="sm"
              title="Refresh controller engine status"
              aria-label="Refresh controller engine status"
              icon={<RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin text-indigo-600" : ""}`} />}
            >
              {loading ? "Checking..." : "Refresh"}
            </Button>
          </div>
        </header>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
          <div className="p-3.5 rounded-lg bg-slate-50 border border-slate-200/70 flex flex-col justify-between min-h-[72px]">
            <span className="text-slate-500 text-xs font-medium block">Service Health</span>
            <div className="flex items-center gap-2 mt-1.5">
              {health?.status === "healthy" ? (
                <>
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                  <span className="text-emerald-700 font-semibold font-sans">Operational (200 OK)</span>
                </>
              ) : wakingAttempt ? (
                <>
                  <Radio className="w-3.5 h-3.5 text-indigo-600 animate-ping shrink-0" />
                  <span className="text-indigo-700 font-semibold font-sans truncate">
                    Waking Controller ({wakingAttempt}/6)...
                  </span>
                </>
              ) : error ? (
                <>
                  <AlertCircle className="w-3.5 h-3.5 text-amber-600 shrink-0" />
                  <span className="text-amber-700 font-semibold font-sans">Backend Offline</span>
                </>
              ) : (
                <>
                  <Radio className="w-3.5 h-3.5 text-indigo-600 animate-pulse shrink-0" />
                  <span className="text-slate-500 font-sans">Connecting...</span>
                </>
              )}
            </div>
          </div>

          <div className="p-3.5 rounded-lg bg-slate-50 border border-slate-200/70 flex flex-col justify-between min-h-[72px]">
            <span className="text-slate-500 text-xs font-medium block">Service Identifier</span>
            <span className="text-slate-900 font-mono text-xs truncate block mt-1.5 font-medium">
              {health?.service ?? "nodal-sentinel-backend"}
            </span>
          </div>

          <div className="p-3.5 rounded-lg bg-slate-50 border border-slate-200/70 flex flex-col justify-between min-h-[72px]">
            <span className="text-slate-500 text-xs font-medium block">Last Heartbeat</span>
            <span className="text-slate-900 font-mono text-xs block mt-1.5 font-medium">
              {lastChecked ? lastChecked.toLocaleTimeString() : "Pending check"}
            </span>
          </div>
        </div>

        {error && (
          <div className="mt-4 p-2.5 rounded-lg bg-amber-50 border border-amber-200 text-xs text-amber-800 font-mono flex items-center justify-between">
            <span>Note: Start FastAPI backend with <code className="text-amber-900 font-semibold">uvicorn backend.main:app --reload</code> to connect live.</span>
          </div>
        )}
      </div>
    </section>
  );
};

"use client";

import React, { useEffect, useState } from "react";
import { fetchHealthStatus } from "../lib/api";
import { executeWithColdStartRetry, isLikelyWakingError } from "../lib/resilience";
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
      <div className="rounded-xl p-5 sm:p-6 border border-slate-800/80 bg-[#0d121d] shadow-sm relative overflow-hidden">
        {/* Main Card Header */}
        <header className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-800/80 mb-5">
          <div className="flex items-start sm:items-center gap-3 min-w-0">
            <div className="p-2 rounded-lg bg-[#111726] border border-slate-800 text-sky-400 shrink-0">
              <Server className="w-4 h-4" />
            </div>
            <div className="min-w-0">
              <h2 className="text-base font-semibold text-white tracking-tight font-sans">
                Controller Engine Status
              </h2>
              <p className="text-xs text-slate-400 mt-0.5">
                Live operational health probe: <code className="font-mono text-slate-300">GET /health</code>
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0 self-start sm:self-center">
            <Button
              onClick={checkHealth}
              disabled={loading}
              variant="secondary"
              size="sm"
              aria-label="Refresh controller engine status"
              icon={<RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin text-sky-400" : ""}`} />}
            >
              {loading ? "Checking..." : "Refresh"}
            </Button>
          </div>
        </header>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
          <div className="p-3 rounded-lg bg-[#090d16] border border-slate-800/80">
            <span className="text-slate-400 text-[11px] font-medium block mb-1">Service Health</span>
            <div className="flex items-center gap-2">
              {health?.status === "healthy" ? (
                <>
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                  <span className="text-emerald-400 font-semibold font-sans">Operational (200 OK)</span>
                </>
              ) : wakingAttempt ? (
                <>
                  <Radio className="w-3.5 h-3.5 text-sky-400 animate-ping" />
                  <span className="text-sky-300 font-semibold font-sans">
                    Waking Controller (retry {wakingAttempt}/6)...
                  </span>
                </>
              ) : error ? (
                <>
                  <AlertCircle className="w-3.5 h-3.5 text-amber-400" />
                  <span className="text-amber-400 font-semibold font-sans">Backend Offline</span>
                </>
              ) : (
                <>
                  <Radio className="w-3.5 h-3.5 text-sky-400 animate-pulse" />
                  <span className="text-slate-400 font-sans">Connecting...</span>
                </>
              )}
            </div>
          </div>

          <div className="p-3 rounded-lg bg-[#090d16] border border-slate-800/80">
            <span className="text-slate-400 text-[11px] font-medium block mb-1">Service Identifier</span>
            <span className="text-slate-200 font-mono text-[12px] truncate block">
              {health?.service ?? "nodal-sentinel-backend"}
            </span>
          </div>

          <div className="p-3 rounded-lg bg-[#090d16] border border-slate-800/80">
            <span className="text-slate-400 text-[11px] font-medium block mb-1">Last Heartbeat</span>
            <span className="text-slate-200 font-mono text-[12px] block">
              {lastChecked ? lastChecked.toLocaleTimeString() : "Pending check"}
            </span>
          </div>
        </div>

        {error && (
          <div className="mt-4 p-2.5 rounded-lg bg-amber-950/30 border border-amber-800/40 text-xs text-amber-300 font-mono flex items-center justify-between">
            <span>Note: Start FastAPI backend with <code className="text-amber-200">uvicorn backend.main:app --reload</code> to connect live.</span>
          </div>
        )}
      </div>
    </section>
  );
};

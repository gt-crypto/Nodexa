"use client";

import React, { useEffect, useState } from "react";
import { fetchHealthStatus } from "../lib/api";
import { HealthCheckResponse } from "../types";
import { Server, CheckCircle2, AlertCircle, RefreshCw, Radio } from "lucide-react";

export const SystemStatus: React.FC = () => {
  const [health, setHealth] = useState<HealthCheckResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [lastChecked, setLastChecked] = useState<Date | null>(null);

  const checkHealth = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchHealthStatus();
      setHealth(data);
      setLastChecked(new Date());
    } catch (err) {
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
    <div className="glass-panel rounded-2xl p-6 border border-slate-800/80 shadow-2xl relative overflow-hidden mb-12">
      <div className="absolute top-0 right-0 w-64 h-64 bg-teal-500/5 rounded-full blur-3xl pointer-events-none" />

      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-5 border-b border-slate-800/60">
        <div className="flex items-center space-x-3">
          <div className="p-2.5 rounded-xl bg-slate-800/80 border border-slate-700/60 text-teal-400">
            <Server className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-base font-semibold text-white flex items-center gap-2">
              FastAPI Controller Engine Status
            </h3>
            <p className="text-xs text-slate-400">
              Live monitoring of backend API endpoint: <code className="font-mono text-slate-300">GET /health</code>
            </p>
          </div>
        </div>

        <button
          onClick={checkHealth}
          disabled={loading}
          className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-800/80 hover:bg-slate-700/80 border border-slate-700 text-xs font-mono text-slate-200 transition-all cursor-pointer disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin text-teal-400" : ""}`} />
          <span>{loading ? "Checking..." : "Re-check"}</span>
        </button>
      </div>

      <div className="mt-5 grid grid-cols-1 sm:grid-cols-3 gap-4 font-mono text-xs">
        <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800/80">
          <span className="text-slate-500 text-[11px] block mb-1">SERVICE HEALTH</span>
          <div className="flex items-center gap-2">
            {health?.status === "healthy" ? (
              <>
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                <span className="text-emerald-400 font-semibold uppercase">Operational (200 OK)</span>
              </>
            ) : error ? (
              <>
                <AlertCircle className="w-4 h-4 text-amber-400" />
                <span className="text-amber-400 font-semibold">Backend Offline</span>
              </>
            ) : (
              <>
                <Radio className="w-4 h-4 text-teal-400 animate-pulse" />
                <span className="text-slate-400">Pinging...</span>
              </>
            )}
          </div>
        </div>

        <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800/80">
          <span className="text-slate-500 text-[11px] block mb-1">SERVICE IDENTIFIER</span>
          <span className="text-slate-300">
            {health?.service ?? "nodal-sentinel-backend"}
          </span>
        </div>

        <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800/80">
          <span className="text-slate-500 text-[11px] block mb-1">LAST HEARTBEAT</span>
          <span className="text-slate-300">
            {lastChecked ? lastChecked.toLocaleTimeString() : "Pending check"}
          </span>
        </div>
      </div>

      {error && (
        <div className="mt-4 p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 text-xs text-amber-300 font-mono flex items-center justify-between">
          <span>Note: Start FastAPI backend with <code className="text-amber-200">uvicorn backend.main:app --reload</code> to connect live.</span>
        </div>
      )}
    </div>
  );
};

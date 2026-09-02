"use client";

import React, { useState, useEffect } from "react";
import {
  Layers,
  Network,
  RefreshCw,
  Search,
  Filter,
  Building2,
  Clock,
  ShieldAlert,
  AlertTriangle,
  CheckCircle2,
  FileSearch,
  ChevronDown,
  ChevronUp,
  Tag,
  Zap,
} from "lucide-react";
import { ClustersResponse, ExceptionCluster } from "../types";
import { fetchClusters, refreshClusters } from "../lib/api";

export function PatternMinerPanel() {
  const [clustersData, setClustersData] = useState<ClustersResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [selectedType, setSelectedType] = useState<string>("ALL");
  const [selectedSource, setSelectedSource] = useState<string>("ALL");
  const [expandedClusterId, setExpandedClusterId] = useState<string | null>(null);

  useEffect(() => {
    loadClusters();
  }, [selectedType, selectedSource]);

  const loadClusters = async () => {
    setLoading(true);
    setError(null);
    try {
      const params: any = {};
      if (selectedType !== "ALL") params.pattern_type = selectedType;
      if (selectedSource !== "ALL") params.source = selectedSource;

      const res = await fetchClusters(params);
      setClustersData(res);
    } catch (err: any) {
      setError(err.message || "Failed to load pattern clusters.");
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    setError(null);
    try {
      const res = await refreshClusters();
      setClustersData(res);
    } catch (err: any) {
      setError(err.message || "Failed to refresh pattern miner.");
    } finally {
      setRefreshing(false);
    }
  };

  const formatRupees = (paise: number) => {
    const rupees = paise / 100.0;
    return `₹${rupees.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  };

  const getTypeIcon = (type: string) => {
    switch (type) {
      case "FAMILY_SIGNATURE":
        return <Layers className="w-4 h-4 text-cyan-400" />;
      case "MERCHANT_REPEATED_FAMILY":
        return <Building2 className="w-4 h-4 text-purple-400" />;
      case "CONTROL_FINDING_SIGNATURE":
        return <ShieldAlert className="w-4 h-4 text-amber-400" />;
      case "TIMING_SLA_SIGNATURE":
        return <Clock className="w-4 h-4 text-teal-400" />;
      default:
        return <Network className="w-4 h-4 text-slate-400" />;
    }
  };

  const getTypeBadgeStyle = (type: string) => {
    switch (type) {
      case "FAMILY_SIGNATURE":
        return "bg-cyan-500/10 border-cyan-500/30 text-cyan-300";
      case "MERCHANT_REPEATED_FAMILY":
        return "bg-purple-500/10 border-purple-500/30 text-purple-300";
      case "CONTROL_FINDING_SIGNATURE":
        return "bg-amber-500/10 border-amber-500/30 text-amber-300";
      case "TIMING_SLA_SIGNATURE":
        return "bg-teal-500/10 border-teal-500/30 text-teal-300";
      default:
        return "bg-slate-500/10 border-slate-500/30 text-slate-300";
    }
  };

  const clusters = clustersData?.clusters || [];

  return (
    <section className="glass-panel rounded-2xl p-6 sm:p-8 border border-slate-800/80 shadow-2xl relative overflow-hidden">
      {/* Ambient glow */}
      <div className="absolute -top-24 -right-24 w-72 h-72 bg-purple-500/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute -bottom-24 -left-24 w-72 h-72 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none" />

      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6 pb-6 border-b border-slate-800">
        <div>
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-purple-500/10 border border-purple-500/30 text-purple-300 text-xs font-mono mb-2">
            <Network className="w-3.5 h-3.5 text-purple-400" />
            Tier-2 Pattern Miner Active (v2.0)
          </div>
          <h2 className="text-2xl font-bold text-white flex items-center gap-2">
            Deterministic Exception Pattern Miner
          </h2>
          <p className="text-sm text-slate-400 mt-1 max-w-2xl">
            Uncovers recurring operational signatures, repeated merchant anomalies, and systemic SLA delays across seeded and live-injected cases with explainable evidence.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleRefresh}
            disabled={refreshing || loading}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-purple-600/20 hover:bg-purple-600/30 border border-purple-500/40 text-purple-300 text-xs font-mono transition-all duration-200 shadow-lg shadow-purple-500/10 disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? "animate-spin" : ""}`} />
            <span>{refreshing ? "Mining..." : "Recompute Patterns"}</span>
          </button>
        </div>
      </div>

      {/* Top Metrics Row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800">
          <span className="text-xs font-mono text-slate-400 block mb-1">Discovered Patterns</span>
          <span className="text-2xl font-extrabold text-white font-mono">
            {clustersData?.total_clusters ?? "—"}
          </span>
        </div>

        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800">
          <span className="text-xs font-mono text-slate-400 block mb-1">Clustered Exceptions</span>
          <span className="text-2xl font-extrabold text-cyan-300 font-mono">
            {clustersData?.total_clustered_exceptions ?? "—"}
          </span>
        </div>

        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800">
          <span className="text-xs font-mono text-slate-400 block mb-1">Total Clustered Exposure</span>
          <span className="text-2xl font-extrabold text-emerald-300 font-mono">
            {clustersData ? formatRupees(clustersData.total_clustered_exposure) : "—"}
          </span>
        </div>

        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800">
          <span className="text-xs font-mono text-slate-400 block mb-1">Min. Cluster Size</span>
          <span className="text-2xl font-extrabold text-amber-300 font-mono">
            ≥ {clustersData?.min_cluster_size ?? 2}
          </span>
        </div>
      </div>

      {/* Filters Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6 p-3 rounded-xl bg-slate-900/40 border border-slate-800/80">
        <div className="flex flex-wrap items-center gap-2 text-xs font-mono">
          <span className="text-slate-500 mr-1 flex items-center gap-1">
            <Filter className="w-3.5 h-3.5" /> Pattern Type:
          </span>
          {["ALL", "FAMILY_SIGNATURE", "MERCHANT_REPEATED_FAMILY", "CONTROL_FINDING_SIGNATURE", "TIMING_SLA_SIGNATURE"].map((t) => (
            <button
              key={t}
              onClick={() => setSelectedType(t)}
              className={`px-2.5 py-1 rounded-lg border transition-all ${
                selectedType === t
                  ? "bg-purple-500/20 border-purple-500/50 text-purple-300 font-semibold"
                  : "bg-slate-900/60 border-slate-800 text-slate-400 hover:text-slate-200"
              }`}
            >
              {t === "ALL" ? "All Types" : t.replace(/_/g, " ")}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2 text-xs font-mono">
          <span className="text-slate-500">Source:</span>
          {["ALL", "seeded", "live-injected"].map((s) => (
            <button
              key={s}
              onClick={() => setSelectedSource(s)}
              className={`px-2 py-0.5 rounded-lg border transition-all ${
                selectedSource === s
                  ? "bg-cyan-500/20 border-cyan-500/50 text-cyan-300 font-semibold"
                  : "bg-slate-900/60 border-slate-800 text-slate-400 hover:text-slate-200"
              }`}
            >
              {s === "ALL" ? "All" : s}
            </button>
          ))}
        </div>
      </div>

      {/* Error state */}
      {error && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-sm flex items-start gap-3 mb-6">
          <AlertTriangle className="w-5 h-5 shrink-0 text-rose-400 mt-0.5" />
          <div>
            <p className="font-semibold">Pattern Miner Error</p>
            <p className="text-xs text-rose-300/80 mt-0.5">{error}</p>
          </div>
        </div>
      )}

      {/* Clusters List */}
      {loading && !clustersData ? (
        <div className="py-12 text-center text-slate-500 font-mono text-sm">
          <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-purple-400" />
          Mining exception patterns...
        </div>
      ) : clusters.length > 0 ? (
        <div className="space-y-4">
          {clusters.map((cluster) => {
            const isExpanded = expandedClusterId === cluster.cluster_id;
            return (
              <div
                key={cluster.cluster_id}
                className="p-5 rounded-xl bg-slate-900/70 border border-slate-800 hover:border-slate-700/80 transition-all duration-200"
              >
                {/* Cluster Card Header */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-3">
                  <div className="flex items-start sm:items-center gap-2.5">
                    {getTypeIcon(cluster.pattern_type)}
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <h4 className="text-base font-bold text-white tracking-tight">
                          {cluster.pattern_label}
                        </h4>
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-mono border uppercase ${getTypeBadgeStyle(cluster.pattern_type)}`}>
                          {cluster.pattern_type.replace(/_/g, " ")}
                        </span>
                      </div>
                      <p className="text-xs text-slate-400 mt-0.5">
                        {cluster.description}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-3 shrink-0">
                    <div className="text-right">
                      <span className="text-xs font-mono text-emerald-300 font-bold block">
                        {formatRupees(cluster.total_exposure)}
                      </span>
                      <span className="text-[11px] font-mono text-slate-400">
                        {cluster.exception_count} cases
                      </span>
                    </div>

                    <button
                      onClick={() => setExpandedClusterId(isExpanded ? null : cluster.cluster_id)}
                      className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors"
                      title={isExpanded ? "Collapse cluster" : "Expand cluster details"}
                    >
                      {isExpanded ? (
                        <ChevronUp className="w-4 h-4" />
                      ) : (
                        <ChevronDown className="w-4 h-4" />
                      )}
                    </button>
                  </div>
                </div>

                {/* Sub-details summary pill row */}
                <div className="flex flex-wrap items-center gap-2 text-xs font-mono pt-2 border-t border-slate-800/60">
                  <span className="px-2 py-0.5 rounded bg-slate-800/80 text-slate-300 border border-slate-700/60">
                    ID: {cluster.cluster_id}
                  </span>

                  {cluster.merchants.length > 0 && (
                    <span className="px-2 py-0.5 rounded bg-purple-500/10 text-purple-300 border border-purple-500/30">
                      Merchants: {cluster.merchants.join(", ")}
                    </span>
                  )}

                  {cluster.live_injected_count > 0 && (
                    <span className="px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-300 border border-cyan-500/30 font-semibold">
                      {cluster.live_injected_count} live-injected
                    </span>
                  )}

                  <span className="px-2 py-0.5 rounded bg-slate-800/60 text-slate-400">
                    {cluster.seeded_count} seeded
                  </span>

                  <span className="text-slate-500 text-[11px] ml-auto">
                    Active: {new Date(cluster.first_seen).toLocaleDateString()} &rarr; {new Date(cluster.last_seen).toLocaleDateString()}
                  </span>
                </div>

                {/* Expanded Details Section */}
                {isExpanded && (
                  <div className="mt-4 pt-4 border-t border-slate-800 space-y-3">
                    {/* Explainability / Grounding Block */}
                    <div className="p-3.5 rounded-lg bg-slate-950/70 border border-slate-800 text-xs font-mono space-y-1.5">
                      <div className="flex items-center gap-2 text-slate-300 font-semibold">
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                        <span>Clustering Reason & Matched Dimensions:</span>
                      </div>
                      <p className="text-slate-400 pl-5">
                        {cluster.evidence.reason}
                      </p>
                      <div className="pl-5 text-[11px] text-slate-500 flex flex-wrap gap-2 pt-1">
                        <span>Matched Fields: [{cluster.evidence.matched_fields.join(", ")}]</span>
                      </div>
                    </div>

                    {/* Member Exception IDs */}
                    <div>
                      <span className="text-xs font-mono text-slate-400 block mb-1.5">
                        Member Exceptions ({cluster.exception_ids.length}):
                      </span>
                      <div className="flex flex-wrap gap-1.5">
                        {cluster.exception_ids.map((id) => (
                          <span
                            key={id}
                            className="px-2 py-0.5 rounded bg-slate-800/90 border border-slate-700 text-slate-200 text-xs font-mono"
                          >
                            {id}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      ) : (
        <div className="py-12 text-center rounded-xl bg-slate-900/40 border border-slate-800/60">
          <Layers className="w-10 h-10 text-slate-600 mx-auto mb-3" />
          <p className="text-sm text-slate-400 font-medium">No recurring patterns detected.</p>
          <p className="text-xs text-slate-500 mt-1 max-w-md mx-auto">
            Exceptions in the current dataset are isolated or do not meet the minimum cluster threshold (≥ {clustersData?.min_cluster_size ?? 2}).
          </p>
        </div>
      )}
    </section>
  );
}

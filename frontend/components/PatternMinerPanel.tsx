"use client";

import React, { useState, useEffect } from "react";
import {
  Layers,
  Network,
  RefreshCw,
  Filter,
  Building2,
  Clock,
  ShieldAlert,
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { ClustersResponse, ExceptionCluster } from "../types";
import { fetchClusters, refreshClusters } from "../lib/api";
import { executeWithColdStartRetry } from "../lib/resilience";
import { ColdStartWakingCard } from "./ColdStartWakingCard";
import { formatPaiseOrUnavailable } from "../lib/formatters";
import { Button } from "./ui/Button";

export function PatternMinerPanel() {
  const [clustersData, setClustersData] = useState<ClustersResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [wakingState, setWakingState] = useState<{ attempt: number; isTimeout: boolean } | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [selectedType, setSelectedType] = useState<string>("ALL");
  const [selectedSource, setSelectedSource] = useState<string>("ALL");
  const [expandedClusterId, setExpandedClusterId] = useState<string | null>(null);

  // Progressive disclosure
  const [showAll, setShowAll] = useState(false);

  useEffect(() => {
    loadClusters();
  }, [selectedType, selectedSource]);

  const loadClusters = async () => {
    setLoading(true);
    setError(null);
    setWakingState(null);
    try {
      const params: any = {};
      if (selectedType !== "ALL") params.pattern_type = selectedType;
      if (selectedSource !== "ALL") params.source = selectedSource;

      const res = await executeWithColdStartRetry(
        () => fetchClusters(params),
        {
          onWaking: (attempt) => setWakingState({ attempt, isTimeout: false }),
          onRecovered: () => setWakingState(null),
        }
      );
      setClustersData(res);
      setWakingState(null);
    } catch (err: any) {
      if (wakingState && wakingState.attempt >= 6) {
        setWakingState({ attempt: 6, isTimeout: true });
      } else {
        setError(err.message || "Failed to load pattern clusters.");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    setError(null);
    try {
      await refreshClusters();
      await loadClusters();
    } catch (err: any) {
      setError(err.message || "Failed to mine clusters.");
    } finally {
      setRefreshing(false);
    }
  };

  const formatRupees = (paise: number) => {
    return formatPaiseOrUnavailable(paise, "₹0.00");
  };

  const getTypeIcon = (type: string) => {
    switch (type) {
      case "FAMILY_SIGNATURE":
        return <Network className="w-4 h-4 text-sky-400" />;
      case "MERCHANT_REPEATED_FAMILY":
        return <Building2 className="w-4 h-4 text-purple-400" />;
      case "CONTROL_FINDING_SIGNATURE":
        return <ShieldAlert className="w-4 h-4 text-amber-400" />;
      case "TIMING_SLA_SIGNATURE":
        return <Clock className="w-4 h-4 text-cyan-400" />;
      default:
        return <Network className="w-4 h-4 text-slate-400" />;
    }
  };

  const getTypeBadgeStyle = (type: string) => {
    switch (type) {
      case "FAMILY_SIGNATURE":
        return "bg-sky-950/30 border-sky-800/40 text-sky-300";
      case "MERCHANT_REPEATED_FAMILY":
        return "bg-purple-950/30 border-purple-800/40 text-purple-300";
      case "CONTROL_FINDING_SIGNATURE":
        return "bg-amber-950/30 border-amber-800/40 text-amber-300";
      case "TIMING_SLA_SIGNATURE":
        return "bg-cyan-950/30 border-cyan-800/40 text-cyan-300";
      default:
        return "bg-slate-900 border-slate-800 text-slate-300";
    }
  };

  const formatPatternType = (type: string) => {
    switch (type) {
      case "FAMILY_SIGNATURE":
        return "Family Signature";
      case "MERCHANT_REPEATED_FAMILY":
        return "Merchant Repeated Family";
      case "CONTROL_FINDING_SIGNATURE":
        return "Control Finding Signature";
      case "TIMING_SLA_SIGNATURE":
        return "Timing SLA Signature";
      default:
        return type.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
    }
  };

  const clusters = clustersData?.clusters || [];
  const visibleClusters = showAll ? clusters : clusters.slice(0, 6);

  return (
    <section
      id="patterns"
      className="rounded-xl p-5 sm:p-6 border border-slate-800/80 bg-[#0d121d] shadow-sm relative overflow-hidden"
    >
      {/* Subordinate Panel Header */}
      <header className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-800/80 mb-5">
        <div className="flex items-start sm:items-center gap-3 min-w-0">
          <div className="p-2 rounded-lg bg-[#111726] border border-slate-800 text-sky-400 shrink-0">
            <Network className="w-4 h-4" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h2 className="text-base font-semibold text-white tracking-tight font-sans">
                Deterministic Exception Pattern Miner
              </h2>
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-mono bg-sky-950/30 border border-sky-800/40 text-sky-300">
                <Network className="w-3 h-3 text-sky-400" />
                <span>Tier-2 Pattern Engine</span>
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-0.5 max-w-2xl leading-relaxed">
              Uncovers recurring operational signatures, repeated merchant anomalies, and systemic SLA delays across seeded and live-injected cases with explainable evidence.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0 self-start sm:self-center">
          <Button
            onClick={handleRefresh}
            disabled={refreshing || loading}
            variant="primary"
            size="sm"
            icon={<RefreshCw className={`w-3.5 h-3.5 ${refreshing ? "animate-spin" : ""}`} />}
          >
            {refreshing ? "Mining..." : "Recompute patterns"}
          </Button>
        </div>
      </header>

      {/* Top Metrics Row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-5">
        <div className="p-3.5 rounded-lg bg-[#090d16] border border-slate-800/80">
          <span className="text-xs font-medium text-slate-400 font-sans block mb-0.5">Discovered Patterns</span>
          <span className="text-2xl font-bold text-white financial-num">
            {clustersData?.total_clusters ?? "—"}
          </span>
        </div>

        <div className="p-3.5 rounded-lg bg-[#090d16] border border-slate-800/80">
          <span className="text-xs font-medium text-slate-400 font-sans block mb-0.5">Clustered Exceptions</span>
          <span className="text-2xl font-bold text-sky-400 financial-num">
            {clustersData?.total_clustered_exceptions ?? "—"}
          </span>
        </div>

        <div className="p-3.5 rounded-lg bg-[#090d16] border border-slate-800/80">
          <span className="text-xs font-medium text-slate-400 font-sans block mb-0.5">Total Clustered Exposure</span>
          <span className="text-2xl font-bold text-emerald-400 financial-num">
            {clustersData ? formatRupees(clustersData.total_clustered_exposure) : "—"}
          </span>
        </div>

        <div className="p-3.5 rounded-lg bg-[#090d16] border border-slate-800/80">
          <span className="text-xs font-medium text-slate-400 font-sans block mb-0.5">Min. Cluster Size</span>
          <span className="text-2xl font-bold text-slate-300 financial-num">
            &ge; {clustersData?.min_cluster_size ?? 2}
          </span>
        </div>
      </div>

      {/* Filters Bar */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3 mb-5 p-3 rounded-lg bg-[#090d16] border border-slate-800/80">
        <div className="flex flex-wrap items-center gap-1.5 text-xs font-sans">
          <span className="h-8 flex items-center text-slate-300 mr-1 gap-1 text-[11px] font-medium shrink-0 font-sans">
            <Filter className="w-3 h-3 text-sky-400" /> Pattern type:
          </span>
          {["ALL", "FAMILY_SIGNATURE", "MERCHANT_REPEATED_FAMILY", "CONTROL_FINDING_SIGNATURE", "TIMING_SLA_SIGNATURE"].map((t) => (
            <button
              key={t}
              onClick={() => setSelectedType(t)}
              className={`h-8 px-2.5 rounded border transition-colors cursor-pointer text-[11px] font-medium font-sans flex items-center justify-center focus:outline-none focus:ring-1 focus:ring-sky-500/50 ${
                selectedType === t
                  ? "bg-sky-950/40 border-sky-800/60 text-sky-300 font-semibold"
                  : "bg-[#0d121d] border-slate-800 text-slate-400 hover:text-slate-200 hover:border-slate-700"
              }`}
            >
              {t === "ALL" ? "All types" : formatPatternType(t)}
            </button>
          ))}
        </div>

        <div className="flex flex-wrap items-center gap-1.5 text-xs font-sans">
          <span className="h-8 flex items-center text-slate-300 text-[11px] font-medium shrink-0 font-sans">
            Source:
          </span>
          {["ALL", "seeded", "live-injected"].map((s) => (
            <button
              key={s}
              onClick={() => setSelectedSource(s)}
              className={`h-8 px-2.5 rounded border transition-colors cursor-pointer text-[11px] font-mono flex items-center justify-center focus:outline-none focus:ring-1 focus:ring-sky-500/50 ${
                selectedSource === s
                  ? "bg-sky-950/40 border-sky-800/60 text-sky-300 font-medium"
                  : "bg-[#0d121d] border-slate-800 text-slate-400 hover:text-slate-200 hover:border-slate-700"
              }`}
            >
              {s === "ALL" ? "All" : s === "seeded" ? "Synthetic" : "Live rails"}
            </button>
          ))}
        </div>
      </div>

      {/* Error / Waking state */}
      {wakingState ? (
        <div className="mb-5">
          <ColdStartWakingCard
            attempt={wakingState.attempt}
            maxAttempts={6}
            isTimeout={wakingState.isTimeout}
            onRetry={loadClusters}
            description="Connecting to Exception Pattern Miner…"
            compact
          />
        </div>
      ) : error ? (
        <div className="p-3 rounded-lg bg-rose-950/30 border border-rose-800/40 text-rose-300 text-xs flex items-start gap-2.5 mb-5">
          <AlertTriangle className="w-4 h-4 shrink-0 text-rose-400 mt-0.5" />
          <div>
            <p className="font-semibold">Pattern miner error</p>
            <p className="text-rose-300/80 mt-0.5">{error}</p>
          </div>
        </div>
      ) : null}

      {/* Clusters List with Progressive Disclosure */}
      {loading && !clustersData ? (
        <div className="py-12 text-center text-slate-400 font-mono text-xs">
          <RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2 text-sky-400" />
          Mining exception patterns...
        </div>
      ) : visibleClusters.length > 0 ? (
        <div className="space-y-3">
          {visibleClusters.map((cluster) => {
            const isExpanded = expandedClusterId === cluster.cluster_id;
            return (
              <div
                key={cluster.cluster_id}
                className="p-4 rounded-xl bg-[#090d16] border border-slate-800/80 hover:border-slate-700/80 transition-colors"
              >
                {/* Cluster Card Header */}
                <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3 mb-1.5">
                  <div className="flex items-start gap-3">
                    <div className="p-1.5 rounded-lg bg-[#0d121d] border border-slate-800 mt-0.5 shrink-0">
                      {getTypeIcon(cluster.pattern_type)}
                    </div>
                    <div>
                      {/* PRIMARY: Strong Title */}
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="text-sm sm:text-base font-semibold text-white tracking-tight font-sans">
                          {cluster.pattern_label}
                        </h3>
                        <span className={`px-2 py-0.5 rounded text-[11px] font-mono border font-medium ${getTypeBadgeStyle(cluster.pattern_type)}`}>
                          {formatPatternType(cluster.pattern_type)}
                        </span>
                      </div>

                      {/* SECONDARY: Description */}
                      <p className="text-xs text-slate-300 mt-1 leading-relaxed">
                        {cluster.description}
                      </p>

                      {/* METADATA: Unified Compact Line */}
                      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] font-mono text-slate-400 mt-2">
                        <span className="text-slate-200 font-medium">{cluster.exception_count} cases</span>
                        <span className="text-slate-600">&bull;</span>
                        <span className="text-slate-300">{cluster.merchants.length} merchants</span>
                        <span className="text-slate-600">&bull;</span>
                        <span className="text-emerald-400 font-medium">{formatRupees(cluster.total_exposure)} exposure</span>
                        {cluster.live_injected_count > 0 && (
                          <>
                            <span className="text-slate-600">&bull;</span>
                            <span className="text-sky-300 font-medium">
                              {cluster.live_injected_count} live-injected
                            </span>
                          </>
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 shrink-0 self-end sm:self-start">
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => setExpandedClusterId(isExpanded ? null : cluster.cluster_id)}
                      icon={isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                      aria-label={isExpanded ? "Collapse cluster details" : "Expand cluster details"}
                    >
                      {isExpanded ? "Collapse" : "Details"}
                    </Button>
                  </div>
                </div>

                {/* Expanded Details Section */}
                {isExpanded && (
                  <div className="mt-3 pt-3 border-t border-slate-800/80 space-y-3">
                    {/* Explainability / Grounding Block */}
                    <div className="p-3 rounded-lg bg-[#0d121d] border border-slate-800 text-xs font-mono space-y-1">
                      <div className="flex items-center gap-1.5 text-slate-300 font-medium">
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                        <span>Clustering Reason &amp; Matched Dimensions:</span>
                      </div>
                      <p className="text-slate-400 pl-5 leading-relaxed">
                        {cluster.evidence.reason}
                      </p>
                      <div className="pl-5 text-[11px] text-slate-400 flex flex-wrap gap-2 pt-0.5">
                        <span>Matched fields: [{cluster.evidence.matched_fields.join(", ")}]</span>
                      </div>
                    </div>

                    {/* Member Exception IDs */}
                    <div>
                      <span className="text-[11px] font-mono text-slate-400 block mb-1">
                        Member Exceptions ({cluster.exception_ids.length}):
                      </span>
                      <div className="flex flex-wrap gap-1.5 max-h-36 overflow-y-auto p-2 bg-[#0d121d] rounded-lg border border-slate-800/80">
                        {cluster.exception_ids.map((id) => (
                          <span
                            key={id}
                            className="px-2 py-0.5 rounded bg-slate-800 border border-slate-700 text-slate-200 text-xs font-mono"
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

          {/* Progressive Disclosure Toggle Button */}
          {clusters.length > 6 && (
            <div className="pt-2 text-center">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setShowAll(!showAll)}
                icon={showAll ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                className="w-full sm:w-auto"
              >
                {showAll ? "Show fewer patterns" : `Show all patterns (${clusters.length})`}
              </Button>
            </div>
          )}
        </div>
      ) : (
        <div className="py-10 text-center rounded-xl bg-[#090d16] border border-slate-800/80">
          <Layers className="w-8 h-8 text-slate-600 mx-auto mb-2" />
          <p className="text-xs text-slate-400 font-medium">No recurring patterns detected.</p>
          <p className="text-[11px] text-slate-400 mt-1 max-w-md mx-auto">
            Exceptions in the current dataset are isolated or do not meet the minimum cluster threshold (≥ {clustersData?.min_cluster_size ?? 2}).
          </p>
        </div>
      )}
    </section>
  );
}

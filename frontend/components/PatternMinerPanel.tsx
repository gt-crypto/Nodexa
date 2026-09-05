"use client";

import React, { useState, useEffect } from "react";
import {
  Network,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  AlertTriangle,
  Building,
  Clock,
  Layers,
  CheckCircle2,
  Filter,
} from "lucide-react";
import { PatternClustersResponse, PatternCluster } from "../types";
import { fetchPatternClusters, triggerPatternMining } from "../lib/api";
import { executeWithColdStartRetry } from "../lib/resilience";
import { ColdStartWakingCard } from "./ColdStartWakingCard";
import { Button } from "./ui/Button";

function formatRupees(paise: number): string {
  const rupees = paise / 100;
  return `₹${rupees.toLocaleString("en-IN", { minimumFractionDigits: 2 })}`;
}

function formatPatternType(type: string): string {
  switch (type) {
    case "FAMILY_SIGNATURE":
      return "Anomaly signature";
    case "MERCHANT_REPEATED_FAMILY":
      return "Merchant concentration";
    case "CONTROL_FINDING_SIGNATURE":
      return "Control invariant breach";
    case "TIMING_SLA_SIGNATURE":
      return "Banking delay signature";
    default:
      return type.replace(/_/g, " ").toLowerCase();
  }
}

function getTypeBadgeStyle(type: string): string {
  switch (type) {
    case "FAMILY_SIGNATURE":
      return "bg-indigo-50 border-indigo-200 text-indigo-700";
    case "MERCHANT_REPEATED_FAMILY":
      return "bg-purple-50 border-purple-200 text-purple-700";
    case "CONTROL_FINDING_SIGNATURE":
      return "bg-amber-50 border-amber-200 text-amber-800";
    case "TIMING_SLA_SIGNATURE":
      return "bg-blue-50 border-blue-200 text-blue-700";
    default:
      return "bg-slate-100 border-slate-200 text-slate-700";
  }
}

function getTypeIcon(type: string) {
  switch (type) {
    case "FAMILY_SIGNATURE":
      return <Layers className="w-4 h-4 text-indigo-600" />;
    case "MERCHANT_REPEATED_FAMILY":
      return <Building className="w-4 h-4 text-purple-600" />;
    case "CONTROL_FINDING_SIGNATURE":
      return <AlertTriangle className="w-4 h-4 text-amber-600" />;
    case "TIMING_SLA_SIGNATURE":
      return <Clock className="w-4 h-4 text-blue-600" />;
    default:
      return <Network className="w-4 h-4 text-indigo-600" />;
  }
}

export function PatternMinerPanel() {
  const [clustersData, setClustersData] = useState<PatternClustersResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [wakingState, setWakingState] = useState<{ attempt: number; isTimeout: boolean } | null>(null);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedType, setSelectedType] = useState<string>("ALL");
  const [selectedSource, setSelectedSource] = useState<string>("ALL");
  const [expandedClusterId, setExpandedClusterId] = useState<string | null>(null);
  const [showAll, setShowAll] = useState<boolean>(false);

  const loadClusters = async () => {
    setLoading(true);
    setError(null);
    setWakingState(null);
    try {
      const data = await executeWithColdStartRetry(
        () => fetchPatternClusters(),
        {
          onWaking: (attempt) => setWakingState({ attempt, isTimeout: false }),
          onRecovered: () => setWakingState(null),
        }
      );
      setClustersData(data);
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
      await triggerPatternMining();
      await loadClusters();
    } catch (err: any) {
      setError(err.message || "Failed to trigger pattern mining.");
    } finally {
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadClusters();
  }, []);

  const clusters: PatternCluster[] = (clustersData?.clusters || []).filter((c) => {
    if (selectedType !== "ALL" && c.pattern_type !== selectedType) return false;
    if (selectedSource === "seeded" && c.live_injected_count > 0 && c.live_injected_count === c.exception_count) return false;
    if (selectedSource === "live-injected" && c.live_injected_count === 0) return false;
    return true;
  });

  const visibleClusters = showAll ? clusters : clusters.slice(0, 6);

  return (
    <section
      id="patterns"
      className="rounded-xl p-5 sm:p-6 border border-slate-200 bg-white shadow-xs relative overflow-hidden"
    >
      {/* Header */}
      <header className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-100 mb-5">
        <div className="flex items-start sm:items-center gap-3 min-w-0">
          <div className="p-2 rounded-lg bg-indigo-50 border border-indigo-100 text-indigo-600 shrink-0">
            <Network className="w-4 h-4" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h2 className="text-base font-bold text-slate-900 tracking-tight font-sans">
                Deterministic Exception Pattern Miner
              </h2>
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-mono bg-indigo-50 border border-indigo-200 text-indigo-700 font-medium">
                <Network className="w-3 h-3 text-indigo-600" />
                <span>Tier-2 Pattern Engine</span>
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-0.5 max-w-2xl leading-relaxed">
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
        <div className="p-3.5 rounded-lg bg-slate-50 border border-slate-200">
          <span className="text-xs font-medium text-slate-500 font-sans block mb-0.5">Discovered Patterns</span>
          <span className="text-2xl font-bold text-slate-900 financial-num">
            {clustersData?.total_clusters ?? "—"}
          </span>
        </div>

        <div className="p-3.5 rounded-lg bg-slate-50 border border-slate-200">
          <span className="text-xs font-medium text-slate-500 font-sans block mb-0.5">Clustered Exceptions</span>
          <span className="text-2xl font-bold text-indigo-600 financial-num">
            {clustersData?.total_clustered_exceptions ?? "—"}
          </span>
        </div>

        <div className="p-3.5 rounded-lg bg-slate-50 border border-slate-200">
          <span className="text-xs font-medium text-slate-500 font-sans block mb-0.5">Total Clustered Exposure</span>
          <span className="text-2xl font-bold text-emerald-700 financial-num">
            {clustersData ? formatRupees(clustersData.total_clustered_exposure) : "—"}
          </span>
        </div>

        <div className="p-3.5 rounded-lg bg-slate-50 border border-slate-200">
          <span className="text-xs font-medium text-slate-500 font-sans block mb-0.5">Min. Cluster Size</span>
          <span className="text-2xl font-bold text-slate-700 financial-num">
            &ge; {clustersData?.min_cluster_size ?? 2}
          </span>
        </div>
      </div>

      {/* Filters Bar */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3 mb-5 p-3 rounded-lg bg-slate-50 border border-slate-200">
        <div className="flex flex-wrap items-center gap-1.5 text-xs font-sans">
          <span className="h-8 flex items-center text-slate-700 mr-1 gap-1 text-[11px] font-medium shrink-0 font-sans">
            <Filter className="w-3 h-3 text-indigo-600" /> Pattern type:
          </span>
          {["ALL", "FAMILY_SIGNATURE", "MERCHANT_REPEATED_FAMILY", "CONTROL_FINDING_SIGNATURE", "TIMING_SLA_SIGNATURE"].map((t) => (
            <button
              key={t}
              onClick={() => setSelectedType(t)}
              className={`h-8 px-2.5 rounded-md border transition-colors cursor-pointer text-[11px] font-medium font-sans flex items-center justify-center focus:outline-none focus:ring-1 focus:ring-indigo-500/30 ${
                selectedType === t
                  ? "bg-indigo-50 border-indigo-200 text-indigo-700 font-semibold shadow-xs"
                  : "bg-white border-slate-200 text-slate-600 hover:text-slate-900 hover:border-slate-300"
              }`}
            >
              {t === "ALL" ? "All types" : formatPatternType(t)}
            </button>
          ))}
        </div>

        <div className="flex flex-wrap items-center gap-1.5 text-xs font-sans">
          <span className="h-8 flex items-center text-slate-700 text-[11px] font-medium shrink-0 font-sans">
            Source:
          </span>
          {["ALL", "seeded", "live-injected"].map((s) => (
            <button
              key={s}
              onClick={() => setSelectedSource(s)}
              className={`h-8 px-2.5 rounded-md border transition-colors cursor-pointer text-[11px] font-mono flex items-center justify-center focus:outline-none focus:ring-1 focus:ring-indigo-500/30 ${
                selectedSource === s
                  ? "bg-indigo-50 border-indigo-200 text-indigo-700 font-semibold shadow-xs"
                  : "bg-white border-slate-200 text-slate-600 hover:text-slate-900 hover:border-slate-300"
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
        <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-start gap-2.5 mb-5">
          <AlertTriangle className="w-4 h-4 shrink-0 text-rose-600 mt-0.5" />
          <div>
            <p className="font-semibold">Pattern miner error</p>
            <p className="text-rose-600 mt-0.5">{error}</p>
          </div>
        </div>
      ) : null}

      {/* Clusters List with Progressive Disclosure */}
      {loading && !clustersData ? (
        <div className="py-12 text-center text-slate-500 font-mono text-xs">
          <RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2 text-indigo-600" />
          Mining exception patterns...
        </div>
      ) : visibleClusters.length > 0 ? (
        <div className="space-y-3">
          {visibleClusters.map((cluster) => {
            const isExpanded = expandedClusterId === cluster.cluster_id;
            return (
              <div
                key={cluster.cluster_id}
                className="p-4 rounded-xl bg-white border border-slate-200 hover:border-slate-300 transition-colors shadow-xs"
              >
                {/* Cluster Card Header */}
                <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3 mb-1.5">
                  <div className="flex items-start gap-3">
                    <div className="p-1.5 rounded-lg bg-slate-50 border border-slate-200 mt-0.5 shrink-0">
                      {getTypeIcon(cluster.pattern_type)}
                    </div>
                    <div>
                      {/* PRIMARY: Strong Title */}
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="text-sm sm:text-base font-bold text-slate-900 tracking-tight font-sans">
                          {cluster.pattern_label}
                        </h3>
                        <span className={`px-2 py-0.5 rounded text-[11px] font-mono border font-medium ${getTypeBadgeStyle(cluster.pattern_type)}`}>
                          {formatPatternType(cluster.pattern_type)}
                        </span>
                      </div>

                      {/* SECONDARY: Description */}
                      <p className="text-xs text-slate-600 mt-1 leading-relaxed">
                        {cluster.description}
                      </p>

                      {/* METADATA: Unified Compact Line */}
                      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] font-mono text-slate-500 mt-2">
                        <span className="text-slate-800 font-semibold">{cluster.exception_count} cases</span>
                        <span className="text-slate-300">&bull;</span>
                        <span className="text-slate-700">{cluster.merchants.length} merchants</span>
                        <span className="text-slate-300">&bull;</span>
                        <span className="text-emerald-700 font-semibold">{formatRupees(cluster.total_exposure)} exposure</span>
                        {cluster.live_injected_count > 0 && (
                          <>
                            <span className="text-slate-300">&bull;</span>
                            <span className="text-indigo-700 font-semibold">
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
                  <div className="mt-3 pt-3 border-t border-slate-100 space-y-3">
                    {/* Explainability / Grounding Block */}
                    <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 text-xs font-mono space-y-1">
                      <div className="flex items-center gap-1.5 text-slate-800 font-semibold">
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                        <span>Clustering Reason &amp; Matched Dimensions:</span>
                      </div>
                      <p className="text-slate-600 pl-5 leading-relaxed">
                        {cluster.evidence.reason}
                      </p>
                      <div className="pl-5 text-[11px] text-slate-500 flex flex-wrap gap-2 pt-0.5">
                        <span>Matched fields: [{cluster.evidence.matched_fields.join(", ")}]</span>
                      </div>
                    </div>

                    {/* Member Exception IDs */}
                    <div>
                      <span className="text-[11px] font-mono text-slate-500 block mb-1 font-medium">
                        Member Exceptions ({cluster.exception_ids.length}):
                      </span>
                      <div className="flex flex-wrap gap-1.5 max-h-36 overflow-y-auto p-2 bg-slate-50 rounded-lg border border-slate-200">
                        {cluster.exception_ids.map((id) => (
                          <span
                            key={id}
                            className="px-2 py-0.5 rounded bg-white border border-slate-200 text-slate-800 text-xs font-mono font-medium shadow-2xs"
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
        <div className="py-10 text-center rounded-xl bg-slate-50 border border-slate-200">
          <Layers className="w-8 h-8 text-slate-400 mx-auto mb-2" />
          <p className="text-xs text-slate-700 font-semibold">No recurring patterns detected.</p>
          <p className="text-[11px] text-slate-500 mt-1 max-w-md mx-auto">
            Exceptions in the current dataset are isolated or do not meet the minimum cluster threshold (≥ {clustersData?.min_cluster_size ?? 2}).
          </p>
        </div>
      )}
    </section>
  );
}

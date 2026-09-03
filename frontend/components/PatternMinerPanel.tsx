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
import { Button } from "./ui/Button";
import { SectionHeading } from "./ui/SectionHeading";

export function PatternMinerPanel() {
  const [clustersData, setClustersData] = useState<ClustersResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [selectedType, setSelectedType] = useState<string>("ALL");
  const [selectedSource, setSelectedSource] = useState<string>("ALL");
  const [expandedClusterId, setExpandedClusterId] = useState<string | null>(null);

  // Progressive disclosure (Issue 6: Wall of data fix)
  const [showAll, setShowAll] = useState(false);

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
        return <Layers className="w-5 h-5 text-cyan-400" />;
      case "MERCHANT_REPEATED_FAMILY":
        return <Building2 className="w-5 h-5 text-purple-400" />;
      case "CONTROL_FINDING_SIGNATURE":
        return <ShieldAlert className="w-5 h-5 text-amber-400" />;
      case "TIMING_SLA_SIGNATURE":
        return <Clock className="w-5 h-5 text-teal-400" />;
      default:
        return <Network className="w-5 h-5 text-slate-400" />;
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
  const visibleClusters = showAll ? clusters : clusters.slice(0, 6);

  return (
    <section
      id="patterns"
      className="glass-panel rounded-2xl p-6 sm:p-8 border border-slate-800/80 shadow-2xl relative overflow-hidden"
    >
      {/* Ambient glow */}
      <div className="absolute -top-24 -right-24 w-72 h-72 bg-purple-500/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute -bottom-24 -left-24 w-72 h-72 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none" />

      {/* Section Header (Issue 3 & 14) */}
      <SectionHeading
        icon={<Network className="w-6 h-6 text-purple-400" />}
        title="Deterministic Exception Pattern Miner"
        badge={{
          text: "Tier-2 Pattern Miner Active (v2.0)",
          icon: <Network className="w-3.5 h-3.5 text-purple-400" />,
          color: "bg-purple-500/10 border-purple-500/30 text-purple-300",
        }}
        description="Uncovers recurring operational signatures, repeated merchant anomalies, and systemic SLA delays across seeded and live-injected cases with explainable evidence."
        action={
          <Button
            onClick={handleRefresh}
            disabled={refreshing || loading}
            variant="secondary"
            icon={<RefreshCw className={`w-4 h-4 ${refreshing ? "animate-spin" : ""}`} />}
          >
            {refreshing ? "Mining..." : "Recompute patterns"}
          </Button>
        }
      />

      {/* Top Metrics Row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800">
          <span className="text-xs font-mono text-slate-400 block mb-1">Discovered patterns</span>
          <span className="text-2xl font-extrabold text-white font-mono">
            {clustersData?.total_clusters ?? "—"}
          </span>
        </div>

        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800">
          <span className="text-xs font-mono text-slate-400 block mb-1">Clustered exceptions</span>
          <span className="text-2xl font-extrabold text-cyan-300 font-mono">
            {clustersData?.total_clustered_exceptions ?? "—"}
          </span>
        </div>

        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800">
          <span className="text-xs font-mono text-slate-400 block mb-1">Total clustered exposure</span>
          <span className="text-2xl font-extrabold text-emerald-300 font-mono">
            {clustersData ? formatRupees(clustersData.total_clustered_exposure) : "—"}
          </span>
        </div>

        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800">
          <span className="text-xs font-mono text-slate-400 block mb-1">Min. cluster size</span>
          <span className="text-2xl font-extrabold text-amber-300 font-mono">
            ≥ {clustersData?.min_cluster_size ?? 2}
          </span>
        </div>
      </div>

      {/* Filters Bar (Issues 6 & 19: Unified Brand Active Filters & Prominent Group Labels) */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6 p-3.5 rounded-xl bg-slate-900/40 border border-slate-800/80">
        <div className="flex flex-wrap items-center gap-2 text-xs font-mono">
          <span className="text-slate-200 mr-1 flex items-center gap-1 font-semibold text-xs">
            <Filter className="w-3.5 h-3.5 text-teal-400" /> Pattern type:
          </span>
          {["ALL", "FAMILY_SIGNATURE", "MERCHANT_REPEATED_FAMILY", "CONTROL_FINDING_SIGNATURE", "TIMING_SLA_SIGNATURE"].map((t) => (
            <button
              key={t}
              onClick={() => setSelectedType(t)}
              className={`px-3 py-1 rounded-lg border transition-all duration-150 cursor-pointer ${
                selectedType === t
                  ? "bg-teal-500/20 border-teal-500/50 text-teal-300 font-semibold shadow-sm shadow-teal-500/10"
                  : "bg-slate-900/60 border-slate-800 text-slate-400 hover:text-slate-200 hover:bg-slate-800/60"
              }`}
            >
              {t === "ALL" ? "All types" : t.replace(/_/g, " ")}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2 text-xs font-mono">
          <span className="text-slate-200 font-semibold text-xs">Source:</span>
          {["ALL", "seeded", "live-injected"].map((s) => (
            <button
              key={s}
              onClick={() => setSelectedSource(s)}
              className={`px-2.5 py-1 rounded-lg border transition-all duration-150 cursor-pointer ${
                selectedSource === s
                  ? "bg-teal-500/20 border-teal-500/50 text-teal-300 font-semibold shadow-sm shadow-teal-500/10"
                  : "bg-slate-900/60 border-slate-800 text-slate-400 hover:text-slate-200 hover:bg-slate-800/60"
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
            <p className="font-semibold">Pattern miner error</p>
            <p className="text-xs text-rose-300/80 mt-0.5">{error}</p>
          </div>
        </div>
      )}

      {/* Clusters List with Progressive Disclosure (Issue 6 & Issue 18) */}
      {loading && !clustersData ? (
        <div className="py-12 text-center text-slate-500 font-mono text-sm">
          <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-purple-400" />
          Mining exception patterns...
        </div>
      ) : visibleClusters.length > 0 ? (
        <div className="space-y-4">
          {visibleClusters.map((cluster) => {
            const isExpanded = expandedClusterId === cluster.cluster_id;
            return (
              <div
                key={cluster.cluster_id}
                className="p-5 rounded-xl bg-slate-900/70 border border-slate-800 hover:border-slate-750 transition-all duration-200"
              >
                {/* Cluster Card Header with Dominant Title Hierarchy (Issue 18) */}
                <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3 mb-2">
                  <div className="flex items-start gap-3">
                    <div className="p-2 rounded-lg bg-slate-800/80 border border-slate-700/60 mt-0.5 shrink-0">
                      {getTypeIcon(cluster.pattern_type)}
                    </div>
                    <div>
                      {/* PRIMARY: Strong Title (Issue 18) */}
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="text-base sm:text-lg font-bold text-white tracking-tight">
                          {cluster.pattern_label}
                        </h3>
                        <span className={`px-2 py-0.5 rounded-full text-xs font-mono border uppercase ${getTypeBadgeStyle(cluster.pattern_type)}`}>
                          {cluster.pattern_type.replace(/_/g, " ")}
                        </span>
                      </div>

                      {/* SECONDARY: Description (Issue 18) */}
                      <p className="text-sm text-slate-300 mt-1 leading-relaxed">
                        {cluster.description}
                      </p>

                      {/* METADATA: Unified Compact Line (Issue 18 & Major Issue 3: Subtle Metadata Treatment) */}
                      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs font-mono text-slate-400 mt-2">
                        <span className="text-white font-medium">{cluster.exception_count} cases</span>
                        <span>•</span>
                        <span>{cluster.merchants.length} merchants</span>
                        <span>•</span>
                        <span className="text-emerald-300 font-bold">{formatRupees(cluster.total_exposure)} exposure</span>
                        {cluster.live_injected_count > 0 && (
                          <>
                            <span>•</span>
                            <span className="text-slate-400 font-medium">
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
                      icon={isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                      aria-label={isExpanded ? "Collapse cluster details" : "Expand cluster details"}
                    >
                      {isExpanded ? "Collapse" : "Details"}
                    </Button>
                  </div>
                </div>

                {/* Expanded Details Section */}
                {isExpanded && (
                  <div className="mt-4 pt-4 border-t border-slate-800 space-y-3">
                    {/* Explainability / Grounding Block */}
                    <div className="p-3.5 rounded-lg bg-slate-950/70 border border-slate-800 text-xs font-mono space-y-1.5">
                      <div className="flex items-center gap-2 text-slate-300 font-semibold">
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                        <span>Clustering reason & matched dimensions:</span>
                      </div>
                      <p className="text-slate-400 pl-5 leading-relaxed">
                        {cluster.evidence.reason}
                      </p>
                      <div className="pl-5 text-xs text-slate-500 flex flex-wrap gap-2 pt-1">
                        <span>Matched fields: [{cluster.evidence.matched_fields.join(", ")}]</span>
                      </div>
                    </div>

                    {/* Member Exception IDs */}
                    <div>
                      <span className="text-xs font-mono text-slate-400 block mb-1.5 font-medium">
                        Member exceptions ({cluster.exception_ids.length}):
                      </span>
                      <div className="flex flex-wrap gap-1.5 max-h-36 overflow-y-auto p-2 bg-slate-950/40 rounded-lg border border-slate-800/60">
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

          {/* Progressive Disclosure Toggle Button (Issue 6) */}
          {clusters.length > 6 && (
            <div className="pt-3 text-center">
              <Button
                variant="secondary"
                onClick={() => setShowAll(!showAll)}
                icon={showAll ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                className="w-full sm:w-auto"
              >
                {showAll ? "Show fewer patterns" : `Show all patterns (${clusters.length})`}
              </Button>
            </div>
          )}
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

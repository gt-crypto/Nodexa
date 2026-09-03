"use client";

import React, { useState, useEffect } from "react";
import {
  Building2,
  Shield,
  ShieldAlert,
  AlertCircle,
  TrendingUp,
  RefreshCcw,
  CheckCircle,
  Activity,
  Search,
} from "lucide-react";
import { MerchantScore, fetchMerchantScores } from "../lib/api";
import { Button } from "./ui/Button";
import { SectionHeading } from "./ui/SectionHeading";
import { StatusBadge } from "./ui/StatusBadge";

export function MerchantTrustScorePanel() {
  const [scores, setScores] = useState<MerchantScore[]>([]);
  const [selectedMerchantId, setSelectedMerchantId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadScores();
  }, []);

  const loadScores = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchMerchantScores();
      setScores(data);
      if (data.length > 0 && !selectedMerchantId) {
        setSelectedMerchantId(data[0].merchant_id);
      }
    } catch (err: any) {
      setError(err.message || "Failed to load merchant scores.");
    } finally {
      setLoading(false);
    }
  };

  const getBandColor = (band: string) => {
    switch (band) {
      case "EXCELLENT": return "text-emerald-400 bg-emerald-400/10 border-emerald-400/30";
      case "HEALTHY": return "text-teal-400 bg-teal-400/10 border-teal-400/30";
      case "WATCH": return "text-amber-400 bg-amber-400/10 border-amber-400/30";
      case "HIGH_RISK": return "text-orange-400 bg-orange-400/10 border-orange-400/30";
      case "CRITICAL": return "text-rose-400 bg-rose-400/10 border-rose-400/30";
      default: return "text-slate-400 bg-slate-400/10 border-slate-400/30";
    }
  };

  const selectedScore = scores.find(s => s.merchant_id === selectedMerchantId);

  return (
    <section id="merchants" className="w-full">
      <div className="glass-panel rounded-2xl p-6 sm:p-8 border border-slate-800/80 shadow-2xl relative overflow-hidden">
        {/* Section Header (Issue 3 & 14) */}
        <SectionHeading
          icon={<Building2 className="w-6 h-6 text-purple-400" />}
          title="Merchant Trust & Impact Scorecards"
          badge={{
            text: "Tier-2 Merchant Intelligence (v2.0)",
            icon: <Shield className="w-3.5 h-3.5 text-purple-400" />,
            color: "bg-purple-500/10 border-purple-500/30 text-purple-300",
          }}
          description="Deterministic risk & operational impact analytics for merchants participating in nodal transaction clearing."
          action={
            <Button
              variant="secondary"
              size="sm"
              onClick={loadScores}
              disabled={loading}
              icon={<RefreshCcw className={`w-3.5 h-3.5 ${loading ? "animate-spin text-teal-400" : ""}`} />}
            >
              Refresh
            </Button>
          }
        />

        {error && (
          <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-sm mb-6">
            {error}
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left: Merchant List */}
          <div className="glass-panel border border-slate-800/80 rounded-xl overflow-hidden flex flex-col h-[520px]">
            <div className="p-4 border-b border-slate-800/80 bg-slate-900/40">
              <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2 font-mono">
                <Search className="w-4 h-4 text-slate-400" />
                <span>Analyzed merchants ({scores.length})</span>
              </h3>
            </div>
            
            <div className="flex-1 overflow-y-auto p-2 space-y-2">
              {loading && scores.length === 0 ? (
                <div className="p-4 text-center text-sm text-slate-400">Loading merchant scores...</div>
              ) : scores.length === 0 ? (
                <div className="p-4 text-center text-sm text-slate-400">No merchant activity found.</div>
              ) : (
                scores.map((score) => (
                  <button
                    key={score.merchant_id}
                    onClick={() => setSelectedMerchantId(score.merchant_id)}
                    className={`w-full text-left p-3 rounded-xl border transition-colors cursor-pointer focus:outline-none focus:ring-2 focus:ring-teal-500/40 ${
                      selectedMerchantId === score.merchant_id
                        ? "bg-teal-500/15 border-teal-500/50 shadow-sm ring-1 ring-teal-500/30"
                        : "bg-slate-900/40 border-slate-800/60 hover:bg-slate-800/60"
                    }`}
                  >
                    <div className="flex justify-between items-center mb-2">
                      <span className="font-mono text-sm font-bold text-white tracking-tight">{score.merchant_id}</span>
                      <StatusBadge status={score.score_band} size="sm" />
                    </div>
                    {/* Compact Grouped Metrics (Issue 23: Balance Card Spacing) */}
                    <div className="grid grid-cols-2 gap-2 pt-2 border-t border-slate-800/60 text-xs font-mono">
                      <div className="flex items-center gap-1.5 bg-slate-900/60 px-2 py-1 rounded-md border border-slate-800/80">
                        <ShieldAlert className="w-3.5 h-3.5 text-teal-400 shrink-0" />
                        <span className="text-slate-400">Trust:</span>
                        <span className="text-white font-bold">{score.trust_score}</span>
                        <span className="text-slate-500 text-[10px]">/100</span>
                      </div>
                      <div className="flex items-center gap-1.5 bg-slate-900/60 px-2 py-1 rounded-md border border-slate-800/80">
                        <TrendingUp className="w-3.5 h-3.5 text-amber-400 shrink-0" />
                        <span className="text-slate-400">Impact:</span>
                        <span className="text-white font-bold">{score.impact_score}</span>
                        <span className="text-slate-500 text-[10px]">/100</span>
                      </div>
                    </div>
                  </button>
                ))
              )}
            </div>
          </div>

          {/* Right: Selected Merchant Detail */}
          <div className="lg:col-span-2 glass-panel border border-slate-800/80 rounded-xl overflow-hidden flex flex-col h-[520px]">
            {selectedScore ? (
              <>
                {/* Header */}
                <div className="p-6 border-b border-slate-800/80 bg-slate-900/40 flex flex-wrap justify-between items-center gap-4">
                  <div>
                    <span className="text-xs font-mono text-purple-400 uppercase tracking-wider block mb-1">Merchant profile</span>
                    <h3 className="text-xl font-bold text-white font-mono">{selectedScore.merchant_id}</h3>
                  </div>

                  <div className="flex gap-4">
                    {/* Trust Score Box (Issue 17: Prominent readable labels) */}
                    <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-3 text-center min-w-[110px]">
                      <div className="text-sm font-semibold text-slate-200 mb-1 font-mono">Trust score</div>
                      <div className="text-2xl font-mono font-bold text-white mb-1.5">{selectedScore.trust_score}</div>
                      <StatusBadge status={selectedScore.score_band} size="sm" />
                    </div>

                    {/* Impact Score Box (Issues 8 & 17: Unified TrendingUp icon & prominent labels) */}
                    <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-3 text-center min-w-[110px]">
                      <div className="text-sm font-semibold text-slate-200 mb-1 font-mono">Impact score</div>
                      <div className="text-2xl font-mono font-bold text-white mb-1.5">{selectedScore.impact_score}</div>
                      <span className="text-xs px-2 py-0.5 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-300 inline-flex items-center gap-1 font-mono font-medium">
                        <TrendingUp className="w-3 h-3 text-amber-400" />
                        Operational impact
                      </span>
                    </div>
                  </div>
                </div>

                {/* Body */}
                <div className="p-6 overflow-y-auto flex-1 grid grid-cols-1 md:grid-cols-2 gap-6">
                  {/* Metrics (Issue 15: H3) */}
                  <div className="space-y-4">
                    <h3 className="text-sm font-semibold text-slate-200 border-b border-slate-800 pb-2 font-mono">
                      Operational metrics
                    </h3>
                    
                    <div className="grid grid-cols-2 gap-3">
                      <div className="bg-slate-900/50 rounded-xl p-3.5 border border-slate-800/60">
                        <div className="text-xs text-slate-400 mb-1 font-mono">Total exceptions</div>
                        <div className="text-lg font-bold text-slate-200 font-mono">{selectedScore.metrics.exception_count}</div>
                      </div>
                      <div className="bg-slate-900/50 rounded-xl p-3.5 border border-slate-800/60">
                        <div className="text-xs text-slate-400 mb-1 font-mono">High-risk cases</div>
                        <div className="text-lg font-bold text-rose-400 font-mono">{selectedScore.metrics.high_risk_exception_count}</div>
                      </div>
                      <div className="bg-slate-900/50 rounded-xl p-3.5 border border-slate-800/60">
                        <div className="text-xs text-slate-400 mb-1 font-mono">Pattern clusters</div>
                        <div className="text-lg font-bold text-amber-400 font-mono">{selectedScore.metrics.recurring_pattern_count}</div>
                      </div>
                      <div className="bg-slate-900/50 rounded-xl p-3.5 border border-slate-800/60">
                        <div className="text-xs text-slate-400 mb-1 font-mono">Total exposure</div>
                        <div className="text-lg font-bold text-teal-400 font-mono">
                          ₹{(selectedScore.metrics.total_exposure / 100).toLocaleString(undefined, {minimumFractionDigits: 2})}
                        </div>
                      </div>
                    </div>
                    
                    {selectedScore.metrics.total_transaction_count > 0 && (
                      <div className="mt-4 text-xs text-slate-300 bg-slate-900/30 p-3 rounded-lg border border-slate-800/40">
                        <span className="font-semibold text-white">Base volume:</span> {selectedScore.metrics.total_transaction_count} transactions (₹{(selectedScore.metrics.total_transaction_volume / 100).toLocaleString(undefined, {minimumFractionDigits: 0})})
                      </div>
                    )}
                  </div>

                  {/* Factors (Issue 15: H3) */}
                  <div className="space-y-4">
                    <h3 className="text-sm font-semibold text-slate-200 border-b border-slate-800 pb-2 font-mono">
                      Determinant factors
                    </h3>
                    
                    <div className="space-y-3">
                      {selectedScore.factors.map((factor, idx) => (
                        <div key={idx} className="flex gap-3 items-start bg-slate-900/40 p-3 rounded-lg border border-slate-800/40">
                          {factor.factor === "FINANCIAL_EXPOSURE" ? (
                            <Activity className="w-4 h-4 text-amber-400 mt-0.5 shrink-0" />
                          ) : factor.direction === "POSITIVE" ? (
                            <CheckCircle className="w-4 h-4 text-emerald-400 mt-0.5 shrink-0" />
                          ) : factor.direction === "NEGATIVE" ? (
                            <AlertCircle className="w-4 h-4 text-rose-400 mt-0.5 shrink-0" />
                          ) : (
                            <Activity className="w-4 h-4 text-slate-400 mt-0.5 shrink-0" />
                          )}
                          <div>
                            <div className="flex items-center gap-2 mb-1">
                              <span className="text-xs font-semibold text-slate-200">{factor.factor.replace(/_/g, ' ')}</span>
                              <span className={`text-xs font-mono px-2 py-0.5 rounded ${
                                factor.contribution < 0 ? 'bg-rose-500/10 text-rose-400' :
                                factor.contribution > 0 ? 'bg-amber-500/10 text-amber-400' :
                                'bg-slate-500/10 text-slate-400'
                              }`}>
                                {factor.contribution > 0 ? '+' : ''}{factor.contribution} pts
                              </span>
                            </div>
                            <p className="text-xs text-slate-400 leading-relaxed">{factor.explanation}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </>
            ) : (
              <div className="p-8 text-center text-slate-400 flex flex-col items-center justify-center h-full">
                <Building2 className="w-12 h-12 text-slate-600 mb-2" />
                <p>Select a merchant from the list to view trust & impact scorecard.</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

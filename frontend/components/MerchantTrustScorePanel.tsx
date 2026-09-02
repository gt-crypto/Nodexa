"use client";

import React, { useState, useEffect } from "react";
import { 
  Building2, 
  Activity, 
  AlertCircle, 
  RefreshCcw,
  CheckCircle,
  TrendingDown,
  TrendingUp,
  ShieldAlert,
  Search,
  Bot
} from "lucide-react";
import { fetchMerchantScores, MerchantScore } from "../lib/api";

export function MerchantTrustScorePanel() {
  const [scores, setScores] = useState<MerchantScore[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedMerchantId, setSelectedMerchantId] = useState<string | null>(null);

  const loadScores = async () => {
    try {
      setLoading(true);
      const data = await fetchMerchantScores();
      setScores(data);
      if (data.length > 0 && !selectedMerchantId) {
        setSelectedMerchantId(data[0].merchant_id);
      }
      setError(null);
    } catch (err: any) {
      setError(err.message || "Failed to load merchant scores");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadScores();
    
    // Auto-refresh every 30s
    const interval = setInterval(loadScores, 30000);
    return () => clearInterval(interval);
  }, []);

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
    <section className="mb-12">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-white flex items-center gap-2">
            <Building2 className="w-6 h-6 text-purple-400" />
            Merchant Trust & Impact Score
          </h2>
          <p className="text-sm text-slate-400 mt-1">
            Deterministic risk & operational impact analytics for merchants. (Tier-2)
          </p>
        </div>
        <button
          onClick={loadScores}
          disabled={loading}
          className="flex items-center gap-2 px-3 py-1.5 rounded bg-slate-800 border border-slate-700 text-sm font-medium text-slate-300 hover:bg-slate-700 disabled:opacity-50 transition-colors"
        >
          <RefreshCcw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Merchant List */}
        <div className="glass-panel border border-slate-800/80 rounded-xl overflow-hidden flex flex-col h-[500px]">
          <div className="p-4 border-b border-slate-800/80 bg-slate-900/40">
            <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
              <Search className="w-4 h-4 text-slate-400" />
              Analyzed Merchants ({scores.length})
            </h3>
          </div>
          
          <div className="flex-1 overflow-y-auto p-2 space-y-2">
            {loading && scores.length === 0 ? (
              <div className="p-4 text-center text-sm text-slate-400">Loading...</div>
            ) : scores.length === 0 ? (
              <div className="p-4 text-center text-sm text-slate-400">No merchant activity found.</div>
            ) : (
              scores.map((score) => (
                <button
                  key={score.merchant_id}
                  onClick={() => setSelectedMerchantId(score.merchant_id)}
                  className={`w-full text-left p-3 rounded-lg border transition-colors ${
                    selectedMerchantId === score.merchant_id
                      ? "bg-purple-500/10 border-purple-500/40"
                      : "bg-slate-900/40 border-slate-800/60 hover:bg-slate-800/60"
                  }`}
                >
                  <div className="flex justify-between items-center mb-1">
                    <span className="font-mono text-sm text-slate-200">{score.merchant_id}</span>
                    <span className={`text-[10px] px-2 py-0.5 rounded-full border ${getBandColor(score.score_band)}`}>
                      {score.score_band}
                    </span>
                  </div>
                  <div className="flex justify-between items-center text-xs">
                    <span className="text-slate-400 flex items-center gap-1">
                      <ShieldAlert className="w-3 h-3 text-slate-500" />
                      Trust: {score.trust_score}/100
                    </span>
                    <span className="text-slate-400 flex items-center gap-1">
                      <Activity className="w-3 h-3 text-slate-500" />
                      Impact: {score.impact_score}/100
                    </span>
                  </div>
                </button>
              ))
            )}
          </div>
        </div>

        {/* Right: Score Details */}
        <div className="lg:col-span-2 glass-panel border border-slate-800/80 rounded-xl overflow-hidden flex flex-col h-[500px]">
          {selectedScore ? (
            <>
              {/* Header */}
              <div className="p-6 border-b border-slate-800/80 bg-slate-900/40 flex items-start justify-between">
                <div>
                  <h3 className="text-2xl font-mono font-bold text-white mb-2">
                    {selectedScore.merchant_id}
                  </h3>
                  <div className="flex gap-3">
                    <span className={`text-xs px-2.5 py-1 rounded-full border flex items-center gap-1.5 ${getBandColor(selectedScore.score_band)}`}>
                      <Activity className="w-3.5 h-3.5" />
                      {selectedScore.score_band} BAND
                    </span>
                    {selectedScore.metrics.live_injected_case_count > 0 && (
                      <span className="text-[10px] px-2 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/30 text-indigo-400 flex items-center gap-1 font-mono">
                        <Bot className="w-3 h-3" />
                        SYNTHETIC DATA INCLUDED
                      </span>
                    )}
                  </div>
                </div>
                
                <div className="flex gap-6 text-right">
                  <div>
                    <div className="text-xs text-slate-400 mb-1 uppercase tracking-wider">Trust Score</div>
                    <div className="text-3xl font-bold text-white flex items-baseline gap-1">
                      {selectedScore.trust_score}
                      <span className="text-sm text-slate-500 font-normal">/100</span>
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-slate-400 mb-1 uppercase tracking-wider">Impact Score</div>
                    <div className="text-3xl font-bold text-white flex items-baseline gap-1">
                      {selectedScore.impact_score}
                      <span className="text-sm text-slate-500 font-normal">/100</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Body */}
              <div className="p-6 overflow-y-auto flex-1 grid grid-cols-1 md:grid-cols-2 gap-6">
                
                {/* Metrics */}
                <div className="space-y-4">
                  <h4 className="text-sm font-semibold text-slate-300 border-b border-slate-800 pb-2">Operational Metrics</h4>
                  
                  <div className="grid grid-cols-2 gap-3">
                    <div className="bg-slate-900/50 rounded-lg p-3 border border-slate-800/60">
                      <div className="text-xs text-slate-400 mb-1">Total Exceptions</div>
                      <div className="text-lg font-bold text-slate-200">{selectedScore.metrics.exception_count}</div>
                    </div>
                    <div className="bg-slate-900/50 rounded-lg p-3 border border-slate-800/60">
                      <div className="text-xs text-slate-400 mb-1">High Risk Cases</div>
                      <div className="text-lg font-bold text-rose-400">{selectedScore.metrics.high_risk_exception_count}</div>
                    </div>
                    <div className="bg-slate-900/50 rounded-lg p-3 border border-slate-800/60">
                      <div className="text-xs text-slate-400 mb-1">Pattern Clusters</div>
                      <div className="text-lg font-bold text-amber-400">{selectedScore.metrics.recurring_pattern_count}</div>
                    </div>
                    <div className="bg-slate-900/50 rounded-lg p-3 border border-slate-800/60">
                      <div className="text-xs text-slate-400 mb-1">Total Exposure</div>
                      <div className="text-lg font-bold text-teal-400 font-mono">
                        ₹{(selectedScore.metrics.total_exposure / 100).toLocaleString(undefined, {minimumFractionDigits: 2})}
                      </div>
                    </div>
                  </div>
                  
                  {selectedScore.metrics.total_transaction_count > 0 && (
                    <div className="mt-4 text-xs text-slate-400 bg-slate-900/30 p-3 rounded-lg border border-slate-800/40">
                      <span className="font-semibold text-slate-300">Base Volume:</span> {selectedScore.metrics.total_transaction_count} transactions (₹{(selectedScore.metrics.total_transaction_volume / 100).toLocaleString(undefined, {minimumFractionDigits: 0})})
                    </div>
                  )}
                </div>

                {/* Factors */}
                <div className="space-y-4">
                  <h4 className="text-sm font-semibold text-slate-300 border-b border-slate-800 pb-2">Determinant Factors</h4>
                  
                  <div className="space-y-3">
                    {selectedScore.factors.map((factor, idx) => (
                      <div key={idx} className="flex gap-3 items-start bg-slate-900/40 p-3 rounded-lg border border-slate-800/40">
                        {factor.direction === "POSITIVE" ? (
                          <CheckCircle className="w-4 h-4 text-emerald-400 mt-0.5 shrink-0" />
                        ) : factor.direction === "NEGATIVE" ? (
                          <AlertCircle className="w-4 h-4 text-rose-400 mt-0.5 shrink-0" />
                        ) : (
                          <Activity className="w-4 h-4 text-slate-400 mt-0.5 shrink-0" />
                        )}
                        <div>
                          <div className="flex items-center gap-2 mb-1">
                            <span className="text-xs font-semibold text-slate-300">{factor.factor.replace(/_/g, ' ')}</span>
                            <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${
                              factor.contribution < 0 ? 'bg-rose-500/10 text-rose-400' :
                              factor.contribution > 0 ? 'bg-amber-500/10 text-amber-400' :
                              'bg-slate-500/10 text-slate-400'
                            }`}>
                              {factor.contribution > 0 ? '+' : ''}{factor.contribution} pts
                            </span>
                          </div>
                          <p className="text-xs text-slate-400">{factor.explanation}</p>
                        </div>
                      </div>
                    ))}
                    {selectedScore.factors.length === 0 && (
                      <div className="text-xs text-slate-500 italic">No determinant factors recorded.</div>
                    )}
                  </div>
                </div>

              </div>
            </>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center p-6 text-slate-500">
              <Building2 className="w-12 h-12 mb-4 opacity-20" />
              <p>Select a merchant from the list to view their Trust & Impact Score.</p>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

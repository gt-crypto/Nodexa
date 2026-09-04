"use client";

import React, { useState, useEffect } from "react";
import {
  Building2,
  Shield,
  AlertCircle,
  TrendingUp,
  RefreshCcw,
  CheckCircle,
  Activity,
  Search,
} from "lucide-react";
import { MerchantScore, fetchMerchantScores } from "../lib/api";
import { toSentenceCase } from "../lib/formatters";
import { Button } from "./ui/Button";
import { SectionHeading } from "./ui/SectionHeading";
import { StatusBadge } from "./ui/StatusBadge";

export function MerchantTrustScorePanel() {
  const [scores, setScores] = useState<MerchantScore[]>([]);
  const [selectedMerchantId, setSelectedMerchantId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>("");
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

  const selectedScore = scores.find(s => s.merchant_id === selectedMerchantId);

  return (
    <section id="merchants" className="w-full">
      <div className="rounded-xl p-5 sm:p-6 border border-slate-800/80 bg-[#0d121d] shadow-sm relative overflow-hidden">
        {/* Section Header */}
        <SectionHeading
          icon={<Building2 className="w-5 h-5 text-sky-400" />}
          title="Merchant Trust &amp; Impact Scorecards"
          badge={{
            text: "Tier-2 Merchant Intelligence",
            icon: <Shield className="w-3 h-3 text-sky-400" />,
            color: "bg-sky-950/30 border-sky-800/40 text-sky-300",
          }}
          description="Deterministic risk &amp; operational impact analytics for merchants participating in nodal transaction clearing."
        />

        {error && (
          <div className="p-3 rounded-lg bg-rose-950/30 border border-rose-800/40 text-rose-300 text-xs mb-5">
            {error}
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* Left: Merchant List */}
          <div className="border border-slate-800/80 bg-[#090d16] rounded-xl overflow-hidden flex flex-col h-[520px]">
            {/* Search and List Header */}
            <div className="p-3 border-b border-slate-800/80 bg-[#070a10] space-y-2">
              <div className="flex items-center justify-between gap-2">
                <h3 className="text-xs font-semibold text-slate-200 flex items-center gap-1.5 font-mono">
                  <Building2 className="w-3.5 h-3.5 text-sky-400 shrink-0" />
                  <span>Analyzed merchants ({scores.filter(s => s.merchant_id.toLowerCase().includes(searchQuery.toLowerCase())).length})</span>
                </h3>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={loadScores}
                  disabled={loading}
                  title="Refresh analyzed merchant scores"
                  aria-label="Refresh analyzed merchant scores"
                  icon={<RefreshCcw className={`w-3.5 h-3.5 ${loading ? "animate-spin text-sky-400" : ""}`} />}
                >
                  Refresh
                </Button>
              </div>
              <div className="relative">
                <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Filter merchants by ID..."
                  aria-label="Filter analyzed merchants by ID"
                  className="w-full h-8 pl-8 pr-2.5 text-xs font-mono bg-[#0d121d] border border-slate-800 rounded-lg text-slate-200 placeholder:text-slate-400 focus:outline-none focus:ring-1 focus:ring-sky-500/50 focus:border-sky-500/50"
                />
              </div>
            </div>
            
            {/* Scrollable Merchant List Container */}
            <div
              className="flex-1 overflow-y-auto p-2 space-y-1.5 sidebar-scrollbar"
              tabIndex={0}
              aria-label="Analyzed merchants scrollable list"
            >
              {loading && scores.length === 0 ? (
                <div className="p-4 text-center text-xs text-slate-400 font-mono">Loading merchant scores...</div>
              ) : scores.length === 0 ? (
                <div className="p-4 text-center text-xs text-slate-400 font-mono">No merchant activity found.</div>
              ) : (
                scores
                  .filter((s) => s.merchant_id.toLowerCase().includes(searchQuery.toLowerCase()))
                  .map((score) => (
                    <button
                      key={score.merchant_id}
                      onClick={() => setSelectedMerchantId(score.merchant_id)}
                      className={`w-full text-left p-2.5 rounded-lg border transition-colors cursor-pointer focus:outline-none ${
                        selectedMerchantId === score.merchant_id
                          ? "bg-sky-950/40 border-sky-800/60 shadow-sm"
                          : "bg-[#0d121d] border-slate-800/80 hover:border-slate-700"
                      }`}
                    >
                      <div className="flex justify-between items-start mb-1.5 gap-2">
                        <div className="min-w-0 flex-1">
                          <span className="text-[10px] font-mono text-slate-400 uppercase tracking-wider block">
                            Merchant ID
                          </span>
                          <span
                            className="font-mono text-xs font-medium text-white truncate block select-all"
                            title={score.merchant_id}
                          >
                            {score.merchant_id}
                          </span>
                        </div>
                        <StatusBadge status={score.score_band} size="sm" />
                      </div>
                      {/* Compact Grouped Metrics with Prominent Scores */}
                      <div className="grid grid-cols-2 gap-1.5 pt-1.5 border-t border-slate-800/60 font-mono">
                        <div className="bg-[#090d16] px-2 py-1 rounded border border-slate-800 flex flex-col justify-center">
                          <div className="flex items-center gap-1 text-[10px] text-slate-400 mb-0.5">
                            <Shield className="w-2.5 h-2.5 text-sky-400 shrink-0" />
                            <span>Trust</span>
                          </div>
                          <div className="text-xs font-bold text-white num-tabular">
                            {score.trust_score}<span className="text-[10px] text-slate-400 font-normal">/100</span>
                          </div>
                        </div>
                        <div className="bg-[#090d16] px-2 py-1 rounded border border-slate-800 flex flex-col justify-center">
                          <div className="flex items-center gap-1 text-[10px] text-slate-400 mb-0.5">
                            <TrendingUp className="w-2.5 h-2.5 text-amber-400 shrink-0" />
                            <span>Impact</span>
                          </div>
                          <div className="text-xs font-bold text-white num-tabular">
                            {score.impact_score}<span className="text-[10px] text-slate-400 font-normal">/100</span>
                          </div>
                        </div>
                      </div>
                    </button>
                  ))
              )}
            </div>
          </div>

          {/* Right: Selected Merchant Detail */}
          <div className="lg:col-span-2 border border-slate-800/80 bg-[#090d16] rounded-xl overflow-hidden flex flex-col h-[520px]">
            {selectedScore ? (
              <>
                {/* Header */}
                <div className="p-4 border-b border-slate-800/80 bg-[#070a10] flex flex-wrap justify-between items-center gap-3">
                  <div>
                    <span className="text-[10px] font-mono text-slate-400 block mb-0.5">Merchant profile</span>
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] font-mono text-slate-400 uppercase tracking-wider">ID:</span>
                      <h3
                        className="text-base font-bold text-white font-mono select-all truncate max-w-md"
                        title={selectedScore.merchant_id}
                      >
                        {selectedScore.merchant_id}
                      </h3>
                    </div>
                  </div>

                  <div className="flex gap-2.5">
                    {/* Trust Score Box */}
                    <div className="bg-[#0d121d] border border-slate-800 rounded-lg p-2.5 text-center min-w-[95px]">
                      <div className="text-xs font-medium text-slate-300 mb-0.5 font-mono">Trust score</div>
                      <div className="text-xl font-mono font-bold text-white mb-1 num-tabular">{selectedScore.trust_score}</div>
                      <StatusBadge status={selectedScore.score_band} size="sm" />
                    </div>

                    {/* Impact Score Box */}
                    <div className="bg-[#0d121d] border border-slate-800 rounded-lg p-2.5 text-center min-w-[95px]">
                      <div className="text-xs font-medium text-slate-300 mb-0.5 font-mono">Impact score</div>
                      <div className="text-xl font-mono font-bold text-amber-400 mb-1 num-tabular">{selectedScore.impact_score}</div>
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-950/30 border border-amber-800/40 text-amber-300 inline-flex items-center gap-1 font-mono font-medium">
                        <TrendingUp className="w-2.5 h-2.5 text-amber-400" />
                        Impact
                      </span>
                    </div>
                  </div>
                </div>

                {/* Body */}
                <div className="p-4 overflow-y-auto flex-1 grid grid-cols-1 md:grid-cols-2 gap-4 sidebar-scrollbar">
                  {/* Metrics */}
                  <div className="space-y-3">
                    <h3 className="text-xs font-semibold text-slate-200 border-b border-slate-800 pb-1.5 font-sans uppercase tracking-wider">
                      Operational metrics
                    </h3>
                    
                    <div className="grid grid-cols-2 gap-2">
                      <div className="bg-[#0d121d] rounded-lg p-3 border border-slate-800/80">
                        <div className="text-[11px] text-slate-400 mb-0.5 font-sans font-medium">Total exceptions</div>
                        <div className="text-base font-bold text-slate-200 financial-num">{selectedScore.metrics.exception_count}</div>
                      </div>
                      <div className="bg-[#0d121d] rounded-lg p-3 border border-slate-800/80">
                        <div className="text-[11px] text-slate-400 mb-0.5 font-sans font-medium">High-risk cases</div>
                        <div className="text-base font-bold text-rose-400 financial-num">{selectedScore.metrics.high_risk_exception_count}</div>
                      </div>
                      <div className="bg-[#0d121d] rounded-lg p-3 border border-slate-800/80">
                        <div className="text-[11px] text-slate-400 mb-0.5 font-sans font-medium">Pattern clusters</div>
                        <div className="text-base font-bold text-amber-400 financial-num">{selectedScore.metrics.recurring_pattern_count}</div>
                      </div>
                      <div className="bg-[#0d121d] rounded-lg p-3 border border-slate-800/80">
                        <div className="text-[11px] text-slate-400 mb-0.5 font-sans font-medium">Total exposure</div>
                        <div className="text-base font-bold text-emerald-400 financial-num">
                          ₹{(selectedScore.metrics.total_exposure / 100).toLocaleString("en-IN", {minimumFractionDigits: 2})}
                        </div>
                      </div>

                      {/* Integrated Base Volume Metric Card */}
                      {selectedScore.metrics.total_transaction_count > 0 && (
                        <div className="col-span-2 bg-[#0d121d] rounded-lg p-3 border border-slate-800/80 flex items-center justify-between">
                          <div>
                            <div className="text-[11px] text-slate-400 font-mono">Base volume</div>
                            <div className="text-xs font-mono text-slate-200 mt-0.5">
                              {selectedScore.metrics.total_transaction_count.toLocaleString("en-US")} transactions
                            </div>
                          </div>
                          <div className="text-right">
                            <div className="text-xs font-bold text-slate-100 font-mono num-tabular">
                              ₹{(selectedScore.metrics.total_transaction_volume / 100).toLocaleString("en-IN", {minimumFractionDigits: 2})}
                            </div>
                            <div className="text-[10px] text-slate-400 font-mono">Clearing volume</div>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Factors */}
                  <div className="space-y-3">
                    <h3 className="text-xs font-semibold text-slate-200 border-b border-slate-800 pb-1.5 font-mono uppercase tracking-wider">
                      Determinant factors
                    </h3>
                    
                    <div className="space-y-2">
                      {selectedScore.factors.map((factor, idx) => (
                        <div key={idx} className="flex gap-2.5 items-start bg-[#0d121d] p-2.5 rounded-lg border border-slate-800/80">
                          {factor.factor === "FINANCIAL_EXPOSURE" ? (
                            <Activity className="w-3.5 h-3.5 text-amber-400 mt-0.5 shrink-0" />
                          ) : factor.direction === "POSITIVE" ? (
                            <CheckCircle className="w-3.5 h-3.5 text-emerald-400 mt-0.5 shrink-0" />
                          ) : factor.direction === "NEGATIVE" ? (
                            <AlertCircle className="w-3.5 h-3.5 text-rose-400 mt-0.5 shrink-0" />
                          ) : (
                            <Activity className="w-3.5 h-3.5 text-slate-400 mt-0.5 shrink-0" />
                          )}
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-2 mb-0.5">
                              <span className="text-xs font-medium text-slate-200">{toSentenceCase(factor.factor)}</span>
                              <span className={`text-[10px] font-mono px-1.5 py-0.2 rounded ${
                                factor.contribution < 0 ? 'bg-rose-950/30 text-rose-400 border border-rose-900/40' :
                                factor.contribution > 0 ? 'bg-amber-950/30 text-amber-400 border border-amber-900/40' :
                                'bg-slate-800 text-slate-400 border border-slate-700'
                              }`}>
                                {factor.contribution > 0 ? '+' : ''}{factor.contribution} pts
                              </span>
                            </div>
                            <p className="text-[11px] text-slate-400 leading-relaxed">{factor.explanation}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </>
            ) : (
              <div className="p-8 text-center text-slate-400 flex flex-col items-center justify-center h-full font-mono text-xs">
                <Building2 className="w-8 h-8 text-slate-600 mb-2" />
                <p>Select a merchant from the list to view trust &amp; impact scorecard.</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

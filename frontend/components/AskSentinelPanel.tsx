"use client";

import React, { useState } from "react";
import {
  Sparkles,
  Search,
  ShieldAlert,
  CheckCircle,
  HelpCircle,
  AlertTriangle,
  FileText,
  Lock,
  ArrowRight,
  RefreshCw,
  Cpu,
} from "lucide-react";
import { CopilotAskResponse } from "../types";

const EXAMPLE_QUESTIONS = [
  "Why is this exception high risk?",
  "What happened to payment PAY-123?",
  "How much open exposure currently exists?",
  "Which exception families are currently unresolved?",
  "Show evidence for the latest ghost settlement exception.",
];

export function AskSentinelPanel() {
  const [question, setQuestion] = useState("");
  const [exceptionIdContext, setExceptionIdContext] = useState("");
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState<CopilotAskResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleAsk = async (promptText?: string) => {
    const qToSubmit = promptText || question;
    if (!qToSubmit.trim()) return;

    setLoading(true);
    setError(null);

    try {
      const res = await fetch("http://127.0.0.1:8000/copilot/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: qToSubmit,
          exception_id: exceptionIdContext.trim() || undefined,
        }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `Server error ${res.status}`);
      }

      const data: CopilotAskResponse = await res.json();
      setResponse(data);
      if (promptText) setQuestion(promptText);
    } catch (err: any) {
      setError(err.message || "Failed to query Ask Sentinel copilot.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="glass-panel rounded-2xl p-6 sm:p-8 border border-slate-800/80 shadow-2xl relative overflow-hidden">
      {/* Background Ambient Glow */}
      <div className="absolute -top-24 -right-24 w-72 h-72 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute -bottom-24 -left-24 w-72 h-72 bg-teal-500/10 rounded-full blur-3xl pointer-events-none" />

      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 mb-6 border-b border-slate-800/80 pb-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-gradient-to-br from-teal-500/20 to-cyan-500/20 border border-teal-500/30 text-teal-300">
            <Sparkles className="w-6 h-6 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-xl font-bold text-white tracking-tight">Ask Sentinel</h2>
              <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-teal-500/10 text-teal-300 border border-teal-500/30">
                v2.0 Grounded Copilot
              </span>
            </div>
            <p className="text-xs text-slate-400">
              Read-only natural language intelligence grounded in live operational evidence.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 text-xs font-mono px-3 py-1.5 rounded-lg bg-slate-900/80 border border-slate-800 text-slate-400">
          <Lock className="w-3.5 h-3.5 text-teal-400" />
          <span>Strict Read-Only Boundary Active</span>
        </div>
      </div>

      {/* Quick Example Prompt Chips */}
      <div className="mb-4">
        <label className="text-xs text-slate-400 font-mono mb-2 block flex items-center gap-1.5">
          <HelpCircle className="w-3.5 h-3.5 text-cyan-400" />
          Suggested Operator Questions:
        </label>
        <div className="flex flex-wrap gap-2">
          {EXAMPLE_QUESTIONS.map((prompt, idx) => (
            <button
              key={idx}
              onClick={() => handleAsk(prompt)}
              disabled={loading}
              className="text-xs px-3 py-1.5 rounded-lg bg-slate-900/60 hover:bg-slate-800/80 border border-slate-800 text-slate-300 hover:text-white transition-all text-left flex items-center gap-1.5 disabled:opacity-50"
            >
              <span>{prompt}</span>
              <ArrowRight className="w-3 h-3 text-slate-500 shrink-0" />
            </button>
          ))}
        </div>
      </div>

      {/* Query Input Area */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          handleAsk();
        }}
        className="space-y-4 mb-6"
      >
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-3.5" />
            <input
              type="text"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Ask Sentinel a question about exceptions, payments, settlements, or exposure..."
              className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-slate-950/80 border border-slate-800 text-white placeholder-slate-500 text-sm focus:outline-none focus:border-teal-500/50 transition-colors"
            />
          </div>

          <input
            type="text"
            value={exceptionIdContext}
            onChange={(e) => setExceptionIdContext(e.target.value)}
            placeholder="Context Exception ID (Optional)"
            className="sm:w-56 px-3.5 py-2.5 rounded-xl bg-slate-950/80 border border-slate-800 text-white placeholder-slate-500 text-xs font-mono focus:outline-none focus:border-teal-500/50 transition-colors"
          />

          <button
            type="submit"
            disabled={loading || !question.trim()}
            className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-teal-500 to-cyan-500 hover:from-teal-400 hover:to-cyan-400 text-slate-950 font-semibold text-sm transition-all flex items-center justify-center gap-2 disabled:opacity-50 shrink-0 shadow-lg shadow-teal-500/20"
          >
            {loading ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" />
                <span>Retrieving Evidence...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4" />
                <span>Ask Sentinel</span>
              </>
            )}
          </button>
        </div>
      </form>

      {/* Error Banner */}
      {error && (
        <div className="p-4 mb-6 rounded-xl bg-red-500/10 border border-red-500/30 text-red-300 text-xs flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 text-red-400 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Copilot Response Panel */}
      {response && (
        <div className="space-y-6 pt-4 border-t border-slate-800/80">
          {/* Header Metadata */}
          <div className="flex flex-wrap items-center justify-between gap-3 text-xs">
            <div className="flex items-center gap-2">
              <span className="text-slate-400">Query ID:</span>
              <code className="px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-teal-300 font-mono">
                {response.query_id}
              </code>
            </div>

            <div className="flex items-center gap-3">
              {/* Abstention Status */}
              {response.abstained ? (
                <span className="px-2.5 py-1 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-300 font-semibold text-[11px] flex items-center gap-1">
                  <ShieldAlert className="w-3.5 h-3.5" />
                  ABSTAINED (Insufficient / Out-of-Scope)
                </span>
              ) : (
                <span className="px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 font-semibold text-[11px] flex items-center gap-1">
                  <CheckCircle className="w-3.5 h-3.5" />
                  GROUNDED FACTUAL RESPONSE
                </span>
              )}

              {/* Confidence Indicator */}
              <span
                className={`px-2.5 py-1 rounded-full font-mono text-[11px] border ${
                  response.confidence === "HIGH"
                    ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
                    : response.confidence === "MEDIUM"
                    ? "bg-yellow-500/10 border-yellow-500/30 text-yellow-400"
                    : "bg-red-500/10 border-red-500/30 text-red-400"
                }`}
              >
                Confidence: {response.confidence}
              </span>
            </div>
          </div>

          {/* Answer Area */}
          <div className="p-5 rounded-xl bg-slate-950/70 border border-slate-800/80 space-y-3">
            <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
              <FileText className="w-3.5 h-3.5 text-teal-400" />
              Answer
            </h4>
            <div className="text-sm text-slate-200 leading-relaxed whitespace-pre-wrap font-sans">
              {response.answer}
            </div>
          </div>

          {/* Evidence References */}
          {response.evidence_refs && response.evidence_refs.length > 0 && (
            <div className="p-4 rounded-xl bg-slate-900/50 border border-slate-800/60 space-y-2">
              <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                <Cpu className="w-3.5 h-3.5 text-cyan-400" />
                Retrieved Factual Evidence Citations
              </h4>
              <div className="flex flex-wrap gap-2">
                {response.evidence_refs.map((ref, i) => (
                  <span
                    key={i}
                    className="px-2.5 py-1 rounded bg-slate-950 border border-slate-700 text-teal-300 font-mono text-xs shadow-sm"
                  >
                    {ref}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Reasoning & Limitations */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
            <div className="p-3.5 rounded-xl bg-slate-900/40 border border-slate-800/60">
              <span className="text-slate-400 block font-semibold mb-1">Evidence Reasoning:</span>
              <p className="text-slate-300 leading-relaxed">{response.reasoning}</p>
            </div>

            <div className="p-3.5 rounded-xl bg-slate-900/40 border border-slate-800/60">
              <span className="text-slate-400 block font-semibold mb-1">Operational Tools Executed:</span>
              <div className="flex flex-wrap gap-1.5 mt-1">
                {response.tools_used.length > 0 ? (
                  response.tools_used.map((t, idx) => (
                    <span key={idx} className="px-2 py-0.5 rounded bg-slate-800/80 text-slate-300 font-mono text-[10px]">
                      {t}
                    </span>
                  ))
                ) : (
                  <span className="text-slate-500 italic">None (Static Guard)</span>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

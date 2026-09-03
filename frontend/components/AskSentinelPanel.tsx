"use client";

import React, { useState } from "react";
import {
  Sparkles,
  Search,
  Lock,
  ArrowRight,
  CheckCircle2,
  FileText,
  Cpu,
  RefreshCw,
  HelpCircle,
  MessageSquare,
} from "lucide-react";
import { CopilotAskResponse } from "../types";
import { askCopilot } from "../lib/api";
import { Button } from "./ui/Button";
import { SectionHeading } from "./ui/SectionHeading";

const EXAMPLE_QUESTIONS = [
  "What is the status of EXC-GHOST-001?",
  "What recurring patterns exist in the exceptions?",
  "What financial exposure has Sentinel surfaced?",
  "What is the trust score for merchant ACME_CORP?",
  "Is nodal health deteriorating according to drift radar?",
];

export function AskSentinelPanel() {
  const [question, setQuestion] = useState("");
  const [exceptionIdContext, setExceptionIdContext] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [response, setResponse] = useState<CopilotAskResponse | null>(null);

  const handleAsk = async (customQ?: string) => {
    const qToAsk = customQ || question;
    if (!qToAsk.trim()) return;

    setLoading(true);
    setError(null);
    try {
      const data = await askCopilot({
        question: qToAsk,
        exception_id: exceptionIdContext.trim() || undefined,
        actor_id: "operations-copilot-ui",
      });
      setResponse(data);
      if (customQ) setQuestion(customQ);
    } catch (err: any) {
      setError(err.message || "Failed to query Ask Sentinel.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <section
      id="copilot"
      className="glass-panel rounded-2xl p-6 sm:p-8 border border-slate-800/80 shadow-2xl relative overflow-hidden"
    >
      {/* Background glow */}
      <div className="absolute -top-24 -right-24 w-72 h-72 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute -bottom-24 -left-24 w-72 h-72 bg-teal-500/10 rounded-full blur-3xl pointer-events-none" />

      {/* Header (Issue 3 & 14) */}
      <SectionHeading
        icon={<Sparkles className="w-6 h-6 text-teal-400" />}
        title="Ask Sentinel Grounded Copilot"
        badge={{
          text: "Tier-1 Copilot Active (v2.0)",
          icon: <MessageSquare className="w-3.5 h-3.5 text-teal-400" />,
          color: "bg-teal-500/10 border-teal-500/30 text-teal-300",
        }}
        description="Read-only natural language intelligence grounded in live operational evidence. Equipped with deterministic tool citations and zero LLM mutation rights."
        action={
          <div className="flex items-center gap-2 text-xs font-mono px-3 py-1.5 rounded-lg bg-slate-900/80 border border-slate-800 text-slate-400">
            <Lock className="w-3.5 h-3.5 text-teal-400" />
            <span>Strict read-only boundary active</span>
          </div>
        }
      />

      {/* Quick Example Prompt Chips */}
      <div className="mb-4">
        <label className="text-xs text-slate-400 font-mono mb-2 flex items-center gap-1.5 font-medium">
          <HelpCircle className="w-3.5 h-3.5 text-cyan-400" />
          <span>Suggested operator questions:</span>
        </label>
        <div className="flex flex-wrap gap-2">
          {EXAMPLE_QUESTIONS.map((prompt, idx) => (
            <button
              key={idx}
              onClick={() => handleAsk(prompt)}
              disabled={loading}
              className="text-xs px-3 py-1.5 rounded-lg bg-slate-900/60 hover:bg-slate-800/80 border border-slate-800 text-slate-300 hover:text-white transition-all text-left flex items-center gap-1.5 disabled:opacity-50 cursor-pointer"
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
            placeholder="Context ID (optional)"
            className="sm:w-48 px-3.5 py-2.5 rounded-xl bg-slate-950/80 border border-slate-800 text-white placeholder-slate-500 text-xs font-mono focus:outline-none focus:border-teal-500/50 transition-colors"
          />

          <Button
            type="submit"
            disabled={loading || !question.trim()}
            variant="primary"
            loading={loading}
            icon={<Sparkles className="w-4 h-4" />}
            className="shrink-0"
          >
            Ask Sentinel
          </Button>
        </div>
      </form>

      {/* Error state */}
      {error && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs font-mono mb-6">
          <p className="font-semibold mb-1">Copilot Query Error</p>
          <p>{error}</p>
        </div>
      )}

      {/* Response Display */}
      {response && (
        <div className="space-y-4 animate-in fade-in duration-200">
          {/* Status and Provenance Bar */}
          <div className="flex flex-wrap items-center justify-between gap-3 p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 text-xs font-mono">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-teal-400" />
              <span className="text-slate-300 font-semibold">Grounded synthesis</span>
              <span className="text-slate-500">| Query: {response.query_id}</span>
            </div>

            <div className="flex items-center gap-3">
              {/* Confidence Indicator */}
              <span
                className={`px-2.5 py-1 rounded-full font-mono text-xs font-medium border ${
                  response.confidence === "HIGH"
                    ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-300"
                    : response.confidence === "MEDIUM"
                    ? "bg-amber-500/10 border-amber-500/30 text-amber-300"
                    : "bg-rose-500/10 border-rose-500/30 text-rose-300"
                }`}
              >
                Confidence: {response.confidence}
              </span>
            </div>
          </div>

          {/* Answer Area (Issue 15: H3) */}
          <div className="p-5 rounded-xl bg-slate-950/70 border border-slate-800/80 space-y-3">
            <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5 font-mono">
              <FileText className="w-3.5 h-3.5 text-teal-400" />
              <span>Grounded answer</span>
            </h3>
            <div className="text-sm text-slate-200 leading-relaxed whitespace-pre-wrap font-sans">
              {response.answer}
            </div>
          </div>

          {/* Evidence References (Issue 15: H3) */}
          {response.evidence_refs && response.evidence_refs.length > 0 && (
            <div className="p-4 rounded-xl bg-slate-900/50 border border-slate-800/60 space-y-2">
              <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5 font-mono">
                <Cpu className="w-3.5 h-3.5 text-cyan-400" />
                <span>Retrieved factual evidence citations</span>
              </h3>
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
            <div className="p-4 rounded-xl bg-slate-900/40 border border-slate-800/60">
              <span className="text-slate-300 block font-semibold mb-1 font-mono">Evidence reasoning:</span>
              <p className="text-slate-300 leading-relaxed">{response.reasoning}</p>
            </div>

            <div className="p-4 rounded-xl bg-slate-900/40 border border-slate-800/60">
              <span className="text-slate-300 block font-semibold mb-1 font-mono">Operational tools executed:</span>
              <div className="flex flex-wrap gap-1.5 mt-1.5">
                {response.tools_used.length > 0 ? (
                  response.tools_used.map((t, idx) => (
                    <span key={idx} className="px-2 py-0.5 rounded bg-slate-800/80 text-slate-300 font-mono text-xs border border-slate-700/60">
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

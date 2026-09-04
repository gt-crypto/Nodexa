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
import { executeWithColdStartRetry } from "../lib/resilience";
import { ColdStartWakingCard } from "./ColdStartWakingCard";
import { Button } from "./ui/Button";
import { SectionHeading } from "./ui/SectionHeading";

const EXAMPLE_QUESTIONS = [
  "What is the status of EXC-GHOST-001?",
  "What recurring patterns exist in the exceptions?",
  "What financial exposure has Nodexa surfaced?",
  "What is the trust score for merchant ACME_CORP?",
  "Is nodal health deteriorating according to drift radar?",
];

export function AskSentinelPanel() {
  const [question, setQuestion] = useState("");
  const [exceptionIdContext, setExceptionIdContext] = useState("");
  const [loading, setLoading] = useState(false);
  const [wakingState, setWakingState] = useState<{ attempt: number; isTimeout: boolean } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [response, setResponse] = useState<CopilotAskResponse | null>(null);

  const handleAsk = async (customQ?: string) => {
    const qToAsk = customQ || question;
    if (!qToAsk.trim()) return;

    setLoading(true);
    setError(null);
    setWakingState(null);
    try {
      const data = await executeWithColdStartRetry(
        () =>
          askCopilot({
            question: qToAsk,
            exception_id: exceptionIdContext.trim() || undefined,
            actor_id: "operations-copilot-ui",
          }),
        {
          onWaking: (attempt) => setWakingState({ attempt, isTimeout: false }),
          onRecovered: () => setWakingState(null),
        }
      );
      setResponse(data);
      if (customQ) setQuestion(customQ);
      setWakingState(null);
    } catch (err: any) {
      if (wakingState && wakingState.attempt >= 6) {
        setWakingState({ attempt: 6, isTimeout: true });
      } else {
        setError(err.message || "Failed to query Ask Nodexa.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <section
      id="copilot"
      className="rounded-xl p-5 sm:p-6 border border-slate-800/80 bg-[#0d121d] shadow-sm relative overflow-hidden"
    >
      {/* Header */}
      <SectionHeading
        icon={<Sparkles className="w-5 h-5 text-sky-400" />}
        title="Ask Nodexa Grounded Copilot"
        badge={{
          text: "Tier-1 Copilot Active (v2.0)",
          icon: <MessageSquare className="w-3 h-3 text-sky-400" />,
          color: "bg-sky-950/30 border-sky-800/40 text-sky-300",
        }}
        description="Read-only natural language intelligence grounded in live operational evidence. Equipped with deterministic tool citations and zero LLM mutation rights."
        action={
          <div className="flex items-center gap-1.5 text-xs font-mono px-2.5 py-1 rounded bg-[#090d16] border border-slate-800 text-slate-400">
            <Lock className="w-3 h-3 text-sky-400" />
            <span>Strict read-only boundary</span>
          </div>
        }
      />

      {/* Quick Example Prompt Chips */}
      <div className="mb-4">
        <label className="text-[11px] text-slate-400 font-sans mb-1.5 flex items-center gap-1.5 font-medium">
          <HelpCircle className="w-3 h-3 text-sky-400" />
          <span>Suggested operator queries:</span>
        </label>
        <div className="flex flex-wrap gap-1.5">
          {EXAMPLE_QUESTIONS.map((prompt, idx) => (
            <button
              key={idx}
              onClick={() => handleAsk(prompt)}
              disabled={loading}
              className="text-[11px] px-2.5 py-1 rounded bg-[#090d16] hover:bg-[#111726] border border-slate-800 text-slate-300 hover:text-white transition-colors text-left flex items-center gap-1.5 disabled:opacity-50 cursor-pointer font-sans"
            >
              <span>{prompt}</span>
              <ArrowRight className="w-2.5 h-2.5 text-slate-500 shrink-0" />
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
        className="space-y-3 mb-5"
      >
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2">
          <div className="relative flex-1">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
            <input
              type="text"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Ask Nodexa a question about exceptions, payments, settlements, or exposure..."
              className="w-full pl-9 pr-3 h-9 rounded-lg bg-[#090d16] border border-slate-700/80 text-white placeholder-slate-400 text-xs focus:outline-none focus:border-sky-500 focus:ring-1 focus:ring-sky-500 transition-colors"
            />
          </div>

          <div className="sm:w-44 shrink-0">
            <input
              type="text"
              value={exceptionIdContext}
              onChange={(e) => setExceptionIdContext(e.target.value)}
              placeholder="Context ID (optional)"
              className="w-full px-3 h-9 rounded-lg bg-[#090d16] border border-slate-700/80 text-white placeholder-slate-400 text-xs font-mono focus:outline-none focus:border-sky-500 focus:ring-1 focus:ring-sky-500 transition-colors"
            />
          </div>

          <Button
            type="submit"
            disabled={loading || !question.trim()}
            variant="primary"
            loading={loading}
            icon={<Sparkles className="w-3.5 h-3.5" />}
            size="md"
            className="shrink-0"
          >
            Ask Nodexa
          </Button>
        </div>
      </form>

      {/* Error / Waking state */}
      {wakingState ? (
        <div className="mb-5">
          <ColdStartWakingCard
            attempt={wakingState.attempt}
            maxAttempts={6}
            isTimeout={wakingState.isTimeout}
            onRetry={() => handleAsk()}
            description="Connecting to Grounded Copilot Engine…"
            compact
          />
        </div>
      ) : error ? (
        <div className="p-3 rounded-lg bg-rose-950/30 border border-rose-800/40 text-rose-300 text-xs font-mono mb-5">
          <p className="font-semibold mb-0.5">Copilot Query Error</p>
          <p>{error}</p>
        </div>
      ) : null}

      {/* Response Display */}
      {response && (
        <div className="space-y-3 animate-in fade-in duration-150">
          {/* Status and Provenance Bar */}
          <div className="flex flex-wrap items-center justify-between gap-2 p-2.5 rounded-lg bg-[#090d16] border border-slate-800 text-xs font-mono">
            <div className="flex items-center gap-1.5">
              <CheckCircle2 className="w-3.5 h-3.5 text-sky-400" />
              <span className="text-slate-300 font-medium">Grounded Synthesis</span>
              <span className="text-slate-500">| Query: {response.query_id}</span>
            </div>

            <div className="flex items-center gap-2">
              <span
                className={`px-2 py-0.5 rounded font-mono text-[11px] font-medium border ${
                  response.confidence === "HIGH"
                    ? "bg-emerald-950/30 border-emerald-800/40 text-emerald-300"
                    : response.confidence === "MEDIUM"
                    ? "bg-amber-950/30 border-amber-800/40 text-amber-300"
                    : "bg-rose-950/30 border-rose-800/40 text-rose-300"
                }`}
              >
                Confidence: {response.confidence}
              </span>
            </div>
          </div>

          {/* Answer Area */}
          <div className="p-4 rounded-lg bg-[#090d16] border border-slate-800/80 space-y-2">
            <h3 className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5 font-mono">
              <FileText className="w-3 h-3 text-sky-400" />
              <span>Grounded Answer</span>
            </h3>
            <div className="text-xs text-slate-200 leading-relaxed whitespace-pre-wrap font-sans">
              {response.answer}
            </div>
          </div>

          {/* Evidence References */}
          {response.evidence_refs && response.evidence_refs.length > 0 && (
            <div className="p-3 rounded-lg bg-[#090d16] border border-slate-800/80 space-y-1.5">
              <h3 className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5 font-mono">
                <Cpu className="w-3 h-3 text-sky-400" />
                <span>Retrieved Factual Evidence Citations</span>
              </h3>
              <div className="flex flex-wrap gap-1.5">
                {response.evidence_refs.map((ref, i) => (
                  <span
                    key={i}
                    className="px-2 py-0.5 rounded bg-[#0d121d] border border-slate-700 text-sky-300 font-mono text-xs"
                  >
                    {ref}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Reasoning & Limitations */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
            <div className="p-3 rounded-lg bg-[#090d16] border border-slate-800/80">
              <span className="text-slate-300 block font-medium mb-0.5 font-mono text-[11px]">Evidence Reasoning:</span>
              <p className="text-slate-400 leading-relaxed text-xs">{response.reasoning}</p>
            </div>

            <div className="p-3 rounded-lg bg-[#090d16] border border-slate-800/80">
              <span className="text-slate-300 block font-medium mb-0.5 font-mono text-[11px]">Operational Tools Executed:</span>
              <div className="flex flex-wrap gap-1 mt-1">
                {response.tools_used.length > 0 ? (
                  response.tools_used.map((t, idx) => (
                    <span key={idx} className="px-1.5 py-0.5 rounded bg-[#0d121d] text-slate-300 font-mono text-[10px] border border-slate-700">
                      {t}
                    </span>
                  ))
                ) : (
                  <span className="text-slate-500 italic text-xs">None (Static Guard)</span>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

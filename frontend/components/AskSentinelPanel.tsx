"use client";

import React, { useState } from "react";
import {
  Sparkles,
  Search,
  MessageSquare,
  Lock,
  CheckCircle2,
  FileText,
  Cpu,
  ArrowRight,
  HelpCircle,
} from "lucide-react";
import { AskSentinelResponse } from "../types";
import { askSentinelCopilot } from "../lib/api";
import { executeWithColdStartRetry } from "../lib/resilience";
import { ColdStartWakingCard } from "./ColdStartWakingCard";
import { Button } from "./ui/Button";
import { SectionHeading } from "./ui/SectionHeading";

const EXAMPLE_QUESTIONS = [
  "Explain why settlement SET-000014 is unallocated.",
  "Which merchants currently have anomalous settlement discrepancies?",
  "What is the total financial risk exposure identified across all exceptions?",
  "Why was payment PAY-000001 flagged as a ghost settlement?",
];

export function AskSentinelPanel() {
  const [question, setQuestion] = useState("");
  const [exceptionIdContext, setExceptionIdContext] = useState("");
  const [response, setResponse] = useState<AskSentinelResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [wakingState, setWakingState] = useState<{ attempt: number; isTimeout: boolean } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleAsk = async (customQ?: string) => {
    const qToAsk = customQ || question;
    if (!qToAsk.trim()) return;

    setLoading(true);
    setError(null);
    try {
      const data = await executeWithColdStartRetry(
        () =>
          askSentinelCopilot({
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
      className="rounded-xl p-5 sm:p-6 border border-slate-200 bg-white shadow-xs relative overflow-hidden"
    >
      {/* Header */}
      <SectionHeading
        icon={<Sparkles className="w-5 h-5 text-indigo-600" />}
        title="Ask Nodexa Grounded Copilot"
        badge={{
          text: "Tier-1 Copilot Active",
          icon: <MessageSquare className="w-3 h-3 text-indigo-600" />,
          color: "bg-indigo-50 border-indigo-200 text-indigo-700",
        }}
        description="Read-only natural language intelligence grounded in live operational evidence. Equipped with deterministic tool citations and zero LLM mutation rights."
        action={
          <div className="flex items-center gap-1.5 text-xs font-mono px-2.5 py-1 rounded bg-slate-50 border border-slate-200 text-slate-600">
            <Lock className="w-3 h-3 text-indigo-600" />
            <span>Strict read-only boundary</span>
          </div>
        }
      />

      {/* Quick Example Prompt Chips */}
      <div className="mb-4">
        <label className="text-[11px] text-slate-500 font-sans mb-1.5 flex items-center gap-1.5 font-medium">
          <HelpCircle className="w-3 h-3 text-indigo-600" />
          <span>Suggested operator queries:</span>
        </label>
        <div className="flex flex-wrap gap-1.5">
          {EXAMPLE_QUESTIONS.map((prompt, idx) => (
            <button
              key={idx}
              onClick={() => handleAsk(prompt)}
              disabled={loading}
              className="text-[11px] px-2.5 py-1 rounded-md bg-slate-50 hover:bg-indigo-50 border border-slate-200 text-slate-700 hover:text-indigo-900 transition-colors text-left flex items-center gap-1.5 disabled:opacity-50 cursor-pointer font-sans"
            >
              <span>{prompt}</span>
              <ArrowRight className="w-2.5 h-2.5 text-slate-400 shrink-0" />
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
              className="w-full pl-9 pr-3 h-9 rounded-lg bg-white border border-slate-200 text-slate-900 placeholder-slate-400 text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition-colors"
            />
          </div>

          <div className="sm:w-44 shrink-0">
            <input
              type="text"
              value={exceptionIdContext}
              onChange={(e) => setExceptionIdContext(e.target.value)}
              placeholder="Context ID (optional)"
              className="w-full px-3 h-9 rounded-lg bg-white border border-slate-200 text-slate-900 placeholder-slate-400 text-xs font-mono focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition-colors"
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
        <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 text-xs font-mono mb-5">
          <p className="font-semibold mb-0.5">Copilot Query Error</p>
          <p>{error}</p>
        </div>
      ) : null}

      {/* Response Display */}
      {response && (
        <div className="space-y-3 animate-in fade-in duration-150">
          {/* Status and Provenance Bar */}
          <div className="flex flex-wrap items-center justify-between gap-2 p-2.5 rounded-lg bg-slate-50 border border-slate-200 text-xs font-mono">
            <div className="flex items-center gap-1.5">
              <CheckCircle2 className="w-3.5 h-3.5 text-indigo-600" />
              <span className="text-slate-900 font-semibold">Grounded Synthesis</span>
              <span className="text-slate-400">| Query: {response.query_id}</span>
            </div>

            <div className="flex items-center gap-2">
              <span
                className={`px-2 py-0.5 rounded font-mono text-[11px] font-semibold border ${
                  response.confidence === "HIGH"
                    ? "bg-[#ECFDF3] border-emerald-200 text-[#15803D]"
                    : response.confidence === "MEDIUM"
                    ? "bg-[#FFFBEB] border-amber-200 text-[#B45309]"
                    : "bg-[#FEF2F2] border-rose-200 text-[#DC2626]"
                }`}
              >
                Confidence: {response.confidence}
              </span>
            </div>
          </div>

          {/* Answer Area */}
          <div className="p-4 rounded-lg bg-slate-50/70 border border-slate-200 space-y-2">
            <h3 className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1.5 font-mono">
              <FileText className="w-3.5 h-3.5 text-indigo-600" />
              <span>Grounded Answer</span>
            </h3>
            <div className="text-xs text-slate-800 leading-relaxed whitespace-pre-wrap font-sans">
              {response.answer}
            </div>
          </div>

          {/* Evidence References */}
          {response.evidence_refs && response.evidence_refs.length > 0 && (
            <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 space-y-1.5">
              <h3 className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1.5 font-mono">
                <Cpu className="w-3.5 h-3.5 text-indigo-600" />
                <span>Retrieved Factual Evidence Citations</span>
              </h3>
              <div className="flex flex-wrap gap-1.5">
                {response.evidence_refs.map((ref, i) => (
                  <span
                    key={i}
                    className="px-2 py-0.5 rounded bg-white border border-slate-200 text-indigo-700 font-mono text-xs font-medium"
                  >
                    {ref}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Reasoning & Limitations */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
            <div className="p-3 rounded-lg bg-slate-50 border border-slate-200">
              <span className="text-slate-700 block font-semibold mb-0.5 font-mono text-[11px]">Evidence Reasoning:</span>
              <p className="text-slate-500 leading-relaxed text-xs">{response.reasoning}</p>
            </div>

            <div className="p-3 rounded-lg bg-slate-50 border border-slate-200">
              <span className="text-slate-700 block font-semibold mb-0.5 font-mono text-[11px]">Operational Tools Executed:</span>
              <div className="flex flex-wrap gap-1 mt-1">
                {response.tools_used.length > 0 ? (
                  response.tools_used.map((t, idx) => (
                    <span key={idx} className="px-1.5 py-0.5 rounded bg-white text-slate-700 font-mono text-[10px] border border-slate-200 font-medium">
                      {t}
                    </span>
                  ))
                ) : (
                  <span className="text-slate-400 italic text-xs">None (Static Guard)</span>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

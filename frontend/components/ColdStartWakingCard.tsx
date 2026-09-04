"use client";

import React from "react";
import { NodexaMark } from "./brand/NodexaLogo";
import { RefreshCw, Radio, Server, ShieldCheck, AlertCircle } from "lucide-react";
import { Button } from "./ui/Button";

export interface ColdStartWakingCardProps {
  /** Current attempt number (1-indexed) */
  attempt?: number;
  /** Max retry attempts */
  maxAttempts?: number;
  /** If retry attempts exhausted */
  isTimeout?: boolean;
  /** Callback for manual retry button */
  onRetry?: () => void;
  /** Optional custom title */
  title?: string;
  /** Optional custom description */
  description?: string;
  /** Compact card style for nested panels vs full block */
  compact?: boolean;
}

/**
 * Professional fintech cold-start loading & waking indicator.
 * Shown when Render's free tier is waking up from inactivity.
 * Replaces unsightly "Failed to fetch" with clear, reassuring operational context.
 */
export const ColdStartWakingCard: React.FC<ColdStartWakingCardProps> = ({
  attempt = 1,
  maxAttempts = 6,
  isTimeout = false,
  onRetry,
  title = "Connecting to Nodexa",
  description = "Waking the Finance Controller…",
  compact = false,
}) => {
  if (isTimeout) {
    return (
      <div
        className={`rounded-xl border border-amber-800/40 bg-[#0d121d] text-center relative overflow-hidden ${
          compact ? "p-4 sm:p-5" : "p-6 sm:p-8"
        }`}
      >
        <div className="max-w-md mx-auto flex flex-col items-center gap-3">
          <div className="p-3 rounded-full bg-amber-950/40 border border-amber-800/50 text-amber-400">
            <AlertCircle className="w-6 h-6" />
          </div>

          <div>
            <h3 className="text-base font-bold text-white font-sans">
              Nodexa is taking longer than expected
            </h3>
            <p className="text-xs text-slate-400 mt-1 leading-relaxed">
              The Finance Controller container is still initializing or networking is congested. Please retry in a moment.
            </p>
          </div>

          {onRetry && (
            <div className="pt-2">
              <Button
                variant="primary"
                size="sm"
                onClick={onRetry}
                icon={<RefreshCw className="w-3.5 h-3.5" />}
              >
                Retry connection
              </Button>
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div
      className={`rounded-xl border border-sky-800/30 bg-[#0d121d] relative overflow-hidden text-center shadow-lg ${
        compact ? "p-5 sm:p-6" : "p-8 sm:p-10"
      }`}
    >
      {/* Background ambient glow */}
      <div className="absolute inset-0 bg-gradient-to-b from-sky-950/20 via-transparent to-transparent pointer-events-none" />

      <div className="max-w-md mx-auto flex flex-col items-center gap-3.5 relative z-10">
        {/* Brand mark with heartbeat pulse */}
        <div className="relative">
          <div className="absolute -inset-2 bg-sky-500/10 rounded-full blur-md animate-pulse" />
          <NodexaMark size={36} className="relative z-10 animate-pulse" />
        </div>

        {/* Status badge */}
        <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-sky-950/50 border border-sky-800/50 text-sky-300 text-[11px] font-mono">
          <span className="w-1.5 h-1.5 rounded-full bg-sky-400 animate-ping" />
          <span>Connecting securely &bull; Attempt {attempt} of {maxAttempts}</span>
        </div>

        {/* Heading & Subheading */}
        <div>
          <h3 className="text-base sm:text-lg font-bold text-white tracking-tight font-sans">
            {description}
          </h3>
          <p className="text-xs text-slate-400 mt-1 leading-relaxed font-sans">
            Reconnecting to the finance operations engine.
          </p>
        </div>

        {/* Animated connection bar indicator */}
        <div className="w-48 h-1.5 bg-slate-800 rounded-full overflow-hidden mt-1 relative">
          <div className="h-full bg-gradient-to-r from-sky-500 via-cyan-400 to-sky-500 rounded-full animate-pulse w-full" />
        </div>

        {/* Footnote note */}
        <p className="text-[11px] text-slate-500 font-sans mt-1">
          This may take up to a minute on the free infrastructure tier.
        </p>
      </div>
    </div>
  );
};

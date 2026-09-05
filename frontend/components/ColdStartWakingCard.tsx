"use client";

import React from "react";
import { NodexaMark } from "./brand/NodexaLogo";
import { RefreshCw, AlertCircle } from "lucide-react";
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
        className={`rounded-xl border border-amber-200 bg-amber-50/40 text-center relative overflow-hidden ${
          compact ? "p-4 sm:p-5" : "p-6 sm:p-8"
        }`}
      >
        <div className="max-w-md mx-auto flex flex-col items-center gap-3">
          <div className="p-3 rounded-full bg-amber-100 border border-amber-200 text-amber-700">
            <AlertCircle className="w-6 h-6" />
          </div>

          <div>
            <h3 className="text-base font-bold text-slate-900 font-sans">
              Nodexa is taking longer than expected
            </h3>
            <p className="text-xs text-slate-600 mt-1 leading-relaxed">
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
      className={`rounded-xl border border-slate-200 bg-white relative overflow-hidden text-center shadow-sm ${
        compact ? "p-5 sm:p-6" : "p-8 sm:p-10"
      }`}
    >
      <div className="max-w-md mx-auto flex flex-col items-center gap-3.5 relative z-10">
        {/* Brand mark with heartbeat pulse */}
        <div className="relative">
          <div className="absolute -inset-2 bg-indigo-500/10 rounded-full blur-md animate-pulse" />
          <NodexaMark size={36} className="relative z-10 animate-pulse" />
        </div>

        {/* Status badge */}
        <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-indigo-50 border border-indigo-200 text-indigo-700 text-[11px] font-mono font-medium">
          <span className="w-1.5 h-1.5 rounded-full bg-indigo-500 animate-ping" />
          <span>Connecting securely &bull; Attempt {attempt} of {maxAttempts}</span>
        </div>

        {/* Heading & Subheading */}
        <div>
          <h3 className="text-base font-bold text-slate-900 font-sans tracking-tight">
            {title}
          </h3>
          <p className="text-xs text-slate-500 mt-1 leading-relaxed">
            {description}
          </p>
        </div>

        {/* Informational reassurance */}
        <div className="w-full pt-3 border-t border-slate-100 flex items-center justify-center gap-4 text-[11px] text-slate-400 font-mono">
          <span>PostgreSQL Live</span>
          <span>&bull;</span>
          <span>Dual-Engine Verification</span>
        </div>
      </div>
    </div>
  );
};

"use client";

import React, { useEffect } from "react";
import Link from "next/link";
import { AlertTriangle, RefreshCw, Home } from "lucide-react";
import { Button } from "../components/ui/Button";

interface ErrorProps {
  error: Error & { digest?: string };
  reset: () => void;
}

export default function GlobalError({ error, reset }: ErrorProps) {
  useEffect(() => {
    // Log unexpected frontend errors with correlation
    console.error("[Nodexa Application Error Boundary]", error);
  }, [error]);

  return (
    <div className="min-h-[60vh] flex items-center justify-center p-4">
      <div className="max-w-md w-full rounded-xl bg-[#090d16] border border-slate-800/80 p-6 sm:p-8 shadow-lg text-center space-y-5">
        <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-rose-950/40 border border-rose-800/50 text-rose-400 mx-auto">
          <AlertTriangle className="w-6 h-6" />
        </div>

        <div className="space-y-2">
          <h2 className="text-lg font-semibold text-white font-sans tracking-tight">
            Something went wrong
          </h2>
          <p className="text-xs text-slate-400 font-sans leading-relaxed">
            We couldn&apos;t complete that request. Please try again or return to the main dashboard.
          </p>
        </div>

        {error?.digest && (
          <div className="px-3 py-1.5 rounded bg-[#0d121d] border border-slate-800 text-[11px] font-mono text-slate-500">
            Error Ref: {error.digest}
          </div>
        )}

        <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
          <Button
            variant="primary"
            size="sm"
            onClick={() => reset()}
            icon={<RefreshCw className="w-3.5 h-3.5" />}
          >
            Try again
          </Button>

          <Link href="/" className="w-full sm:w-auto">
            <Button
              variant="secondary"
              size="sm"
              className="w-full sm:w-auto"
              icon={<Home className="w-3.5 h-3.5" />}
            >
              Return to Overview
            </Button>
          </Link>
        </div>
      </div>
    </div>
  );
}

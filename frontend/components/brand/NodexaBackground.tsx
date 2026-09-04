"use client";

import React, { useMemo } from "react";
import { usePathname } from "next/navigation";

interface NodexaBackgroundProps {
  /**
   * Optional manual override for the variant.
   * If not specified, the variant is inferred from the active pathname.
   */
  variant?: "command" | "copilot" | "patterns" | "drift" | "verifier" | "benchmark" | "architecture" | "login" | "default";
  className?: string;
}

export const NodexaBackground: React.FC<NodexaBackgroundProps> = ({
  variant: manualVariant,
  className = "",
}) => {
  const pathname = usePathname();

  const activeVariant = useMemo(() => {
    if (manualVariant) return manualVariant;
    if (!pathname || pathname === "/") return "command";
    if (pathname.startsWith("/copilot")) return "copilot";
    if (pathname.startsWith("/patterns")) return "patterns";
    if (pathname.startsWith("/drift-radar")) return "drift";
    if (pathname.startsWith("/verifier") || pathname.startsWith("/escalations")) return "verifier";
    if (pathname.startsWith("/benchmark")) return "benchmark";
    if (pathname.startsWith("/architecture")) return "architecture";
    if (pathname.startsWith("/login")) return "login";
    return "default";
  }, [manualVariant, pathname]);

  return (
    <div
      aria-hidden="true"
      className={`fixed inset-0 pointer-events-none overflow-hidden z-0 select-none ${className}`}
      style={{ isolation: "isolate" }}
    >
      {/* ── Base Atmospheric Layer: Near-Black Fintech Canvas ───────────────────────── */}
      <div className="absolute inset-0 bg-[#080b11]" />

      {/* ── Layer 1: Ambient Financial Vignettes (Extremely restrained) ─────────────── */}
      <div
        className="absolute inset-0 opacity-40 transition-opacity duration-700"
        style={{
          backgroundImage: `
            radial-gradient(circle at 15% 15%, rgba(14, 165, 233, 0.04) 0%, transparent 45%),
            radial-gradient(circle at 85% 25%, rgba(2, 132, 199, 0.03) 0%, transparent 50%),
            radial-gradient(circle at 50% 85%, rgba(30, 41, 59, 0.2) 0%, transparent 60%)
          `,
        }}
      />

      {/* ── Layer 2: Subtle Financial Grid Texture (32px * 32px) ────────────────────── */}
      <svg
        className="absolute inset-0 w-full h-full opacity-[0.025]"
        xmlns="http://www.w3.org/2000/svg"
      >
        <defs>
          <pattern
            id="nodexa-base-grid"
            width="48"
            height="48"
            patternUnits="userSpaceOnUse"
          >
            <path
              d="M 48 0 L 0 0 0 48"
              fill="none"
              stroke="#ffffff"
              strokeWidth="0.75"
            />
            <circle cx="48" cy="48" r="0.75" fill="#ffffff" opacity="0.3" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#nodexa-base-grid)" />
      </svg>

      {/* ── Layer 3: Contextual Financial Topology Network (Dynamic by Route) ────────── */}
      <svg
        className="absolute inset-0 w-full h-full opacity-[0.22] transition-all duration-700 nodexa-network-svg"
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 1600 900"
        preserveAspectRatio="xMidYMid slice"
      >
        <defs>
          {/* Subtle Linear Gradients for Transaction Pathways */}
          <linearGradient id="flow-line-sky" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#0284c7" stopOpacity="0.1" />
            <stop offset="50%" stopColor="#38bdf8" stopOpacity="0.5" />
            <stop offset="100%" stopColor="#0284c7" stopOpacity="0.1" />
          </linearGradient>

          <linearGradient id="flow-line-cyan" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor="#06b6d4" stopOpacity="0.1" />
            <stop offset="60%" stopColor="#22d3ee" stopOpacity="0.4" />
            <stop offset="100%" stopColor="#06b6d4" stopOpacity="0.05" />
          </linearGradient>

          <linearGradient id="flow-line-slate" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#334155" stopOpacity="0.25" />
            <stop offset="100%" stopColor="#1e293b" stopOpacity="0.1" />
          </linearGradient>

          {/* Node Glow Filters */}
          <filter id="subtle-glow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="2" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>
        </defs>

        {/* ── Global Backbone Lines: Persistent Ledger Conduits ────────────────────── */}
        <g stroke="#334155" strokeWidth="0.75" fill="none" opacity="0.6">
          {/* Horizon Bus Line */}
          <line x1="80" y1="180" x2="1520" y2="180" strokeDasharray="3 6" opacity="0.3" />
          <line x1="80" y1="460" x2="1520" y2="460" strokeDasharray="2 8" opacity="0.25" />
          <line x1="80" y1="740" x2="1520" y2="740" strokeDasharray="4 10" opacity="0.2" />

          {/* Vertical Channel Stems */}
          <line x1="360" y1="60" x2="360" y2="840" strokeDasharray="4 8" opacity="0.2" />
          <line x1="800" y1="60" x2="800" y2="840" strokeDasharray="2 6" opacity="0.15" />
          <line x1="1240" y1="60" x2="1240" y2="840" strokeDasharray="4 8" opacity="0.2" />
        </g>

        {/* ── Persistent Financial Flow Arteries (Orthogonal Routing) ──────────────── */}
        <g fill="none" strokeWidth="1">
          {/* Main Transaction Arteries with subtle dash pulse */}
          <path
            d="M 160 220 L 360 220 L 360 380 L 580 380 L 640 440 L 920 440 L 920 280 L 1140 280 L 1240 380 L 1440 380"
            stroke="url(#flow-line-sky)"
            strokeDasharray="8 12"
            className="nodexa-path-flow"
          />
          <path
            d="M 240 680 L 460 680 L 460 520 L 720 520 L 800 600 L 1080 600 L 1080 720 L 1380 720"
            stroke="url(#flow-line-slate)"
            strokeDasharray="6 10"
          />
          <path
            d="M 580 120 L 580 260 L 760 260 L 800 300 L 800 500 L 960 500 L 960 660 L 1180 660"
            stroke="url(#flow-line-cyan)"
            strokeDasharray="4 8"
            className="nodexa-path-flow-slow"
          />
        </g>

        {/* ── Persistent Financial Pathway Nodes (Small precision vertices) ───────── */}
        <g fill="#0ea5e9" opacity="0.75">
          {/* Primary Junction Nodes */}
          <circle cx="360" cy="220" r="2.5" />
          <circle cx="360" cy="380" r="2" />
          <circle cx="580" cy="380" r="2" />
          <circle cx="640" cy="440" r="2.5" fill="#38bdf8" filter="url(#subtle-glow)" className="nodexa-node-pulse" />
          <circle cx="920" cy="440" r="2" />
          <circle cx="920" cy="280" r="2.5" />
          <circle cx="1140" cy="280" r="2" />
          <circle cx="1240" cy="380" r="3" fill="#38bdf8" filter="url(#subtle-glow)" />

          {/* Lower Sub-Ledger Nodes */}
          <circle cx="460" cy="680" r="2" fill="#64748b" />
          <circle cx="460" cy="520" r="2" fill="#64748b" />
          <circle cx="720" cy="520" r="2" fill="#64748b" />
          <circle cx="800" cy="600" r="2.5" fill="#0ea5e9" />
          <circle cx="1080" cy="600" r="2" fill="#64748b" />
          <circle cx="1080" cy="720" r="2" fill="#64748b" />
        </g>

        {/* ── Variant-Specific Contextual Geometries ───────────────────────────────── */}
        {/* 1. Command Center / Default: Central settlement hub geometry */}
        {(activeVariant === "command" || activeVariant === "default") && (
          <g className="nodexa-variant-group" opacity="0.6">
            <rect
              x="740"
              y="380"
              width="120"
              height="120"
              fill="none"
              stroke="#0284c7"
              strokeWidth="0.75"
              strokeDasharray="4 6"
              opacity="0.4"
            />
            <circle cx="800" cy="440" r="4" fill="#0284c7" opacity="0.4" filter="url(#subtle-glow)" />
            <circle cx="800" cy="440" r="1.5" fill="#e0f2fe" />
            <path d="M 720 440 L 740 440 M 860 440 L 880 440" stroke="#0ea5e9" strokeWidth="1" />
            <path d="M 800 360 L 800 380 M 800 500 L 800 520" stroke="#0ea5e9" strokeWidth="1" />
          </g>
        )}

        {/* 2. Copilot: Evidence reasoning graph */}
        {activeVariant === "copilot" && (
          <g className="nodexa-variant-group" opacity="0.65">
            <path
              d="M 680 320 L 760 280 L 840 320 L 840 420 L 760 460 L 680 420 Z"
              fill="none"
              stroke="#06b6d4"
              strokeWidth="0.85"
              strokeDasharray="3 4"
            />
            <line x1="760" y1="280" x2="760" y2="460" stroke="#06b6d4" strokeWidth="0.5" strokeDasharray="2 4" />
            <circle cx="760" cy="370" r="2.5" fill="#38bdf8" filter="url(#subtle-glow)" />
            <circle cx="760" cy="280" r="2" fill="#22d3ee" />
            <circle cx="840" cy="320" r="2" fill="#22d3ee" />
            <circle cx="840" cy="420" r="2" fill="#22d3ee" />
            <circle cx="680" cy="420" r="2" fill="#22d3ee" />
          </g>
        )}

        {/* 3. Pattern Miner: Cluster network structures */}
        {activeVariant === "patterns" && (
          <g className="nodexa-variant-group" opacity="0.6">
            <circle cx="780" cy="380" r="32" fill="none" stroke="#0ea5e9" strokeWidth="0.75" strokeDasharray="3 5" />
            <circle cx="860" cy="420" r="24" fill="none" stroke="#6366f1" strokeWidth="0.75" strokeDasharray="3 4" />
            <circle cx="730" cy="440" r="20" fill="none" stroke="#06b6d4" strokeWidth="0.75" strokeDasharray="2 4" />
            <line x1="780" y1="380" x2="860" y2="420" stroke="#38bdf8" strokeWidth="0.75" />
            <line x1="780" y1="380" x2="730" y2="440" stroke="#38bdf8" strokeWidth="0.75" />
            <circle cx="780" cy="380" r="2.5" fill="#38bdf8" />
            <circle cx="860" cy="420" r="2" fill="#818cf8" />
            <circle cx="730" cy="440" r="2" fill="#22d3ee" />
          </g>
        )}

        {/* 4. Drift Radar: Directional vector flow & angle coordinates */}
        {activeVariant === "drift" && (
          <g className="nodexa-variant-group" opacity="0.55">
            <circle cx="800" cy="420" r="80" fill="none" stroke="#0ea5e9" strokeWidth="0.5" strokeDasharray="2 6" />
            <circle cx="800" cy="420" r="50" fill="none" stroke="#0284c7" strokeWidth="0.5" strokeDasharray="3 5" />
            <line x1="700" y1="420" x2="900" y2="420" stroke="#334155" strokeWidth="0.75" strokeDasharray="2 4" />
            <line x1="800" y1="320" x2="800" y2="520" stroke="#334155" strokeWidth="0.75" strokeDasharray="2 4" />
            <line x1="730" y1="350" x2="870" y2="490" stroke="#38bdf8" strokeWidth="0.75" opacity="0.4" />
            <circle cx="845" cy="375" r="2.5" fill="#f59e0b" filter="url(#subtle-glow)" />
          </g>
        )}

        {/* 5. Verifier / Escalations: Shield / dual-opinion verification circuits */}
        {activeVariant === "verifier" && (
          <g className="nodexa-variant-group" opacity="0.6">
            <path
              d="M 800 320 L 860 350 L 860 430 L 800 480 L 740 430 L 740 350 Z"
              fill="none"
              stroke="#0ea5e9"
              strokeWidth="0.8"
              strokeDasharray="4 4"
            />
            <circle cx="800" cy="400" r="2" fill="#10b981" filter="url(#subtle-glow)" />
            <line x1="740" y1="390" x2="860" y2="390" stroke="#0284c7" strokeWidth="0.5" strokeDasharray="2 4" />
          </g>
        )}

        {/* 6. Benchmark: Measurement matrix and accuracy coordinates */}
        {activeVariant === "benchmark" && (
          <g className="nodexa-variant-group" opacity="0.55">
            <rect x="720" y="340" width="160" height="120" fill="none" stroke="#64748b" strokeWidth="0.5" strokeDasharray="2 4" />
            <line x1="720" y1="400" x2="880" y2="400" stroke="#64748b" strokeWidth="0.5" strokeDasharray="2 4" />
            <line x1="800" y1="340" x2="800" y2="460" stroke="#64748b" strokeWidth="0.5" strokeDasharray="2 4" />
            <circle cx="760" cy="370" r="2" fill="#38bdf8" />
            <circle cx="840" cy="370" r="2" fill="#10b981" />
            <circle cx="760" cy="430" r="2" fill="#f59e0b" />
            <circle cx="840" cy="430" r="2" fill="#10b981" />
          </g>
        )}

        {/* 7. Architecture: Stratified layer flow conduits */}
        {activeVariant === "architecture" && (
          <g className="nodexa-variant-group" opacity="0.6">
            <rect x="710" y="280" width="180" height="24" rx="3" fill="none" stroke="#0284c7" strokeWidth="0.75" strokeDasharray="4 4" />
            <rect x="710" y="320" width="180" height="24" rx="3" fill="none" stroke="#0ea5e9" strokeWidth="0.75" strokeDasharray="4 4" />
            <rect x="710" y="360" width="180" height="24" rx="3" fill="none" stroke="#06b6d4" strokeWidth="0.75" strokeDasharray="4 4" />
            <rect x="710" y="400" width="180" height="24" rx="3" fill="none" stroke="#10b981" strokeWidth="0.75" strokeDasharray="4 4" />
            <rect x="710" y="440" width="180" height="24" rx="3" fill="none" stroke="#6366f1" strokeWidth="0.75" strokeDasharray="4 4" />
            <line x1="800" y1="260" x2="800" y2="480" stroke="#38bdf8" strokeWidth="0.6" strokeDasharray="2 4" />
          </g>
        )}

        {/* 8. Login: Expressive institutional clearing network */}
        {activeVariant === "login" && (
          <g className="nodexa-variant-group" opacity="0.75">
            <path
              d="M 80 440 L 260 260 L 460 260 L 600 400 L 800 400 L 940 260 L 1140 260 L 1280 400 L 1480 400"
              stroke="#0ea5e9"
              strokeWidth="1.2"
              fill="none"
              strokeDasharray="6 8"
            />
            <circle cx="260" cy="260" r="3.5" fill="#38bdf8" filter="url(#subtle-glow)" />
            <circle cx="600" cy="400" r="3" fill="#06b6d4" />
            <circle cx="940" cy="260" r="4.5" fill="#0284c7" filter="url(#subtle-glow)" />
            <circle cx="1280" cy="400" r="3.5" fill="#38bdf8" />
            <rect x="200" y="200" width="120" height="120" rx="6" fill="none" stroke="#0ea5e9" strokeWidth="0.5" strokeDasharray="3 6" opacity="0.3" />
            <rect x="880" y="200" width="120" height="120" rx="6" fill="none" stroke="#0284c7" strokeWidth="0.5" strokeDasharray="3 6" opacity="0.3" />
          </g>
        )}
      </svg>

      {/* ── Layer 4: Vignette & Readability Gradient Overlay ───────────────────────── */}
      {/* 
        This layer guarantees that content text and numbers retain pristine contrast.
        The center remains calm and unobstructed, with network elements subtly visible 
        toward the margins and behind transparent panel backdrops.
      */}
      <div
        className="absolute inset-0"
        style={{
          background: `
            radial-gradient(ellipse 70% 60% at 50% 50%, rgba(8, 11, 17, 0.75) 0%, rgba(8, 11, 17, 0.95) 100%),
            linear-gradient(to bottom, rgba(8, 11, 17, 0.4) 0%, rgba(8, 11, 17, 0.8) 100%)
          `,
        }}
      />
    </div>
  );
};

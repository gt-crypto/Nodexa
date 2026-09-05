import React from "react";

export interface NodexaLogoProps {
  /**
   * Render only the geometric icon or with the NODEXA wordmark.
   * Default is false (renders icon + wordmark).
   */
  iconOnly?: boolean;
  /**
   * Pixel size of the mark. Defaults to 28.
   */
  size?: number;
  /**
   * Optional subtitle/descriptor display under wordmark. Defaults to true when wordmark is visible.
   */
  showSubtitle?: boolean;
  /**
   * Custom CSS class name applied to container.
   */
  className?: string;
  /**
   * Subtitle text. Defaults to "AI FINANCE CONTROLLER".
   */
  subtitle?: string;
}

/**
 * Custom geometric SVG icon for NODEXA.
 * Features a precision financial node lattice forming an "N" mark
 * with verified pathways, interconnect vertices, and a nexus core.
 */
export const NodexaMark: React.FC<{ size?: number; className?: string }> = ({
  size = 28,
  className = "",
}) => {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={`shrink-0 ${className}`}
      aria-hidden="true"
    >
      <defs>
        {/* Gradients for node pathways */}
        <linearGradient id="nodexa-stem-left" x1="6" y1="26" x2="6" y2="6" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#0284c7" />
          <stop offset="100%" stopColor="#38bdf8" />
        </linearGradient>
        <linearGradient id="nodexa-diagonal" x1="6" y1="6" x2="26" y2="26" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#38bdf8" />
          <stop offset="50%" stopColor="#22d3ee" />
          <stop offset="100%" stopColor="#0ea5e9" />
        </linearGradient>
        <linearGradient id="nodexa-stem-right" x1="26" y1="26" x2="26" y2="6" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#0ea5e9" />
          <stop offset="100%" stopColor="#06b6d4" />
        </linearGradient>
        <radialGradient id="nodexa-core-glow" cx="16" cy="16" r="8" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#22d3ee" stopOpacity="0.4" />
          <stop offset="100%" stopColor="#22d3ee" stopOpacity="0" />
        </radialGradient>
      </defs>

      {/* Subtle core glow behind intersection */}
      <circle cx="16" cy="16" r="7" fill="url(#nodexa-core-glow)" />

      {/* Subtle horizontal grid coordinate lines */}
      <line x1="6" y1="16" x2="26" y2="16" stroke="#1e293b" strokeWidth="1" strokeDasharray="1.5 2" />

      {/* Node Pathways: Forming the geometric "N" */}
      {/* 1. Left Vertical Stem */}
      <line x1="7" y1="7" x2="7" y2="25" stroke="url(#nodexa-stem-left)" strokeWidth="2.5" strokeLinecap="round" />

      {/* 2. Diagonal Pathway */}
      <line x1="7" y1="7" x2="25" y2="25" stroke="url(#nodexa-diagonal)" strokeWidth="2.5" strokeLinecap="round" />

      {/* 3. Right Vertical Stem */}
      <line x1="25" y1="7" x2="25" y2="25" stroke="url(#nodexa-stem-right)" strokeWidth="2.5" strokeLinecap="round" />

      {/* Minor Secondary Data Pathway (Upper Right Return - financial closed loop) */}
      <path
        d="M25 11 L19 11"
        stroke="#38bdf8"
        strokeWidth="1.2"
        strokeLinecap="round"
        strokeOpacity="0.5"
      />

      {/* Key Network Vertices / Data Nodes */}
      {/* Top Left Vertex */}
      <circle cx="7" cy="7" r="2.75" fill="#FFFFFF" stroke="#38bdf8" strokeWidth="1.75" />
      <circle cx="7" cy="7" r="1.2" fill="#0284c7" />

      {/* Bottom Left Vertex */}
      <circle cx="7" cy="25" r="2.5" fill="#FFFFFF" stroke="#0284c7" strokeWidth="1.5" />
      <circle cx="7" cy="25" r="1" fill="#38bdf8" />

      {/* Central Nexus Intersection Node */}
      <circle cx="16" cy="16" r="2.75" fill="#FFFFFF" stroke="#4F46E5" strokeWidth="1.75" />
      <circle cx="16" cy="16" r="1.25" fill="#4F46E5" />

      {/* Bottom Right Vertex */}
      <circle cx="25" cy="25" r="2.75" fill="#FFFFFF" stroke="#0ea5e9" strokeWidth="1.75" />
      <circle cx="25" cy="25" r="1.2" fill="#0284c7" />

      {/* Top Right Vertex */}
      <circle cx="25" cy="7" r="2.5" fill="#FFFFFF" stroke="#06b6d4" strokeWidth="1.5" />
      <circle cx="25" cy="7" r="1" fill="#22d3ee" />
    </svg>
  );
};

/**
 * Complete NODEXA brand component supporting icon-only, standard, and enterprise header styles.
 */
export const NodexaLogo: React.FC<NodexaLogoProps> = ({
  iconOnly = false,
  size = 28,
  showSubtitle = true,
  className = "",
  subtitle = "AI FINANCE CONTROLLER",
}) => {
  if (iconOnly) {
    return (
      <div className={`inline-flex items-center justify-center ${className}`}>
        <NodexaMark size={size} />
      </div>
    );
  }

  return (
    <div className={`inline-flex items-center gap-2.5 ${className}`}>
      <div className="p-1.5 rounded-lg bg-indigo-50/80 border border-indigo-100/90 shadow-xs flex items-center justify-center">
        <NodexaMark size={size} />
      </div>
      <div className="flex flex-col">
        <div className="flex items-center leading-none">
          <span className="font-bold tracking-tight text-slate-900 font-sans text-base">
            NODEXA
          </span>
        </div>
        {showSubtitle && (
          <span className="text-[10px] font-mono tracking-wider text-slate-500 mt-1 uppercase font-medium">
            {subtitle}
          </span>
        )}
      </div>
    </div>
  );
};

export default NodexaLogo;

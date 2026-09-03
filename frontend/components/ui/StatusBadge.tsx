import React from "react";

export type BadgeTone = "success" | "warning" | "danger" | "info" | "neutral" | "purple";

export interface StatusBadgeProps {
  status?: string;
  tone?: BadgeTone;
  children?: React.ReactNode;
  icon?: React.ReactNode;
  className?: string;
  size?: "sm" | "md";
}

export function getStatusTone(status?: string): BadgeTone {
  if (!status) return "neutral";
  const s = status.toUpperCase();
  if (["CRITICAL", "FAILED", "HIGH_DRIFT", "REJECTED", "SECURITY_ALERT"].includes(s)) return "danger";
  if (["HIGH", "WARNING", "ELEVATED", "WATCH", "MANUAL_REVIEW"].includes(s)) return "warning";
  if (["PASSED", "VERIFIED", "RESOLVED", "LOW", "STABLE", "NORMAL"].includes(s)) return "success";
  if (["INFO", "INVESTIGATING", "AUTO_EXECUTED", "SEEDED"].includes(s)) return "info";
  if (["LEGITIMATE", "EDGE_CASE", "PARTIAL_SETTLEMENT"].includes(s)) return "neutral";
  return "neutral";
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({
  status,
  tone,
  children,
  icon,
  className = "",
  size = "md",
}) => {
  const resolvedTone = tone || getStatusTone(status);

  const toneMap: Record<BadgeTone, string> = {
    success: "bg-emerald-500/15 border-emerald-500/30 text-emerald-300",
    warning: "bg-amber-500/15 border-amber-500/30 text-amber-300",
    danger: "bg-rose-500/15 border-rose-500/30 text-rose-300 font-semibold",
    info: "bg-teal-500/15 border-teal-500/30 text-teal-300",
    neutral: "bg-slate-800/80 border-slate-700/60 text-slate-300",
    purple: "bg-purple-500/15 border-purple-500/30 text-purple-300",
  };

  const sizeMap = {
    sm: "px-2 py-0.5 text-[11px]",
    md: "px-2.5 py-1 text-xs",
  };

  const content = children || status;

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-md font-mono font-medium border ${toneMap[resolvedTone]} ${sizeMap[size]} ${className}`}
    >
      {icon && <span className="shrink-0">{icon}</span>}
      <span>{content}</span>
    </span>
  );
};


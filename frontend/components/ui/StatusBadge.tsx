import React from "react";

export type BadgeTone = "success" | "warning" | "danger" | "info" | "neutral" | "orange";

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
  if (["CRITICAL", "FAILED", "HIGH_DRIFT", "REJECTED", "SECURITY_ALERT", "HIGH RISK"].includes(s)) return "danger";
  if (["ELEVATED", "ORANGE"].includes(s)) return "orange";
  if (["HIGH", "WARNING", "WATCH", "MANUAL_REVIEW", "PENDING_APPROVAL"].includes(s)) return "warning";
  if (["PASSED", "VERIFIED", "RESOLVED", "LOW", "STABLE", "NORMAL", "VERIFIED_CLOSED"].includes(s)) return "success";
  if (["INFO", "INVESTIGATING", "AUTO_EXECUTED", "SEEDED", "ACTIVE"].includes(s)) return "info";
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

  // Semantic enterprise risk tones - restrained, high-contrast, no loud glare
  const toneMap: Record<BadgeTone, string> = {
    success: "bg-emerald-950/30 border-emerald-800/40 text-emerald-300",
    warning: "bg-amber-950/30 border-amber-800/40 text-amber-300",
    orange: "bg-orange-950/30 border-orange-800/40 text-orange-300",
    danger: "bg-rose-950/30 border-rose-800/40 text-rose-300 font-medium",
    info: "bg-sky-950/30 border-sky-800/40 text-sky-300",
    neutral: "bg-slate-900/90 border-slate-800 text-slate-300",
  };

  const sizeMap = {
    sm: "px-2 py-0.5 text-[11px]",
    md: "px-2.5 py-0.5 text-xs",
  };

  const content = children || status;

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded font-mono border ${toneMap[resolvedTone]} ${sizeMap[size]} ${className}`}
    >
      {icon && <span className="shrink-0">{icon}</span>}
      <span>{content}</span>
    </span>
  );
};

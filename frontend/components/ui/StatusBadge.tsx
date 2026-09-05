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

  // Subtle tinted semantic backgrounds with strong readable text
  const toneMap: Record<BadgeTone, string> = {
    success: "bg-emerald-100 border border-emerald-700 text-emerald-950 shadow-2xs font-bold",
    warning: "bg-[#FFFBEB] border-amber-200 text-[#B45309]",
    orange: "bg-orange-50 border-orange-200 text-orange-800",
    danger: "bg-[#FEF2F2] border-rose-200 text-[#DC2626] font-medium",
    info: "bg-[#EEF2FF] border-indigo-200 text-[#4F46E5]",
    neutral: "bg-slate-100 border-slate-200 text-slate-700",
  };

  const sizeMap = {
    sm: "px-2 py-0.5 text-[11px]",
    md: "px-2.5 py-0.5 text-xs",
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

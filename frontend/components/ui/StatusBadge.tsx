import React from "react";

export type BadgeTone = "success" | "warning" | "danger" | "info" | "neutral";

export interface StatusBadgeProps {
  tone?: BadgeTone;
  children: React.ReactNode;
  icon?: React.ReactNode;
  className?: string;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({
  tone = "neutral",
  children,
  icon,
  className = "",
}) => {
  const toneMap: Record<BadgeTone, string> = {
    success: "bg-emerald-500/15 border-emerald-500/30 text-emerald-300",
    warning: "bg-amber-500/15 border-amber-500/30 text-amber-300",
    danger: "bg-rose-500/15 border-rose-500/30 text-rose-300",
    info: "bg-teal-500/15 border-teal-500/30 text-teal-300",
    neutral: "bg-slate-800/80 border-slate-700/60 text-slate-300",
  };

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-mono font-medium border ${toneMap[tone]} ${className}`}
    >
      {icon && <span className="shrink-0">{icon}</span>}
      <span>{children}</span>
    </span>
  );
};

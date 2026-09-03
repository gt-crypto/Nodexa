import React from "react";

export interface SectionHeadingProps {
  icon: React.ReactNode;
  title: string;
  badge?: {
    text: string;
    icon?: React.ReactNode;
    color?: string;
  };
  description?: string;
  action?: React.ReactNode;
  className?: string;
}

export const SectionHeading: React.FC<SectionHeadingProps> = ({
  icon,
  title,
  badge,
  description,
  action,
  className = "",
}) => {
  return (
    <div
      className={`flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6 pb-6 border-b border-slate-800 ${className}`}
    >
      <div>
        {badge && (
          <div
            className={`inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-mono mb-2 border ${
              badge.color || "bg-teal-500/10 border-teal-500/30 text-teal-300"
            }`}
          >
            {badge.icon}
            <span>{badge.text}</span>
          </div>
        )}
        <h2 className="text-2xl sm:text-3xl font-bold text-white flex items-center gap-3 tracking-tight">
          <span className="p-2 rounded-xl bg-slate-800/80 border border-slate-700/60 text-teal-400 shrink-0">
            {icon}
          </span>
          <span>{title}</span>
        </h2>
        {description && (
          <p className="text-sm text-slate-400 mt-2 max-w-2xl leading-relaxed">
            {description}
          </p>
        )}
      </div>

      {action && <div className="flex items-center gap-3 shrink-0">{action}</div>}
    </div>
  );
};

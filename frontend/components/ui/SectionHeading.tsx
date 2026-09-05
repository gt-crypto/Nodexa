import React from "react";

export interface SectionHeadingProps {
  icon?: React.ReactNode;
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
      className={`flex flex-col md:flex-row md:items-center justify-between gap-4 mb-5 pb-4 border-b border-slate-200 ${className}`}
    >
      <div>
        {badge && (
          <div
            className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-[11px] font-mono mb-2 border ${
              badge.color || "bg-indigo-50 border-indigo-200 text-indigo-700"
            }`}
          >
            {badge.icon}
            <span>{badge.text}</span>
          </div>
        )}
        <div className="flex items-center gap-2.5">
          {icon && (
            <span className="p-1.5 rounded-lg bg-indigo-50 border border-indigo-100 text-indigo-600 shrink-0">
              {icon}
            </span>
          )}
          <h2 className="text-xl sm:text-2xl font-bold text-slate-900 tracking-tight font-sans">
            {title}
          </h2>
        </div>
        {description && (
          <p className="text-xs sm:text-sm text-slate-500 mt-1.5 max-w-2xl leading-relaxed">
            {description}
          </p>
        )}
      </div>

      {action && <div className="flex items-center gap-2.5 shrink-0">{action}</div>}
    </div>
  );
};

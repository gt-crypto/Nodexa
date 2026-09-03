"use client";

import React from "react";

export interface TabItem {
  id: string;
  label: string;
  count?: number;
  icon?: React.ReactNode;
}

export interface TabsProps {
  tabs: TabItem[];
  activeTab: string;
  onChange: (id: string) => void;
  className?: string;
  ariaLabel?: string;
}

export const Tabs: React.FC<TabsProps> = ({
  tabs,
  activeTab,
  onChange,
  className = "",
  ariaLabel = "Navigation tabs",
}) => {
  const handleKeyDown = (e: React.KeyboardEvent, index: number) => {
    if (e.key === "ArrowRight") {
      e.preventDefault();
      const nextIndex = (index + 1) % tabs.length;
      onChange(tabs[nextIndex].id);
    } else if (e.key === "ArrowLeft") {
      e.preventDefault();
      const prevIndex = (index - 1 + tabs.length) % tabs.length;
      onChange(tabs[prevIndex].id);
    }
  };

  return (
    <div
      role="tablist"
      aria-label={ariaLabel}
      className={`flex items-center gap-1.5 border-b border-slate-800/80 pb-px overflow-x-auto text-sm scrollbar-none ${className}`}
    >
      {tabs.map((tab, idx) => {
        const isActive = activeTab === tab.id;
        return (
          <button
            key={tab.id}
            role="tab"
            aria-selected={isActive}
            tabIndex={isActive ? 0 : -1}
            onClick={() => onChange(tab.id)}
            onKeyDown={(e) => handleKeyDown(e, idx)}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-t-lg font-medium text-xs sm:text-sm whitespace-nowrap transition-all duration-150 border-b-2 -mb-px focus:outline-none focus:ring-2 focus:ring-teal-500/40 cursor-pointer ${
              isActive
                ? "border-teal-400 text-teal-300 bg-slate-900/50 font-semibold"
                : "border-transparent text-slate-400 hover:text-slate-200 hover:bg-slate-900/30"
            }`}
          >
            {tab.icon && <span className="shrink-0">{tab.icon}</span>}
            <span>{tab.label}</span>
            {tab.count !== undefined && (
              <span
                className={`ml-1.5 px-2 py-0.5 rounded-full text-xs font-mono ${
                  isActive
                    ? "bg-teal-500/20 text-teal-300 border border-teal-500/40"
                    : "bg-slate-800 text-slate-400"
                }`}
              >
                {tab.count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
};

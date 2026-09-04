"use client";

import React, { useState, useEffect } from "react";
import { Shield, Activity, Sparkles, Scale, Network, TrendingUp, Gauge, Send, Zap, Award } from "lucide-react";

interface NavItem {
  id: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}

interface NavGroup {
  name: string;
  items: NavItem[];
}

const NAV_GROUPS: NavGroup[] = [
  {
    name: "Overview",
    items: [
      { id: "impact", label: "Business ROI", icon: TrendingUp },
      { id: "copilot", label: "Copilot", icon: Sparkles },
    ],
  },
  {
    name: "Analysis",
    items: [
      { id: "patterns", label: "Patterns", icon: Network },
      { id: "merchants", label: "Trust Score", icon: Shield },
      { id: "drift", label: "Drift Radar", icon: Activity },
    ],
  },
  {
    name: "Operations",
    items: [
      { id: "verifier", label: "Verifier", icon: Scale },
      { id: "escalations", label: "Escalations", icon: Send },
    ],
  },
  {
    name: "Evaluation",
    items: [
      { id: "injection", label: "Injection", icon: Zap },
      { id: "benchmark", label: "Benchmark", icon: Award },
      { id: "calibration", label: "Calibration", icon: Gauge },
    ],
  },
];

const ALL_NAV_ITEMS = NAV_GROUPS.flatMap((g) => g.items);

export const Navbar: React.FC = () => {
  const [activeSection, setActiveSection] = useState<string>("impact");

  useEffect(() => {
    const handleScroll = () => {
      const threshold = 180;
      let currentSection = ALL_NAV_ITEMS[0].id;

      for (const item of ALL_NAV_ITEMS) {
        const el = document.getElementById(item.id);
        if (el) {
          const rect = el.getBoundingClientRect();
          if (rect.top <= threshold) {
            currentSection = item.id;
          }
        }
      }

      // Bottom of page check
      if (
        typeof window !== "undefined" &&
        window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 100
      ) {
        currentSection = ALL_NAV_ITEMS[ALL_NAV_ITEMS.length - 1].id;
      }

      setActiveSection(currentSection);
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    handleScroll();
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const scrollTo = (id: string, e: React.MouseEvent) => {
    e.preventDefault();
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "start" });
      setActiveSection(id);
    }
  };

  return (
    <header className="sticky top-0 z-50 w-full glass-panel border-b border-slate-800/80 bg-slate-950/80 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-4">
        {/* Brand */}
        <div className="flex items-center space-x-3 shrink-0">
          <div className="p-2 rounded-xl bg-teal-500/10 border border-teal-500/30 text-teal-400">
            <Shield className="w-5 h-5" />
          </div>
          <div className="hidden sm:block">
            <span className="font-bold text-lg tracking-tight text-white flex items-center gap-1.5">
              NODEXA
            </span>
          </div>
        </div>

        {/* Grouped Scroll Spy Navigation (Issue 22 & Finding #8) */}
        <nav
          aria-label="Dashboard sections"
          className="flex items-center gap-2 overflow-x-auto py-1 text-xs font-medium scrollbar-none max-w-3xl"
        >
          {NAV_GROUPS.map((group, groupIdx) => (
            <React.Fragment key={group.name}>
              {groupIdx > 0 && <span className="h-4 w-px bg-slate-800/80 shrink-0" />}
              <div className="flex items-center gap-1 shrink-0">
                {group.items.map((item) => {
                  const Icon = item.icon;
                  const isActive = activeSection === item.id;
                  return (
                    <a
                      key={item.id}
                      href={`#${item.id}`}
                      onClick={(e) => scrollTo(item.id, e)}
                      aria-current={isActive ? "page" : undefined}
                      className={`px-2.5 py-1.5 rounded-lg transition-all duration-150 flex items-center gap-1.5 shrink-0 focus:outline-none focus:ring-2 focus:ring-teal-500/40 text-xs ${
                        isActive
                          ? "bg-teal-500/20 text-teal-300 border border-teal-500/40 font-semibold shadow-sm shadow-teal-500/10"
                          : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/60 border border-transparent"
                      }`}
                      title={`${group.name} → ${item.label}`}
                    >
                      <Icon className={`w-3.5 h-3.5 ${isActive ? "text-teal-400" : "text-slate-500"}`} />
                      <span>{item.label}</span>
                    </a>
                  );
                })}
              </div>
            </React.Fragment>
          ))}
        </nav>

        {/* System Status Pill */}
        <div className="flex items-center gap-2 pl-3 border-l border-slate-800 shrink-0">
          <span className="flex h-2 w-2 relative">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
          </span>
          <span className="text-xs font-mono text-slate-300 hidden md:inline">Healthy</span>
        </div>
      </div>
    </header>
  );
};

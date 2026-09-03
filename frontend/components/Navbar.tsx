"use client";

import React, { useState, useEffect } from "react";
import { Shield, Activity, Sparkles, Scale, Network, TrendingUp, Gauge, Send, Zap, Award } from "lucide-react";

interface NavItem {
  id: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}

const NAV_ITEMS: NavItem[] = [
  { id: "impact", label: "Business ROI", icon: TrendingUp },
  { id: "copilot", label: "Copilot", icon: Sparkles },
  { id: "verifier", label: "Verifier", icon: Scale },
  { id: "patterns", label: "Patterns", icon: Network },
  { id: "merchants", label: "Trust Score", icon: Shield },
  { id: "drift", label: "Drift Radar", icon: Activity },
  { id: "calibration", label: "Calibration", icon: Gauge },
  { id: "escalations", label: "Escalations", icon: Send },
  { id: "injection", label: "Injection", icon: Zap },
  { id: "benchmark", label: "Benchmark", icon: Award },
];

export const Navbar: React.FC = () => {
  const [activeSection, setActiveSection] = useState<string>("impact");

  useEffect(() => {
    const handleScroll = () => {
      const scrollPosition = window.scrollY + 200;
      for (const item of NAV_ITEMS) {
        const el = document.getElementById(item.id);
        if (el) {
          const top = el.offsetTop;
          const height = el.offsetHeight;
          if (scrollPosition >= top && scrollPosition < top + height) {
            setActiveSection(item.id);
            break;
          }
        }
      }
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
              Nodal<span className="text-teal-400">Sentinel</span>
            </span>
          </div>
          <span className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-teal-950/80 text-teal-300 border border-teal-800/60 font-mono">
            v2.0
          </span>
        </div>

        {/* Scroll Spy Navigation (Issue 17) */}
        <nav
          aria-label="Dashboard sections"
          className="flex items-center gap-1.5 overflow-x-auto py-1 text-xs font-medium scrollbar-none max-w-2xl"
        >
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const isActive = activeSection === item.id;
            return (
              <a
                key={item.id}
                href={`#${item.id}`}
                onClick={(e) => scrollTo(item.id, e)}
                className={`px-3 py-1.5 rounded-lg transition-all duration-150 flex items-center gap-1.5 shrink-0 focus:outline-none focus:ring-2 focus:ring-teal-500/40 ${
                  isActive
                    ? "bg-teal-500/20 text-teal-300 border border-teal-500/40 font-semibold shadow-sm shadow-teal-500/20"
                    : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/60 border border-transparent"
                }`}
              >
                <Icon className={`w-3.5 h-3.5 ${isActive ? "text-teal-400" : "text-slate-500"}`} />
                <span>{item.label}</span>
              </a>
            );
          })}
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

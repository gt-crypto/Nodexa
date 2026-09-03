"use client";

import React, { useState, useEffect } from "react";
import {
  Shield,
  Activity,
  Sparkles,
  Scale,
  Network,
  TrendingUp,
  Gauge,
  Send,
  Zap,
  Award,
  Menu,
  X,
  Radio,
  Lock,
} from "lucide-react";

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
    name: "OVERVIEW",
    items: [
      { id: "impact", label: "Business ROI", icon: TrendingUp },
      { id: "copilot", label: "Copilot", icon: Sparkles },
    ],
  },
  {
    name: "INTELLIGENCE",
    items: [
      { id: "patterns", label: "Patterns", icon: Network },
      { id: "merchants", label: "Trust Score", icon: Shield },
      { id: "drift", label: "Drift Radar", icon: Activity },
    ],
  },
  {
    name: "OPERATIONS",
    items: [
      { id: "verifier", label: "Verifier", icon: Scale },
      { id: "escalations", label: "Escalations", icon: Send },
      { id: "injection", label: "Injection", icon: Zap },
    ],
  },
  {
    name: "EVALUATION",
    items: [
      { id: "benchmark", label: "Benchmark", icon: Award },
      { id: "calibration", label: "Calibration", icon: Gauge },
    ],
  },
];

const ALL_NAV_ITEMS = NAV_GROUPS.flatMap((g) => g.items);

export const Sidebar: React.FC = () => {
  const [activeSection, setActiveSection] = useState<string>("impact");
  const [mobileOpen, setMobileOpen] = useState<boolean>(false);

  // Viewport-relative Scroll-Spy
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

      // Check if user has scrolled near bottom of page
      if (
        typeof window !== "undefined" &&
        window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 120
      ) {
        currentSection = ALL_NAV_ITEMS[ALL_NAV_ITEMS.length - 1].id;
      }

      setActiveSection(currentSection);
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    handleScroll();
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  // Handle ESC key to close mobile drawer
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && mobileOpen) {
        setMobileOpen(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [mobileOpen]);

  const scrollTo = (id: string, e: React.MouseEvent) => {
    e.preventDefault();
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "start" });
      setActiveSection(id);
    }
    setMobileOpen(false);
  };

  const navContent = (
    <div className="flex flex-col h-full">
      {/* Brand Header */}
      <div className="p-5 border-b border-slate-800/80 bg-slate-950/60 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="p-2 rounded-xl bg-teal-500/10 border border-teal-500/30 text-teal-400">
            <Shield className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <span className="font-bold text-base tracking-tight text-white">
                Nodal<span className="text-teal-400">Sentinel</span>
              </span>
              <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-teal-950/80 text-teal-300 border border-teal-800/60 font-mono">
                v2.0
              </span>
            </div>
            <p className="text-[11px] font-mono text-slate-400 tracking-tight mt-0.5">
              AI Finance Controller
            </p>
          </div>
        </div>

        {/* Mobile close button */}
        <button
          onClick={() => setMobileOpen(false)}
          className="lg:hidden p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800/60 transition"
          aria-label="Close navigation menu"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Navigation Links (Scrollable) */}
      <nav
        aria-label="Dashboard sections"
        className="flex-1 overflow-y-auto p-3.5 space-y-5 sidebar-scrollbar"
      >
        {NAV_GROUPS.map((group) => (
          <div key={group.name} className="space-y-1">
            <h2 className="px-2.5 text-[10px] font-bold font-mono text-slate-400 uppercase tracking-wider mb-1.5">
              {group.name}
            </h2>
            <div className="space-y-0.5">
              {group.items.map((item) => {
                const Icon = item.icon;
                const isActive = activeSection === item.id;
                return (
                  <a
                    key={item.id}
                    href={`#${item.id}`}
                    onClick={(e) => scrollTo(item.id, e)}
                    aria-current={isActive ? "page" : undefined}
                    className={`relative group flex items-center gap-3 px-3 py-2 rounded-xl text-xs font-medium transition-all duration-150 cursor-pointer focus:outline-none focus:ring-2 focus:ring-teal-500/40 ${
                      isActive
                        ? "bg-teal-500/15 border border-teal-500/40 text-teal-300 font-semibold shadow-sm shadow-teal-500/10"
                        : "border border-transparent text-slate-400 hover:text-slate-200 hover:bg-slate-900/70"
                    }`}
                  >
                    {/* Active left indicator accent */}
                    {isActive && (
                      <span className="absolute left-0 top-2 bottom-2 w-1 rounded-r-full bg-teal-400 shadow-sm shadow-teal-400" />
                    )}

                    <Icon
                      className={`w-4 h-4 shrink-0 transition-colors ${
                        isActive
                          ? "text-teal-400"
                          : "text-slate-400 group-hover:text-slate-300"
                      }`}
                    />
                    <span className="truncate">{item.label}</span>
                  </a>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* Footer / System Status Area */}
      <div className="p-3.5 border-t border-slate-800/80 bg-slate-950/90 space-y-2">
        <div className="flex items-center gap-2.5 px-3 py-2.5 rounded-xl bg-slate-900/80 border border-slate-800/80">
          <span className="flex h-2.5 w-2.5 relative shrink-0">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span>
          </span>
          <div className="min-w-0 flex-1">
            <div className="text-xs font-semibold text-slate-200 truncate font-mono flex items-center justify-between">
              <span>System Status</span>
              <span className="text-[10px] text-emerald-400 font-bold">200 OK</span>
            </div>
            <p className="text-[11px] text-slate-400 truncate">Deterministic controller active</p>
          </div>
        </div>

        <div className="flex items-center justify-between px-2 text-[10px] font-mono text-slate-400">
          <span className="flex items-center gap-1 text-slate-400">
            <Lock className="w-3 h-3 text-teal-400" />
            Audit Protected
          </span>
          <span className="text-slate-400">Mainnet v2.0</span>
        </div>
      </div>
    </div>
  );

  return (
    <>
      {/* Mobile Sticky Top Header (Only on screens < 1024px) */}
      <header className="lg:hidden sticky top-0 z-40 w-full glass-panel border-b border-slate-800/80 bg-slate-950/90 backdrop-blur-md px-4 h-14 flex items-center justify-between">
        <div className="flex items-center space-x-2.5">
          <div className="p-1.5 rounded-lg bg-teal-500/10 border border-teal-500/30 text-teal-400">
            <Shield className="w-4 h-4" />
          </div>
          <span className="font-bold text-sm tracking-tight text-white">
            Nodal<span className="text-teal-400">Sentinel</span>
          </span>
          <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-teal-950/80 text-teal-300 border border-teal-800/60 font-mono">
            v2.0
          </span>
        </div>

        <div className="flex items-center gap-2">
          {/* Active section indicator pill */}
          <span className="text-xs font-mono text-slate-400 hidden sm:inline-block px-2 py-0.5 rounded bg-slate-900 border border-slate-800 truncate max-w-[120px]">
            {ALL_NAV_ITEMS.find((i) => i.id === activeSection)?.label}
          </span>

          <button
            onClick={() => setMobileOpen(true)}
            className="p-2 rounded-lg text-slate-300 hover:text-white bg-slate-900/80 border border-slate-800 hover:bg-slate-800/80 transition"
            aria-label="Open navigation menu"
            aria-expanded={mobileOpen}
          >
            <Menu className="w-5 h-5" />
          </button>
        </div>
      </header>

      {/* Mobile Drawer Backdrop */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm lg:hidden transition-opacity"
          onClick={() => setMobileOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Mobile Off-Canvas Drawer */}
      <div
        className={`fixed top-0 bottom-0 left-0 z-50 w-72 max-w-[85vw] bg-slate-950 border-r border-slate-800/90 shadow-2xl transition-transform duration-200 ease-in-out lg:hidden ${
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        {navContent}
      </div>

      {/* Desktop Fixed Left Sidebar (≥ 1024px) */}
      <aside
        className="hidden lg:flex flex-col fixed top-0 bottom-0 left-0 w-64 z-30 bg-slate-950/95 border-r border-slate-800/80 backdrop-blur-md"
        aria-label="Main Navigation"
      >
        {navContent}
      </aside>
    </>
  );
};

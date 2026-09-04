"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  Sparkles,
  Scale,
  Network,
  TrendingUp,
  Send,
  Zap,
  Award,
  Menu,
  X,
  Lock,
  Layers,
  ShieldAlert,
} from "lucide-react";
import { useAuth } from "../lib/auth";
import { NodexaLogo, NodexaMark } from "./brand/NodexaLogo";

export interface NavItem {
  id: string;
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}

export interface NavGroup {
  name: string;
  items: NavItem[];
}

export const NAV_GROUPS: NavGroup[] = [
  {
    name: "Overview",
    items: [
      { id: "impact", href: "/", label: "Business ROI", icon: TrendingUp },
      { id: "copilot", href: "/copilot", label: "Copilot", icon: Sparkles },
    ],
  },
  {
    name: "Intelligence",
    items: [
      { id: "patterns", href: "/patterns", label: "Patterns", icon: Network },
      { id: "trust-score", href: "/trust-score", label: "Trust Score", icon: ShieldAlert },
      { id: "drift-radar", href: "/drift-radar", label: "Drift Radar", icon: Activity },
    ],
  },
  {
    name: "Operations",
    items: [
      { id: "verifier", href: "/verifier", label: "Verifier", icon: Scale },
      { id: "escalations", href: "/escalations", label: "Escalations", icon: Send },
      { id: "injection", href: "/injection", label: "Data Injection", icon: Zap },
    ],
  },
  {
    name: "Evaluation & Specs",
    items: [
      { id: "benchmark", href: "/benchmark", label: "Benchmark", icon: Award },
      { id: "architecture", href: "/architecture", label: "Architecture", icon: Layers },
    ],
  },
];

const ALL_NAV_ITEMS = NAV_GROUPS.flatMap((g) => g.items);

export const Sidebar: React.FC = () => {
  const pathname = usePathname();
  const { user } = useAuth();
  const [mobileOpen, setMobileOpen] = useState<boolean>(false);

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

  // Determine active item based strictly on current URL pathname
  const isItemActive = (itemHref: string) => {
    if (itemHref === "/") {
      return pathname === "/";
    }
    return pathname === itemHref || pathname.startsWith(itemHref + "/");
  };

  const activeItem = ALL_NAV_ITEMS.find((i) => isItemActive(i.href)) || ALL_NAV_ITEMS[0];

  const navContent = (
    <div className="flex flex-col h-full bg-[#090d16]">
      {/* Brand Header */}
      <div className="p-4 border-b border-slate-800/80 flex items-center justify-between">
        <Link
          href="/"
          onClick={() => setMobileOpen(false)}
          className="group cursor-pointer focus:outline-none"
        >
          <NodexaLogo size={24} showSubtitle={true} subtitle="AI FINANCE CONTROLLER" />
        </Link>

        {/* Mobile close button */}
        <button
          onClick={() => setMobileOpen(false)}
          className="lg:hidden p-1.5 rounded-md text-slate-400 hover:text-white hover:bg-slate-800/60 transition-colors"
          aria-label="Close navigation menu"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Navigation Links (Real Next.js Routes) */}
      <nav
        aria-label="Terminal sections"
        className="flex-1 overflow-y-auto p-3 space-y-4 sidebar-scrollbar"
      >
        {NAV_GROUPS.map((group, groupIdx) => (
          <div key={group.name} className={`space-y-1 ${groupIdx > 0 ? "pt-1" : ""}`}>
            <h2 className="px-2.5 text-xs font-semibold tracking-normal text-slate-300 mb-1.5 font-sans">
              {group.name}
            </h2>
            <div className="space-y-0.5">
              {group.items.map((item) => {
                const Icon = item.icon;
                const isActive = isItemActive(item.href);
                const isRoleFocus = Boolean(user?.highlightRoutes.includes(item.href));

                return (
                  <Link
                    key={item.id}
                    href={item.href}
                    onClick={() => setMobileOpen(false)}
                    aria-current={isActive ? "page" : undefined}
                    className={`relative group flex items-center gap-2.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer focus:outline-none focus:ring-1 focus:ring-sky-500/50 ${
                      isActive
                        ? "bg-sky-950/40 border border-sky-800/40 text-sky-200 font-medium"
                        : "border border-transparent text-slate-400 hover:text-slate-200 hover:bg-[#111726]/60"
                    }`}
                  >
                    {/* Active subtle left indicator bar */}
                    {isActive && (
                      <span className="absolute left-0 top-1.5 bottom-1.5 w-0.5 rounded-r bg-sky-400" />
                    )}

                    <Icon
                      className={`w-3.5 h-3.5 shrink-0 transition-colors ${
                        isActive ? "text-sky-400" : "text-slate-500 group-hover:text-slate-300"
                      }`}
                    />
                    <span className="min-w-0 truncate font-sans text-xs">{item.label}</span>

                    {/* Contextual Role Focus indicator (subtle neutral dot, subordinate to active state) */}
                    {isRoleFocus && !isActive && (
                      <span className="ml-auto shrink-0 flex items-center gap-1 text-[10px] font-medium text-slate-500 group-hover:text-slate-400 font-sans">
                        <span className="w-1 h-1 rounded-full bg-sky-400/80" />
                        <span>Focus</span>
                      </span>
                    )}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* Authenticated User Profile Section */}
      {user && (
        <div className="p-3 border-t border-slate-800/80 bg-[#070a10] shrink-0">
          <div className="flex items-center gap-2.5 p-2 rounded-lg bg-[#0d121d] border border-slate-800/80">
            <div className="w-7 h-7 rounded bg-slate-800 border border-slate-700 text-sky-300 font-mono font-bold text-xs flex items-center justify-center shrink-0">
              {user.initials}
            </div>
            <div className="min-w-0 flex-1">
              <div className="text-xs font-medium text-slate-200 truncate leading-tight font-sans">
                {user.role}
              </div>
              <div className="text-[10px] font-mono text-slate-500 truncate mt-0.5">
                {user.email}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Footer / System Status Area */}
      <div className="p-3 border-t border-slate-800/80 bg-[#070a10] space-y-2">
        <div className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-[#0d121d] border border-slate-800/80 text-[11px] font-medium text-slate-300">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 shrink-0" />
          <span className="flex-1 truncate font-sans">Core Controller</span>
          <span className="text-emerald-400 font-semibold text-[10px] font-mono">ACTIVE</span>
        </div>

        <div className="flex items-center justify-between px-1 text-[10px] font-mono text-slate-500">
          <span className="flex items-center gap-1 font-sans">
            <Lock className="w-3 h-3 text-sky-400" />
            Audit Protected
          </span>
          <span>Mainnet v2.0</span>
        </div>
      </div>
    </div>
  );

  return (
    <>
      {/* Mobile Sticky Top Header (Only on screens < 1024px) */}
      <header className="lg:hidden sticky top-0 z-40 w-full border-b border-slate-800/80 bg-[#090d16]/95 backdrop-blur-sm px-4 h-12 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2">
          <NodexaMark size={22} />
          <span className="font-bold text-sm tracking-tight text-white font-sans">
            NODEXA
          </span>
          <span className="text-[9px] font-mono px-1 py-0.5 rounded bg-slate-800 text-sky-400 border border-slate-700">
            v2.0
          </span>
        </Link>

        <div className="flex items-center gap-2">
          {/* Active route indicator pill */}
          <span className="text-[11px] font-mono text-slate-400 hidden sm:inline-block px-2 py-0.5 rounded bg-slate-900 border border-slate-800 truncate max-w-[120px]">
            {activeItem.label}
          </span>

          <button
            onClick={() => setMobileOpen(true)}
            className="p-1.5 rounded-md text-slate-300 hover:text-white bg-slate-900 border border-slate-800 transition-colors"
            aria-label="Open navigation menu"
            aria-expanded={mobileOpen}
          >
            <Menu className="w-4 h-4" />
          </button>
        </div>
      </header>

      {/* Mobile Drawer Backdrop */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm lg:hidden transition-opacity"
          onClick={() => setMobileOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Mobile Off-Canvas Drawer */}
      <div
        className={`fixed top-0 bottom-0 left-0 z-50 w-64 max-w-[85vw] bg-[#090d16] border-r border-slate-800 shadow-2xl transition-transform duration-200 ease-in-out lg:hidden ${
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        {navContent}
      </div>

      {/* Desktop Fixed Left Sidebar (≥ 1024px) */}
      <aside
        className="hidden lg:flex flex-col fixed top-0 bottom-0 left-0 w-64 h-screen z-30 bg-[#090d16] border-r border-slate-800/80"
        aria-label="Main Navigation"
      >
        {navContent}
      </aside>
    </>
  );
};

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
  Zap,
  Award,
  Menu,
  X,
  Lock,
  ShieldAlert,
  FileSpreadsheet,
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
    name: "OVERVIEW",
    items: [
      { id: "dashboard", href: "/", label: "Dashboard", icon: TrendingUp },
    ],
  },
  {
    name: "OPERATIONS",
    items: [
      { id: "exceptions", href: "/exceptions", label: "Exceptions", icon: ShieldAlert },
      { id: "patterns", href: "/patterns", label: "Patterns", icon: Network },
      { id: "verifier", href: "/verifier", label: "Verifier", icon: Scale },
    ],
  },
  {
    name: "INTELLIGENCE",
    items: [
      { id: "copilot", href: "/copilot", label: "Copilot", icon: Sparkles },
      { id: "insights", href: "/trust-score", label: "Insights", icon: Activity },
    ],
  },
  {
    name: "TESTING",
    items: [
      { id: "sandbox", href: "/sandbox", label: "Test New Dataset", icon: FileSpreadsheet },
      { id: "injection", href: "/injection", label: "Digital Twin", icon: Zap },
      { id: "benchmark", href: "/benchmark", label: "Benchmark", icon: Award },
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
    <div className="flex flex-col h-full bg-white border-r border-slate-200">
      {/* Brand Header */}
      <div className="p-4 border-b border-slate-100 flex items-center justify-between">
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
          className="lg:hidden p-1.5 rounded-md text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
          aria-label="Close navigation menu"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Navigation Links */}
      <nav
        aria-label="Terminal sections"
        className="flex-1 overflow-y-auto p-3 space-y-4 sidebar-scrollbar"
      >
        {NAV_GROUPS.map((group, groupIdx) => (
          <div key={group.name} className={`space-y-1 ${groupIdx > 0 ? "pt-1" : ""}`}>
            <h2 className="px-2.5 text-[11px] font-semibold tracking-wider uppercase text-slate-400 mb-1.5 font-mono">
              {group.name}
            </h2>
            <div className="space-y-0.5">
              {group.items.map((item) => {
                const Icon = item.icon;
                const isActive = isItemActive(item.href);

                return (
                  <Link
                    key={item.id}
                    href={item.href}
                    onClick={() => setMobileOpen(false)}
                    aria-current={isActive ? "page" : undefined}
                    className={`relative group flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-medium transition-colors cursor-pointer focus:outline-none focus:ring-1 focus:ring-indigo-500/30 ${
                      isActive
                        ? "bg-indigo-50/90 text-indigo-700 font-semibold"
                        : "text-slate-600 hover:text-slate-900 hover:bg-slate-50"
                    }`}
                  >
                    {/* Active subtle indicator */}
                    {isActive && (
                      <span className="absolute left-0 top-2 bottom-2 w-1 rounded-r bg-indigo-600" />
                    )}

                    <Icon
                      className={`w-4 h-4 shrink-0 transition-colors ${
                        isActive ? "text-indigo-600" : "text-slate-400 group-hover:text-slate-600"
                      }`}
                    />
                    <span className="min-w-0 truncate font-sans text-xs">{item.label}</span>
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* Authenticated User Profile Section */}
      {user && (
        <div className="p-3 border-t border-slate-100 bg-slate-50/50 shrink-0">
          <div className="flex items-center gap-2.5 p-2 rounded-lg bg-white border border-slate-200/80 shadow-xs">
            <div className="w-7 h-7 rounded bg-indigo-50 border border-indigo-100 text-indigo-700 font-mono font-bold text-xs flex items-center justify-center shrink-0">
              {user.initials}
            </div>
            <div className="min-w-0 flex-1">
              <div className="text-xs font-medium text-slate-900 truncate leading-tight font-sans">
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
      <div className="p-3 border-t border-slate-100 bg-white space-y-2">
        <div className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-slate-50 border border-slate-200/70 text-[11px] font-medium text-slate-700">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0" />
          <span className="flex-1 truncate font-sans">Core Controller</span>
          <span className="text-emerald-700 font-semibold text-[10px] font-mono">ACTIVE</span>
        </div>

        <div className="flex items-center justify-between px-1 text-[10px] font-mono text-slate-400">
          <span className="flex items-center gap-1 font-sans">
            <Lock className="w-3 h-3 text-indigo-500" />
            Audit Protected
          </span>
          <span>Mainnet</span>
        </div>
      </div>
    </div>
  );

  return (
    <>
      {/* Mobile Sticky Top Header (Only on screens < 1024px) */}
      <header className="lg:hidden sticky top-0 z-40 w-full border-b border-slate-200 bg-white/95 backdrop-blur-sm px-4 h-12 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2">
          <NodexaMark size={22} />
          <span className="font-bold text-sm tracking-tight text-slate-900 font-sans">
            NODEXA
          </span>
        </Link>

        <div className="flex items-center gap-2">
          <span className="text-[11px] font-mono text-slate-600 hidden sm:inline-block px-2 py-0.5 rounded bg-slate-100 border border-slate-200 truncate max-w-[120px]">
            {activeItem.label}
          </span>

          <button
            onClick={() => setMobileOpen(true)}
            className="p-1.5 rounded-md text-slate-600 hover:text-slate-900 bg-slate-50 border border-slate-200 transition-colors"
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
          className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs lg:hidden transition-opacity"
          onClick={() => setMobileOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Mobile Off-Canvas Drawer */}
      <div
        className={`fixed top-0 bottom-0 left-0 z-50 w-64 max-w-[85vw] bg-white border-r border-slate-200 shadow-2xl transition-transform duration-200 ease-in-out lg:hidden ${
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        {navContent}
      </div>

      {/* Desktop Fixed Left Sidebar (≥ 1024px) */}
      <aside
        className="hidden lg:flex flex-col fixed top-0 bottom-0 left-0 w-64 h-screen z-30 bg-white border-r border-slate-200 shadow-xs"
        aria-label="Main Navigation"
      >
        {navContent}
      </aside>
    </>
  );
};

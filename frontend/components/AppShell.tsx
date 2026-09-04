"use client";

import React, { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Sidebar } from "./Sidebar";
import { useAuth } from "../lib/auth";
import { LogOut } from "lucide-react";
import { NodexaMark } from "./brand/NodexaLogo";
import { NodexaBackground } from "./brand/NodexaBackground";

export const AppShell: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const pathname = usePathname();
  const router = useRouter();
  const { user, isAuthenticated, isLoading, logout } = useAuth();

  const isLoginPage = pathname === "/login";

  // Route protection: redirect unauthenticated users to /login
  useEffect(() => {
    if (!isLoading && !isAuthenticated && !isLoginPage) {
      router.replace("/login");
    }
  }, [isLoading, isAuthenticated, isLoginPage, router]);

  // If on /login page, render children cleanly without sidebar
  if (isLoginPage) {
    return <>{children}</>;
  }

  // Loading state while checking localStorage session
  if (isLoading) {
    return (
      <div className="min-h-screen bg-[#080b11] flex items-center justify-center relative">
        <NodexaBackground />
        <div className="flex flex-col items-center gap-3 relative z-10">
          <NodexaMark size={32} className="animate-pulse" />
          <span className="text-xs font-medium text-slate-400">Verifying session...</span>
        </div>
      </div>
    );
  }

  // Unauthenticated guard state
  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-[#080b11] flex items-center justify-center relative">
        <NodexaBackground />
        <div className="flex flex-col items-center gap-3 relative z-10">
          <NodexaMark size={32} className="animate-pulse" />
          <span className="text-xs font-medium text-slate-400">Redirecting to sign in...</span>
        </div>
      </div>
    );
  }

  // Authenticated application layout with layered background
  return (
    <div className="min-h-screen bg-[#080b11] text-slate-100 relative">
      {/* ── Layer 1: Persistent Abstract Fintech Infrastructure Background ── */}
      <NodexaBackground />

      {/* ── Layer 2: Terminal Navigation Sidebar (relative z-30) ── */}
      <Sidebar />

      {/* ── Layer 3: Main Page Content & Contextual Header (relative z-10) ── */}
      <div className="lg:pl-64 flex flex-col min-h-screen relative z-10">
        {/* Top contextual role banner with single global Sign out action */}
        <header className="flex flex-wrap items-center justify-between px-4 sm:px-6 py-2 border-b border-slate-800/80 bg-[#080b11]/80 backdrop-blur-md gap-2 sticky top-0 z-20">
          <div className="flex items-center gap-2 sm:gap-2.5 min-w-0">
            <span className="text-xs font-semibold text-slate-200 hidden sm:inline tracking-tight font-sans">
              Terminal Session:
            </span>
            <div className="flex items-center gap-1.5 px-2.5 py-0.5 rounded bg-sky-950/40 border border-sky-800/40 text-sky-300 text-xs font-medium truncate">
              <span className="w-1.5 h-1.5 rounded-full bg-sky-400 shrink-0" />
              <span className="truncate">{user?.role}</span>
            </div>
          </div>

          <div className="flex items-center gap-2 sm:gap-3 text-xs text-slate-400 shrink-0">
            <span className="hidden md:inline text-slate-400 font-medium">{user?.department}</span>
            <span className="hidden md:inline text-slate-700">&bull;</span>
            <span className="text-slate-300 hidden sm:inline font-medium">{user?.email}</span>
            <button
              onClick={logout}
              className="px-2.5 py-1 rounded text-xs text-slate-400 hover:text-rose-300 hover:bg-rose-950/40 border border-slate-800 hover:border-rose-800/60 transition-colors flex items-center gap-1.5 cursor-pointer focus:outline-none focus:ring-1 focus:ring-rose-500/40"
              title="Sign out of current session"
              aria-label="Sign out of session"
            >
              <LogOut className="w-3.5 h-3.5 text-rose-400" />
              <span className="font-medium">Sign out</span>
            </button>
          </div>
        </header>

        {/* Main application page content */}
        <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8 space-y-6">
          {children}
        </main>

        {/* Global footer */}
        <footer className="border-t border-slate-800/80 bg-[#070a10]/80 backdrop-blur-sm py-4 text-center text-xs text-slate-500">
          <p>Nodexa &copy; 2026 &mdash; Autonomous AI Finance Controller Architecture &bull; Demo Access</p>
        </footer>
      </div>
    </div>
  );
};

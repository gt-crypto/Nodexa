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
      <div className="min-h-screen bg-[#FFFBE6] flex items-center justify-center relative">
        <NodexaBackground />
        <div className="flex flex-col items-center gap-3 relative z-10">
          <NodexaMark size={32} className="animate-pulse" />
          <span className="text-xs font-medium text-slate-600">Verifying session...</span>
        </div>
      </div>
    );
  }

  // Unauthenticated guard state
  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-[#FFFBE6] flex items-center justify-center relative">
        <NodexaBackground />
        <div className="flex flex-col items-center gap-3 relative z-10">
          <NodexaMark size={32} className="animate-pulse" />
          <span className="text-xs font-medium text-slate-600">Redirecting to sign in...</span>
        </div>
      </div>
    );
  }

  // Authenticated application layout with light neon green fintech background
  return (
    <div className="min-h-screen bg-transparent text-slate-900 relative">
      {/* ── Layer 1: Persistent Abstract Fintech Infrastructure Background ── */}
      <NodexaBackground />

      {/* ── Layer 2: Terminal Navigation Sidebar (relative z-30) ── */}
      <Sidebar />

      {/* ── Layer 3: Main Page Content & Contextual Header (relative z-10) ── */}
      <div className="lg:pl-64 flex flex-col min-h-screen relative z-10">
        {/* Top contextual role banner with single global Sign out action */}
        <header className="flex flex-wrap items-center justify-between px-4 sm:px-6 py-2.5 border-b border-slate-200 bg-white/95 backdrop-blur-md gap-2 sticky top-0 z-20">
          <div className="flex items-center gap-2 sm:gap-2.5 min-w-0">
            <span className="text-xs font-semibold text-slate-700 hidden sm:inline tracking-tight font-sans">
              Terminal Session:
            </span>
            <div className="flex items-center gap-1.5 px-2.5 py-0.5 rounded bg-indigo-50 border border-indigo-200/80 text-indigo-700 text-xs font-medium truncate">
              <span className="w-1.5 h-1.5 rounded-full bg-indigo-500 shrink-0" />
              <span className="truncate">{user?.role}</span>
            </div>
          </div>

          <div className="flex items-center gap-2 sm:gap-3 text-xs text-slate-600 shrink-0">
            <span className="hidden md:inline text-slate-500 font-medium">{user?.department}</span>
            <span className="hidden md:inline text-slate-300">&bull;</span>
            <span className="text-slate-700 hidden sm:inline font-medium">{user?.email}</span>
            <button
              onClick={logout}
              className="px-2.5 py-1 rounded text-xs text-slate-600 hover:text-rose-700 hover:bg-rose-50 border border-slate-200 hover:border-rose-200 transition-colors flex items-center gap-1.5 cursor-pointer focus:outline-none focus:ring-1 focus:ring-rose-400"
              title="Sign out of current session"
              aria-label="Sign out of session"
            >
              <LogOut className="w-3.5 h-3.5 text-rose-500" />
              <span className="font-medium">Sign out</span>
            </button>
          </div>
        </header>

        {/* Main application page content */}
        <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8 space-y-6">
          {children}
        </main>

        {/* Global footer */}
        <footer className="border-t border-slate-200 bg-white/90 backdrop-blur-sm py-4 text-center text-xs text-slate-500">
          <p>Nodexa &copy; 2026 &mdash; Autonomous AI Finance Controller Architecture &bull; Demo Access</p>
        </footer>
      </div>
    </div>
  );
};

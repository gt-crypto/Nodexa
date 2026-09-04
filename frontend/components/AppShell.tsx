"use client";

import React, { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Sidebar } from "./Sidebar";
import { useAuth } from "../lib/auth";
import { Shield, UserCheck, Sparkles, LogOut } from "lucide-react";

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
      <div className="min-h-screen bg-[#090d16] flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" />
          <span className="text-xs font-mono text-slate-400">Verifying demo session...</span>
        </div>
      </div>
    );
  }

  // Unauthenticated guard state
  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-[#090d16] flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" />
          <span className="text-xs font-mono text-slate-400">Redirecting to sign in...</span>
        </div>
      </div>
    );
  }

  // Authenticated application layout
  return (
    <div className="min-h-screen bg-grid-pattern">
      {/* Sidebar with embedded authenticated user profile */}
      <Sidebar />

      <div className="lg:pl-64 flex flex-col min-h-screen">
        {/* Top contextual role banner with single global Sign out action */}
        <header className="flex flex-wrap items-center justify-between px-4 sm:px-6 py-2.5 sm:py-3 border-b border-slate-900 bg-slate-950/80 backdrop-blur-md gap-2">
          <div className="flex items-center gap-2 sm:gap-3 min-w-0">
            <span className="text-[11px] sm:text-xs font-mono text-slate-400 hidden sm:inline">
              Active Controller Session:
            </span>
            <div className="flex items-center gap-1.5 sm:gap-2 px-2.5 py-1 rounded-full bg-teal-500/10 border border-teal-500/30 text-teal-300 text-xs font-mono truncate">
              <span className="w-1.5 h-1.5 rounded-full bg-teal-400 shrink-0" />
              <span className="truncate">{user?.role}</span>
            </div>
          </div>

          <div className="flex items-center gap-2 sm:gap-3 text-xs font-mono text-slate-400 shrink-0">
            <span className="hidden md:inline text-slate-400">{user?.department}</span>
            <span className="hidden md:inline text-slate-700">&bull;</span>
            <span className="text-slate-300 hidden sm:inline">{user?.email}</span>
            <button
              onClick={logout}
              className="px-2.5 py-1 rounded-lg text-xs font-mono text-slate-300 hover:text-rose-300 hover:bg-rose-500/15 border border-slate-800 hover:border-rose-500/30 transition flex items-center gap-1.5 cursor-pointer focus:outline-none focus:ring-2 focus:ring-rose-500/40"
              title="Sign out of current demo session"
              aria-label="Sign out of demo session"
            >
              <LogOut className="w-3.5 h-3.5 text-rose-400" />
              <span>Sign out</span>
            </button>
          </div>
        </header>

        {/* Main application page content */}
        <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
          {children}
        </main>

        {/* Global footer */}
        <footer className="border-t border-slate-900 glass-panel py-6 text-center text-xs text-slate-400 font-mono">
          <p>Nodexa &copy; 2026 &mdash; Autonomous AI Finance Controller Architecture &bull; Demo Access</p>
        </footer>
      </div>
    </div>
  );
};

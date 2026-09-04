"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  Shield,
  Lock,
  Mail,
  Eye,
  EyeOff,
  ArrowRight,
  AlertCircle,
  KeyRound,
  CheckCircle2,
  Sparkles,
} from "lucide-react";
import { useAuth, DEMO_USERS, DEMO_PASSWORD } from "../../lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const { login, isAuthenticated, isLoading } = useAuth();

  const [email, setEmail] = useState<string>("");
  const [password, setPassword] = useState<string>("");
  const [showPassword, setShowPassword] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [selectedDemoEmail, setSelectedDemoEmail] = useState<string | null>(null);

  // If already authenticated, smoothly redirect to dashboard
  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      router.replace("/");
    }
  }, [isAuthenticated, isLoading, router]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);

    const result = login(email, password);
    if (result.success) {
      router.push("/");
    } else {
      setError(result.error || "Authentication failed. Please check your credentials.");
      setIsSubmitting(false);
    }
  };

  const handleSelectDemoUser = (userEmail: string) => {
    setEmail(userEmail);
    setSelectedDemoEmail(userEmail);
    setError(null);
  };

  const handleUseDemoCredentials = (userEmail: string) => {
    setEmail(userEmail);
    setPassword(DEMO_PASSWORD);
    setSelectedDemoEmail(userEmail);
    setError(null);
  };

    if (isLoading || isAuthenticated) {
    return (
      <div className="min-h-screen bg-[#090d16] flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" />
          <span className="text-xs font-mono text-slate-400">Loading Nodexa session...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#090d16] bg-grid-pattern flex flex-col justify-between p-4 sm:p-6 lg:p-8">
      {/* Top micro brand banner */}
      <header className="max-w-md w-full mx-auto flex items-center justify-between pt-2 sm:pt-4">
        <div className="flex items-center space-x-2.5">
          <div className="p-1.5 rounded-lg bg-teal-500/10 border border-teal-500/30 text-teal-400">
            <Shield className="w-4 h-4" />
          </div>
          <span className="font-bold text-sm tracking-tight text-white">
            NODEXA
          </span>
          <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-teal-950/80 text-teal-300 border border-teal-800/60 font-mono">
            v2.0
          </span>
        </div>
        <span className="text-[11px] font-mono text-slate-400">Mainnet • Escrow</span>
      </header>

      {/* Center login card */}
      <main className="max-w-md w-full mx-auto my-auto py-6">
        <div className="glass-panel rounded-2xl p-6 sm:p-8 border border-slate-800 shadow-2xl relative overflow-hidden">
          {/* Subtle background ambient glow */}
          <div className="absolute top-0 right-0 -mr-16 -mt-16 w-56 h-56 bg-teal-500/10 rounded-full blur-3xl pointer-events-none" />
          <div className="absolute bottom-0 left-0 -ml-16 -mb-16 w-56 h-56 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none" />

          {/* Header */}
          <div className="text-center mb-6 relative">
            <div className="inline-flex p-3 rounded-2xl bg-teal-500/10 border border-teal-500/30 text-teal-400 mb-3 shadow-inner">
              <Shield className="w-7 h-7" />
            </div>
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-white mb-1">
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-teal-400 to-cyan-300">NODEXA</span>
            </h1>
            <p className="text-xs font-mono text-teal-400/90 tracking-wide uppercase font-semibold mb-2">
              AI Finance Controller
            </p>
            <p className="text-xs sm:text-sm text-slate-400 max-w-xs mx-auto leading-relaxed">
              Secure control for payment and settlement operations.
            </p>
          </div>

          {/* Error Banner */}
          {error && (
            <div
              role="alert"
              className="mb-5 p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-start gap-2.5 animate-in fade-in duration-200"
            >
              <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
              <span className="leading-snug">{error}</span>
            </div>
          )}

          {/* Login Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Email Field */}
            <div>
              <label
                htmlFor="work-email"
                className="block text-xs font-medium text-slate-300 mb-1.5 font-mono"
              >
                Work email
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                  <Mail className="w-4 h-4" />
                </div>
                <input
                  id="work-email"
                  type="email"
                  required
                  autoComplete="email"
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value);
                    setError(null);
                  }}
                  placeholder="name@nodalsentinel.demo"
                  className="w-full pl-10 pr-3.5 py-2.5 bg-slate-900/90 border border-slate-700/80 rounded-xl text-sm text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-teal-500/50 focus:border-teal-400 transition"
                />
              </div>
            </div>

            {/* Password Field */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label
                  htmlFor="password"
                  className="block text-xs font-medium text-slate-300 font-mono"
                >
                  Password
                </label>
                <span className="text-[10px] font-mono text-slate-400">Demo access</span>
              </div>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                  <Lock className="w-4 h-4" />
                </div>
                <input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  required
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value);
                    setError(null);
                  }}
                  placeholder="Enter demo password"
                  className="w-full pl-10 pr-10 py-2.5 bg-slate-900/90 border border-slate-700/80 rounded-xl text-sm text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-teal-500/50 focus:border-teal-400 transition"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-slate-400 hover:text-slate-200 transition focus:outline-none"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full py-2.5 px-4 rounded-xl bg-gradient-to-r from-teal-500 to-emerald-600 hover:from-teal-400 hover:to-emerald-500 text-white text-sm font-semibold shadow-md shadow-teal-500/20 border border-teal-400/40 transition flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-teal-500/50"
            >
              {isSubmitting ? (
                <>
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  <span>Signing in...</span>
                </>
              ) : (
                <>
                  <span>Sign in to Nodexa</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>

          {/* Demo Credentials Quick-Fill helper */}
          <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between text-xs">
            <span className="text-slate-400 font-mono text-[11px]">
              Demo password: <code className="text-teal-300 font-semibold">{DEMO_PASSWORD}</code>
            </span>
            <button
              type="button"
              onClick={() => handleUseDemoCredentials(email || "finance@nodalsentinel.demo")}
              className="text-[11px] font-mono text-teal-400 hover:text-teal-300 underline underline-offset-2 transition"
            >
              Fill password
            </button>
          </div>

          {/* Demo Accounts List Section */}
          <div className="mt-6 pt-5 border-t border-slate-800/80">
            <div className="flex items-center justify-between mb-3">
              <span className="text-[11px] font-mono font-bold tracking-wider text-slate-400 uppercase flex items-center gap-1.5">
                <KeyRound className="w-3.5 h-3.5 text-teal-400" />
                Demo Accounts
              </span>
              <span className="text-[10px] text-slate-400 font-mono">Click to select role</span>
            </div>

            <div className="space-y-2">
              {Object.values(DEMO_USERS).map((u) => {
                const isSelected = selectedDemoEmail === u.email || email === u.email;
                return (
                  <div
                    key={u.email}
                    onClick={() => handleSelectDemoUser(u.email)}
                    className={`p-2.5 rounded-xl border text-left cursor-pointer transition-all duration-150 flex items-center justify-between group ${
                      isSelected
                        ? "bg-teal-500/10 border-teal-500/50 shadow-sm"
                        : "bg-slate-900/60 border-slate-800 hover:bg-slate-800/60 hover:border-slate-700"
                    }`}
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="w-5 h-5 rounded-md bg-slate-800 border border-slate-700 text-[10px] font-mono font-bold text-teal-300 flex items-center justify-center shrink-0">
                          {u.initials}
                        </span>
                        <span className="text-xs font-medium text-slate-200 group-hover:text-white truncate">
                          {u.role}
                        </span>
                      </div>
                      <p className="text-[11px] font-mono text-slate-400 truncate pl-7 mt-0.5">
                        {u.email}
                      </p>
                    </div>

                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleUseDemoCredentials(u.email);
                      }}
                      title="Use credentials and sign in"
                      className="ml-2 px-2 py-1 text-[10px] font-mono rounded bg-slate-800/80 hover:bg-teal-500/20 text-slate-300 hover:text-teal-200 border border-slate-700 shrink-0 transition"
                    >
                      Use
                    </button>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Subtext notice */}
          <div className="mt-5 pt-3 border-t border-slate-800/60 text-center">
            <p className="text-[11px] font-mono text-slate-400 flex items-center justify-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-teal-400" />
              Demo environment &bull; Synthetic / Test Data
            </p>
          </div>
        </div>
      </main>

      {/* Footer disclaimer */}
      <footer className="max-w-md w-full mx-auto text-center py-2 text-[11px] text-slate-400 font-mono">
        <p>Demo environment &bull; Synthetic / Test Data &bull; Nodexa &copy; 2026</p>
      </footer>
    </div>
  );
}

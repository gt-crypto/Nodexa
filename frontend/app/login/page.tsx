"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  Lock,
  Mail,
  Eye,
  EyeOff,
  ArrowRight,
  AlertCircle,
  KeyRound,
  ShieldCheck,
  Activity,
  CheckCircle2,
  Server,
  Terminal,
} from "lucide-react";
import { useAuth, DEMO_USERS, DEMO_PASSWORD } from "../../lib/auth";
import { NodexaMark, NodexaLogo } from "../../components/brand/NodexaLogo";
import { NodexaBackground } from "../../components/brand/NodexaBackground";

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
      <div className="min-h-screen bg-[#080b11] flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <NodexaMark size={36} className="animate-pulse" />
          <span className="text-xs font-mono text-slate-400">Authenticating Nodexa terminal...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#080b11] text-slate-100 flex flex-col justify-between relative overflow-hidden">
      {/* Visual Identity Background Layer */}
      <NodexaBackground variant="login" />

      {/* ── Layer: Ambient Neon Glow System (Restrained Fintech Infrastructure) ── */}
      <div
        aria-hidden="true"
        className="absolute inset-0 pointer-events-none overflow-hidden select-none z-0"
      >
        {/* Primary soft radial glow centered behind login card on desktop / centered on mobile */}
        <div
          className="ambient-glow-primary absolute top-1/2 left-1/2 lg:left-[72%] w-[420px] sm:w-[580px] lg:w-[720px] h-[420px] sm:h-[580px] lg:h-[720px] rounded-full blur-[100px] sm:blur-[130px] lg:blur-[160px] pointer-events-none"
          style={{
            background:
              "radial-gradient(circle, rgba(14, 165, 233, 0.22) 0%, rgba(99, 102, 241, 0.16) 40%, rgba(139, 92, 246, 0.08) 65%, transparent 80%)",
          }}
        />

        {/* Secondary complementary soft glow in upper-left corner */}
        <div
          className="ambient-glow-secondary absolute -top-24 -left-24 sm:-top-32 sm:-left-32 w-[340px] sm:w-[480px] h-[340px] sm:h-[480px] rounded-full blur-[90px] sm:blur-[120px] pointer-events-none"
          style={{
            background:
              "radial-gradient(circle, rgba(99, 102, 241, 0.12) 0%, rgba(6, 182, 212, 0.08) 50%, transparent 75%)",
          }}
        />

        {/* Tertiary ultra-subtle bottom-right anchor glow */}
        <div
          className="absolute -bottom-32 right-[-10%] w-[380px] sm:w-[520px] h-[380px] sm:h-[520px] rounded-full blur-[110px] pointer-events-none opacity-40"
          style={{
            background:
              "radial-gradient(circle, rgba(2, 132, 199, 0.12) 0%, rgba(79, 70, 229, 0.06) 60%, transparent 80%)",
          }}
        />
      </div>

      {/* Top minimal brand bar with subtle logo ambient glow */}
      <header className="w-full px-6 py-4 border-b border-slate-800/80 bg-[#090d16]/70 backdrop-blur-md flex items-center justify-between relative z-10">
        <div className="relative inline-flex items-center">
          {/* Subtle soft ambient bloom behind the brand mark */}
          <div
            aria-hidden="true"
            className="absolute -inset-2 bg-sky-500/15 rounded-full blur-md pointer-events-none"
          />
          <NodexaLogo size={24} showSubtitle={false} className="relative z-10" />
        </div>
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-[11px] font-medium bg-sky-950/40 text-sky-400 border border-sky-800/40">
            <span className="w-1.5 h-1.5 rounded-full bg-sky-400 animate-pulse" />
            Demo Environment
          </span>
        </div>
      </header>

      {/* Main Full-Screen Layout: Left Brand Identity, Right Enterprise Login Card */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 lg:py-12 flex flex-col lg:flex-row items-center justify-center gap-8 lg:gap-16 relative z-10">
        {/* LEFT COLUMN: Brand Identity & Abstract Financial Infrastructure Visual */}
        <div className="w-full lg:w-1/2 max-w-xl space-y-6">
          <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded bg-[#111726]/80 backdrop-blur-sm border border-slate-800 text-slate-300 text-xs font-medium">
            <Terminal className="w-3.5 h-3.5 text-sky-400" />
            <span className="tracking-wide">INSTITUTIONAL RISK &amp; RECONCILIATION SUITE</span>
          </div>

          <div className="space-y-3">
            <h1 className="text-3xl sm:text-5xl font-extrabold tracking-tight text-white font-sans leading-tight">
              Intelligent control for modern financial operations.
            </h1>
            <p className="text-sm sm:text-base text-slate-400 leading-relaxed font-sans font-normal">
              Nodexa provides deterministic reconciliation, live exception detection, and cryptographically verified financial audit trails across high-throughput nodal networks.
            </p>
          </div>

          {/* Abstract Financial Network Topology Card */}
          <div className="rounded-xl border border-slate-800/80 bg-[#0d121d] p-5 space-y-4 shadow-sm relative overflow-hidden">
            <div className="flex items-center justify-between border-b border-slate-800/80 pb-3 text-xs font-mono text-slate-400">
              <span className="flex items-center gap-2">
                <Server className="w-3.5 h-3.5 text-sky-400" />
                <span>ACTIVE CONTROL INVARIANTS</span>
              </span>
              <span className="text-emerald-400 flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                ONLINE (14/14)
              </span>
            </div>

            {/* Network Vector Illustration */}
            <div className="relative py-2">
              <svg className="w-full h-24" viewBox="0 0 400 80" fill="none" xmlns="http://www.w3.org/2000/svg">
                {/* Background coordinate grid */}
                <line x1="10" y1="20" x2="390" y2="20" stroke="#1e293b" strokeWidth="1" strokeDasharray="2 4" />
                <line x1="10" y1="40" x2="390" y2="40" stroke="#1e293b" strokeWidth="1" strokeDasharray="2 4" />
                <line x1="10" y1="60" x2="390" y2="60" stroke="#1e293b" strokeWidth="1" strokeDasharray="2 4" />

                {/* Connecting financial telemetry pathways */}
                <path d="M40 40 L120 20 L200 40 L280 20 L360 40" stroke="#0ea5e9" strokeWidth="1.5" strokeOpacity="0.8" />
                <path d="M40 40 L120 60 L200 40 L280 60 L360 40" stroke="#06b6d4" strokeWidth="1.2" strokeOpacity="0.5" />

                {/* Nodes with status indicators */}
                <circle cx="40" cy="40" r="4" fill="#080e1a" stroke="#38bdf8" strokeWidth="2" />
                <circle cx="120" cy="20" r="4" fill="#080e1a" stroke="#22d3ee" strokeWidth="2" />
                <circle cx="120" cy="60" r="3.5" fill="#080e1a" stroke="#0284c7" strokeWidth="2" />
                <circle cx="200" cy="40" r="6" fill="#0284c7" stroke="#38bdf8" strokeWidth="2" />
                <circle cx="280" cy="20" r="4" fill="#080e1a" stroke="#22d3ee" strokeWidth="2" />
                <circle cx="280" cy="60" r="3.5" fill="#080e1a" stroke="#0ea5e9" strokeWidth="2" />
                <circle cx="360" cy="40" r="4" fill="#080e1a" stroke="#10b981" strokeWidth="2" />

                {/* Labels */}
                <text x="32" y="58" fill="#64748b" fontSize="8" fontFamily="monospace">GATEWAY</text>
                <text x="182" y="62" fill="#38bdf8" fontSize="8" fontFamily="monospace" fontWeight="bold">NODEXA</text>
                <text x="342" y="58" fill="#64748b" fontSize="8" fontFamily="monospace">ESCROW</text>
              </svg>
            </div>

            <div className="grid grid-cols-3 gap-2 pt-1 text-[11px] font-mono text-slate-400">
              <div className="p-2 rounded bg-[#090d16] border border-slate-800/80">
                <span className="text-slate-400 block text-[10px]">Precision</span>
                <span className="text-slate-200 font-medium">Integer Paise</span>
              </div>
              <div className="p-2 rounded bg-[#090d16] border border-slate-800/80">
                <span className="text-slate-400 block text-[10px]">Governance</span>
                <span className="text-slate-200 font-medium">Dual Controller</span>
              </div>
              <div className="p-2 rounded bg-[#090d16] border border-slate-800/80">
                <span className="text-slate-400 block text-[10px]">Audit Log</span>
                <span className="text-slate-200 font-medium">Append-Only</span>
              </div>
            </div>
          </div>
        </div>

        {/* RIGHT COLUMN: Enterprise Login Card */}
        <div className="w-full lg:w-1/2 max-w-md relative">
          {/* Dedicated soft neon backlight focused directly behind the login card */}
          <div
            aria-hidden="true"
            className="absolute -inset-1.5 sm:-inset-2 bg-gradient-to-br from-sky-500/15 via-indigo-500/10 to-transparent rounded-2xl blur-xl pointer-events-none opacity-80"
          />

          <div className="rounded-xl border border-slate-800/80 bg-[#0d121d]/90 backdrop-blur-md p-6 sm:p-8 shadow-2xl relative">
            <div className="mb-6">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[11px] font-semibold text-sky-400 tracking-wider uppercase">
                  ENTERPRISE ACCESS
                </span>
                <span className="text-[11px] font-mono text-slate-500">Mainnet</span>
              </div>
              <h2 className="text-xl font-bold text-white tracking-tight font-sans">Sign in to console</h2>
              <p className="text-xs text-slate-400 mt-1 font-sans">
                Enter your work credentials or choose a pre-configured role below.
              </p>
            </div>

            {/* Error Banner */}
            {error && (
              <div
                role="alert"
                className="mb-5 p-3 rounded-lg bg-rose-950/40 border border-rose-800/50 text-rose-300 text-xs flex items-start gap-2.5 animate-in fade-in duration-150"
              >
                <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
                <span className="leading-snug">{error}</span>
              </div>
            )}

            {/* Login Form */}
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label
                  htmlFor="work-email"
                  className="block text-xs font-medium text-slate-300 mb-1.5"
                >
                  Work email
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-500">
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
                    placeholder="name@nodexa.demo"
                    className="w-full pl-9 pr-3.5 h-9 bg-[#090d16] border border-slate-700/80 rounded-lg text-xs text-white placeholder-slate-500 focus:outline-none focus:border-sky-500 focus:ring-1 focus:ring-sky-500 transition-colors"
                  />
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label
                    htmlFor="password"
                    className="block text-xs font-medium text-slate-300"
                  >
                    Password
                  </label>
                  <button
                    type="button"
                    onClick={() => handleUseDemoCredentials(email || "finance@nodalsentinel.demo")}
                    className="text-[11px] font-medium text-sky-400 hover:text-sky-300 transition-colors cursor-pointer"
                  >
                    Use demo password
                  </button>
                </div>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-500">
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
                    className="w-full pl-9 pr-9 h-9 bg-[#090d16] border border-slate-700/80 rounded-lg text-xs text-white placeholder-slate-500 focus:outline-none focus:border-sky-500 focus:ring-1 focus:ring-sky-500 transition-colors"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute inset-y-0 right-0 pr-3 flex items-center text-slate-400 hover:text-slate-200 transition focus:outline-none cursor-pointer"
                    aria-label={showPassword ? "Hide password" : "Show password"}
                  >
                    {showPassword ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                  </button>
                </div>
              </div>

              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full h-9 rounded-lg bg-sky-600 hover:bg-sky-500 active:bg-sky-700 text-white text-xs font-semibold border border-sky-500/60 shadow-sm transition-colors flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-1 focus:ring-sky-500"
              >
                {isSubmitting ? (
                  <>
                    <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    <span>Authenticating...</span>
                  </>
                ) : (
                  <>
                    <span>Sign in to Nodexa</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </>
                )}
              </button>
            </form>

            {/* Quick Demo Role Selector */}
            <div className="mt-6 pt-5 border-t border-slate-800/80 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                  <KeyRound className="w-3 h-3 text-sky-400" />
                  Pre-Configured Demo Accounts
                </span>
                <span className="text-[10px] text-slate-400 font-medium">1-Click Auto-Fill</span>
              </div>

              <div className="grid grid-cols-1 gap-2">
                {Object.values(DEMO_USERS).map((u) => {
                  const isSelected = selectedDemoEmail === u.email || email === u.email;
                  return (
                    <div
                      key={u.email}
                      onClick={() => handleSelectDemoUser(u.email)}
                      className={`p-2 rounded-lg border text-left cursor-pointer transition-colors flex items-center justify-between group ${
                        isSelected
                          ? "bg-sky-950/40 border-sky-600/60"
                          : "bg-[#090d16] border-slate-800 hover:border-slate-700"
                      }`}
                    >
                      <div className="flex items-center gap-2.5 min-w-0">
                        <span className="w-6 h-6 rounded bg-slate-800 border border-slate-700 text-[10px] font-mono font-bold text-sky-300 flex items-center justify-center shrink-0">
                          {u.initials}
                        </span>
                        <div className="min-w-0">
                          <span className="text-xs font-semibold text-slate-200 block truncate">
                            {u.role}
                          </span>
                          <span className="text-[10px] font-mono text-slate-400 block truncate">
                            {u.email}
                          </span>
                        </div>
                      </div>

                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleUseDemoCredentials(u.email);
                        }}
                        className="px-2 py-1 text-[10px] font-medium rounded bg-slate-800 hover:bg-sky-900/60 text-slate-300 hover:text-sky-200 border border-slate-700 shrink-0 transition-colors cursor-pointer"
                      >
                        Auto-Fill
                      </button>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="mt-4 pt-3 border-t border-slate-800/60 text-center">
              <span className="text-[11px] text-slate-400">
                Demo Password: <code className="text-slate-300 font-mono font-semibold px-1.5 py-0.5 rounded bg-slate-800/60 border border-slate-700/50">{DEMO_PASSWORD}</code>
              </span>
            </div>
          </div>
        </div>
      </main>

      {/* Footer disclaimer */}
      <footer className="w-full px-6 py-4 border-t border-slate-800/80 text-center text-xs text-slate-500 font-sans relative z-10">
        <p>Demo Environment &bull; Synthetic Financial Data &bull; Nodexa &copy; 2026</p>
      </footer>
    </div>
  );
}

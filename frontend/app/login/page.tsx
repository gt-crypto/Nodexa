"use client";

import React, { useState, useEffect, useRef } from "react";
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
  Play,
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
  const [isPlaying, setIsPlaying] = useState<boolean>(true);
  const videoRef = useRef<HTMLVideoElement | null>(null);

  // Guarantee instant video playback: programmatic DOM mute + play + global interaction fallback
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    // Explicitly set DOM properties to satisfy Chromium/Safari autoplay requirements
    video.muted = true;
    video.defaultMuted = true;
    video.volume = 0;

    const startPlayback = () => {
      if (!video) return;
      video.muted = true;
      const playPromise = video.play();
      if (playPromise !== undefined) {
        playPromise
          .then(() => setIsPlaying(true))
          .catch(() => {
            setIsPlaying(false);
          });
      }
    };

    startPlayback();

    const onPlay = () => setIsPlaying(true);
    const onPause = () => setIsPlaying(false);
    const onCanPlay = () => startPlayback();

    video.addEventListener("play", onPlay);
    video.addEventListener("pause", onPause);
    video.addEventListener("canplay", onCanPlay);

    // Global interaction fallback: any tap, click, or key anywhere immediately starts playback
    const handleInteraction = () => {
      if (video && video.paused) {
        video.muted = true;
        video.play().then(() => setIsPlaying(true)).catch(() => {});
      }
    };

    window.addEventListener("pointerdown", handleInteraction, { passive: true });
    window.addEventListener("touchstart", handleInteraction, { passive: true });
    window.addEventListener("keydown", handleInteraction, { passive: true });

    return () => {
      video.removeEventListener("play", onPlay);
      video.removeEventListener("pause", onPause);
      video.removeEventListener("canplay", onCanPlay);
      window.removeEventListener("pointerdown", handleInteraction);
      window.removeEventListener("touchstart", handleInteraction);
      window.removeEventListener("keydown", handleInteraction);
    };
  }, []);

  const togglePlay = () => {
    const video = videoRef.current;
    if (video) {
      if (video.paused) {
        video.muted = true;
        video.play().then(() => setIsPlaying(true)).catch(() => {});
      } else {
        video.pause();
        setIsPlaying(false);
      }
    }
  };

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
      <div className="min-h-screen bg-[#FFFBE6] flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <NodexaMark size={36} className="animate-pulse" />
          <span className="text-xs font-mono text-slate-800 font-semibold">Authenticating Nodexa terminal...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-transparent text-slate-900 flex flex-col justify-between relative overflow-hidden">
      {/* Visual Identity Background Layer */}
      <NodexaBackground variant="login" />

      {/* ── Layer: Ambient Warm Yellow Glow System (Clean Fintech Infrastructure) ── */}
      <div
        aria-hidden="true"
        className="absolute inset-0 pointer-events-none overflow-hidden select-none z-0"
      >
        {/* Primary soft radial glow centered behind login card on desktop / centered on mobile */}
        <div
          className="ambient-glow-primary absolute top-1/2 left-1/2 lg:left-[72%] w-[420px] sm:w-[580px] lg:w-[720px] h-[420px] sm:h-[580px] lg:h-[720px] rounded-full blur-[100px] sm:blur-[130px] lg:blur-[160px] pointer-events-none"
          style={{
            background:
              "radial-gradient(circle, rgba(244, 211, 94, 0.28) 0%, rgba(255, 243, 176, 0.2) 40%, rgba(79, 70, 229, 0.03) 65%, transparent 80%)",
          }}
        />

        {/* Secondary complementary soft glow in upper-left corner */}
        <div
          className="ambient-glow-secondary absolute -top-24 -left-24 sm:-top-32 sm:-left-32 w-[340px] sm:w-[480px] h-[340px] sm:h-[480px] rounded-full blur-[90px] sm:blur-[120px] pointer-events-none"
          style={{
            background:
              "radial-gradient(circle, rgba(255, 243, 176, 0.3) 0%, rgba(244, 211, 94, 0.15) 50%, transparent 75%)",
          }}
        />

        {/* Tertiary ultra-subtle bottom-right anchor glow */}
        <div
          className="absolute -bottom-32 right-[-10%] w-[380px] sm:w-[520px] h-[380px] sm:h-[520px] rounded-full blur-[110px] pointer-events-none opacity-40"
          style={{
            background:
              "radial-gradient(circle, rgba(244, 211, 94, 0.18) 0%, rgba(79, 70, 229, 0.02) 60%, transparent 80%)",
          }}
        />
      </div>

      {/* Top minimal brand bar with subtle logo ambient glow */}
      <header className="w-full px-6 py-4 border-b border-slate-200 bg-white/80 backdrop-blur-md flex items-center justify-between relative z-10">
        <div className="relative inline-flex items-center">
          <NodexaLogo size={24} showSubtitle={false} className="relative z-10" />
        </div>
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-[11px] font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
            Demo Environment
          </span>
        </div>
      </header>

      {/* Main Full-Screen Layout: Left Brand Identity, Right Enterprise Login Card */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 lg:py-12 flex flex-col lg:flex-row items-center justify-center gap-8 lg:gap-16 relative z-10">
        {/* LEFT COLUMN: Brand Identity & Abstract Financial Infrastructure Visual */}
        <div className="w-full lg:w-1/2 max-w-xl space-y-6">
          <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded bg-white border border-slate-200 text-slate-600 text-xs font-semibold shadow-2xs">
            <Terminal className="w-3.5 h-3.5 text-indigo-600" />
            <span className="tracking-wide">INSTITUTIONAL RISK &amp; RECONCILIATION SUITE</span>
          </div>

          <div className="space-y-3">
            <h1 className="text-3xl sm:text-5xl font-extrabold tracking-tight text-slate-900 font-sans leading-tight">
              Intelligent control for modern financial operations.
            </h1>
            <p className="text-sm sm:text-base text-slate-600 leading-relaxed font-sans font-normal">
              Nodexa provides deterministic reconciliation, live exception detection, and cryptographically verified financial audit trails across high-throughput nodal networks.
            </p>
          </div>

          {/* Nodexa in Action Video Preview Card */}
          <div className="rounded-xl border border-slate-200 bg-white p-4 sm:p-5 space-y-3 shadow-xs relative overflow-hidden">
            <div className="flex items-center justify-between border-b border-slate-100 pb-2.5 text-xs font-mono text-slate-500">
              <span className="flex items-center gap-2 font-semibold text-slate-800">
                <Activity className="w-3.5 h-3.5 text-indigo-600" />
                <span>NODEXA IN ACTION</span>
              </span>
              <span className={`font-semibold flex items-center gap-1 text-[11px] ${isPlaying ? "text-emerald-700" : "text-amber-700"}`}>
                <span className={`w-1.5 h-1.5 rounded-full ${isPlaying ? "bg-emerald-500 animate-pulse" : "bg-amber-500"}`} />
                {isPlaying ? "LIVE DEMO" : "CLICK TO PLAY"}
              </span>
            </div>

            {/* Video Player Container */}
            <div
              onClick={togglePlay}
              className="relative w-full aspect-video rounded-lg overflow-hidden bg-slate-950 border border-slate-200/80 shadow-2xs cursor-pointer group select-none"
              title={isPlaying ? "Click to pause preview" : "Click to play preview"}
            >
              <video
                ref={videoRef}
                src="/first_20_seconds.mp4"
                autoPlay
                muted
                loop
                playsInline
                preload="auto"
                className="w-full h-full object-cover rounded-lg"
                title="Nodexa Autonomous AI Finance Controller Demo"
              />

              {/* Pause overlay with intuitive play button if autoplay was blocked */}
              {!isPlaying && (
                <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/35 backdrop-blur-[1px] transition-all">
                  <div className="w-12 h-12 rounded-full bg-white/95 text-slate-900 flex items-center justify-center shadow-lg group-hover:scale-110 transition-transform">
                    <Play className="w-5 h-5 fill-slate-900 ml-0.5 text-slate-900" />
                  </div>
                  <span className="text-white text-[11px] font-mono mt-2 font-medium bg-black/60 px-2.5 py-0.5 rounded shadow-sm">
                    Click to Play Demo
                  </span>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* RIGHT COLUMN: Enterprise Login Card */}
        <div className="w-full lg:w-1/2 max-w-md relative">
          <div className="rounded-xl border border-slate-200 bg-white p-6 sm:p-8 shadow-sm relative">
            <div className="mb-6">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[11px] font-bold text-indigo-600 tracking-wider uppercase">
                  ENTERPRISE ACCESS
                </span>
                <span className="text-[11px] font-mono text-slate-400 font-medium">Mainnet</span>
              </div>
              <h2 className="text-xl font-bold text-slate-900 tracking-tight font-sans">Sign in to console</h2>
              <p className="text-xs text-slate-500 mt-1 font-sans">
                Enter your work credentials or choose a pre-configured role below.
              </p>
            </div>

            {/* Error Banner */}
            {error && (
              <div
                role="alert"
                className="mb-5 p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-start gap-2.5 animate-in fade-in duration-150"
              >
                <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                <span className="leading-snug">{error}</span>
              </div>
            )}

            {/* Login Form */}
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label
                  htmlFor="work-email"
                  className="block text-xs font-semibold text-slate-700 mb-1.5"
                >
                  Work email
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
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
                    className="w-full pl-9 pr-3.5 h-9 bg-white border border-slate-300 rounded-lg text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 shadow-2xs transition-colors"
                  />
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label
                    htmlFor="password"
                    className="block text-xs font-semibold text-slate-700"
                  >
                    Password
                  </label>
                  <button
                    type="button"
                    onClick={() => handleUseDemoCredentials(email || "finance@nodalsentinel.demo")}
                    className="text-[11px] font-semibold text-indigo-600 hover:text-indigo-700 transition-colors cursor-pointer"
                  >
                    Use demo password
                  </button>
                </div>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
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
                    className="w-full pl-9 pr-9 h-9 bg-white border border-slate-300 rounded-lg text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 shadow-2xs transition-colors"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute inset-y-0 right-0 pr-3 flex items-center text-slate-400 hover:text-slate-700 transition focus:outline-none cursor-pointer"
                    aria-label={showPassword ? "Hide password" : "Show password"}
                  >
                    {showPassword ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                  </button>
                </div>
              </div>

              <button
                type="submit"
                data-variant="primary"
                disabled={isSubmitting}
                className="btn-primary-cta w-full h-9 rounded-lg bg-[#F4D35E] hover:bg-[#E8C84A] active:bg-[#DDBA35] text-slate-950 text-xs font-semibold shadow-xs transition-colors flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-[#F4D35E]/40 border border-[#E8C84A]"
              >
                {isSubmitting ? (
                  <>
                    <div className="w-3.5 h-3.5 border-2 border-slate-950 border-t-transparent rounded-full animate-spin" />
                    <span>Authenticating...</span>
                  </>
                ) : (
                  <>
                    <span>Sign in to Nodexa</span>
                    <ArrowRight className="w-3.5 h-3.5 text-slate-950" />
                  </>
                )}
              </button>
            </form>

            {/* Quick Demo Role Selector */}
            <div className="mt-6 pt-5 border-t border-slate-100 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold text-slate-700 uppercase tracking-wider flex items-center gap-1.5">
                  <KeyRound className="w-3 h-3 text-indigo-600" />
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
                      className={`p-2.5 rounded-lg border text-left cursor-pointer transition-colors flex items-center justify-between group ${
                        isSelected
                          ? "bg-indigo-50/80 border-indigo-400 shadow-2xs"
                          : "bg-slate-50/70 border-slate-200 hover:border-slate-300 hover:bg-slate-50"
                      }`}
                    >
                      <div className="flex items-center gap-2.5 min-w-0">
                        <span className="w-6 h-6 rounded bg-white border border-slate-200 text-[10px] font-mono font-bold text-indigo-700 flex items-center justify-center shrink-0 shadow-2xs">
                          {u.initials}
                        </span>
                        <div className="min-w-0">
                          <span className="text-xs font-semibold text-slate-900 block truncate">
                            {u.role}
                          </span>
                          <span className="text-[10px] font-mono text-slate-500 block truncate">
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
                        className="px-2.5 py-1 text-[10px] font-semibold rounded bg-white hover:bg-indigo-50 text-slate-700 hover:text-indigo-700 border border-slate-200 shrink-0 shadow-2xs transition-colors cursor-pointer"
                      >
                        Auto-Fill
                      </button>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="mt-4 pt-3 border-t border-slate-100 text-center">
              <span className="text-[11px] text-slate-500">
                Demo Password: <code className="text-slate-800 font-mono font-semibold px-1.5 py-0.5 rounded bg-slate-100 border border-slate-200">{DEMO_PASSWORD}</code>
              </span>
            </div>
          </div>
        </div>
      </main>

      {/* Footer disclaimer */}
      <footer className="w-full px-6 py-4 border-t border-slate-200 bg-white/60 text-center text-xs text-slate-500 font-sans relative z-10">
        <p>Demo Environment &bull; Synthetic Financial Data &bull; Nodexa &copy; 2026</p>
      </footer>
    </div>
  );
}

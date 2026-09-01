import React from "react";
import { Shield, Activity, GitBranch, Terminal } from "lucide-react";

export const Navbar: React.FC = () => {
  return (
    <header className="sticky top-0 z-50 w-full glass-panel border-b border-slate-800/80">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="p-2 rounded-lg bg-teal-500/10 border border-teal-500/30 text-teal-400">
            <Shield className="w-5 h-5" />
          </div>
          <div>
            <span className="font-bold text-lg tracking-tight text-white flex items-center gap-1.5">
              Nodal<span className="text-teal-400">Sentinel</span>
            </span>
          </div>
          <span className="hidden sm:inline-flex text-[11px] font-medium px-2 py-0.5 rounded-full bg-teal-950/80 text-teal-300 border border-teal-800/60 font-mono">
            v0.1.0-foundation
          </span>
        </div>

        <nav className="flex items-center space-x-6 text-sm">
          <a
            href="#control-loop"
            className="text-slate-400 hover:text-teal-300 transition-colors flex items-center gap-1.5"
          >
            <Activity className="w-4 h-4" />
            <span className="hidden md:inline">Control Loop</span>
          </a>
          <a
            href="#architecture"
            className="text-slate-400 hover:text-teal-300 transition-colors flex items-center gap-1.5"
          >
            <GitBranch className="w-4 h-4" />
            <span className="hidden md:inline">Layer Isolation</span>
          </a>
          <div className="flex items-center gap-2 pl-2 border-l border-slate-800">
            <span className="flex h-2 w-2 relative">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-teal-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-teal-500"></span>
            </span>
            <span className="text-xs font-mono text-slate-300">Ready</span>
          </div>
        </nav>
      </div>
    </header>
  );
};

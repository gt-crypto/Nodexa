import type { Metadata } from "next";
import "./globals.css";
import { Sidebar } from "../components/Sidebar";

export const metadata: Metadata = {
  title: "Nodal Sentinel | AI Finance Controller",
  description:
    "AI Finance Controller for Nodal Account Health. Deterministic financial control coupled with controlled AI investigation.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="antialiased bg-[#090d16] text-slate-100 min-h-screen">
        <div className="min-h-screen bg-grid-pattern">
          <Sidebar />

          <div className="lg:pl-64 flex flex-col min-h-screen">
            <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
              {children}
            </main>

            <footer className="border-t border-slate-900 glass-panel py-6 text-center text-xs text-slate-500 font-mono">
              <p>Nodal Sentinel &copy; 2026 &mdash; Autonomous AI Finance Controller Architecture</p>
            </footer>
          </div>
        </div>
      </body>
    </html>
  );
}

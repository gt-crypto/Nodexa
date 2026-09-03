import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "../lib/auth";
import { AppShell } from "../components/AppShell";

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
        <AuthProvider>
          <AppShell>{children}</AppShell>
        </AuthProvider>
      </body>
    </html>
  );
}

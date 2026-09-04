import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "../lib/auth";
import { AppShell } from "../components/AppShell";

export const metadata: Metadata = {
  title: "Nodexa — AI Finance Controller",
  description:
    "AI-powered financial control, reconciliation, investigation, and verification for payment operations.",
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

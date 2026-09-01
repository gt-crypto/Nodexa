import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Nodal Sentinel | AI Finance Controller",
  description: "AI Finance Controller for Nodal Account Health. Deterministic financial control coupled with controlled AI investigation.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="antialiased bg-[#090d16] text-slate-100 min-h-screen">
        {children}
      </body>
    </html>
  );
}

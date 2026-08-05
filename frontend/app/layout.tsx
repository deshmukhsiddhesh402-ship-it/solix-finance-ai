import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Solix Finance AI",
  description: "AI-powered finance, accounting, tax, and Excel automation platform.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-[#0a0a12] text-slate-100 antialiased">{children}</body>
    </html>
  );
}

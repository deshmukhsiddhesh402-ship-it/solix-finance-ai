import Link from "next/link";
import { Wand2, Calculator, Receipt, LayoutDashboard, Landmark, TrendingUp, MessageSquare, Sparkles, GraduationCap, ScanLine, Bot, ShieldCheck, CreditCard } from "lucide-react";

const MODULES = [
  { href: "/excel-assistant", title: "AI Excel Assistant", desc: "Explain, generate, fix formulas. VBA, Office Scripts, Pivot plans.", icon: Wand2, color: "from-violet-600/20 to-indigo-600/20 border-violet-400/30" },
  { href: "/accounting", title: "Accounting Core", desc: "Journal entries → Trial Balance, P&L, Balance Sheet.", icon: Calculator, color: "from-emerald-600/20 to-violet-600/20 border-emerald-400/30" },
  { href: "/tax", title: "Indian Tax Module", desc: "GST, TDS, and Income Tax calculators.", icon: Receipt, color: "from-amber-600/20 to-violet-600/20 border-amber-400/30" },
  { href: "/dashboard", title: "Dashboard", desc: "Live KPIs from your posted books, with Excel/PDF export.", icon: LayoutDashboard, color: "from-indigo-600/20 to-emerald-600/20 border-indigo-400/30" },
  { href: "/banking", title: "Banking & Reconciliation", desc: "Match bank statement lines against your books automatically.", icon: Landmark, color: "from-sky-600/20 to-violet-600/20 border-sky-400/30" },
  { href: "/analysis", title: "Financial Analysis", desc: "NPV, IRR, CAGR, Break-even, DCF Valuation, Scenario Analysis.", icon: TrendingUp, color: "from-indigo-600/20 to-emerald-600/20 border-indigo-400/30" },
  { href: "/chat", title: "AI Chat", desc: "Upload PDFs, Excel, Word files, or bank statements and ask questions.", icon: MessageSquare, color: "from-violet-600/20 to-sky-600/20 border-violet-400/30" },
  { href: "/excel-automation", title: "Excel Automation", desc: "Auto-clean data, remove duplicates, detect errors, categorize expenses.", icon: Sparkles, color: "from-emerald-600/20 to-amber-600/20 border-emerald-400/30" },
  { href: "/learning", title: "Learning Mode", desc: "Excel, Tally, Power BI, GST, TDS, ITR, Accounting, Finance, US CMA.", icon: GraduationCap, color: "from-fuchsia-600/20 to-indigo-600/20 border-fuchsia-400/30" },
  { href: "/invoice-ocr", title: "OCR & Invoice Processing", desc: "Extract vendor, GSTIN, amounts from invoices — export to Excel or journal entries.", icon: ScanLine, color: "from-teal-600/20 to-violet-600/20 border-teal-400/30" },
  { href: "/copilot", title: "AI Finance Copilot", desc: "Ask about your books in plain language — expenses, profit drivers, forecasts, GST.", icon: Bot, color: "from-violet-600/20 to-emerald-600/20 border-violet-400/30" },
  { href: "/admin", title: "Enterprise Admin", desc: "Roles & permissions (Admin/Accountant/Auditor), audit log, API keys.", icon: ShieldCheck, color: "from-sky-600/20 to-indigo-600/20 border-sky-400/30" },
  { href: "/pricing", title: "Pricing & Billing", desc: "Trial, Pro, and Enterprise plans — subscribe via Razorpay (UPI/cards).", icon: CreditCard, color: "from-violet-600/20 to-amber-600/20 border-violet-400/30" },
];

export default function Home() {
  return (
    <main className="min-h-screen bg-[#0a0a12] text-slate-100 flex flex-col items-center justify-center px-6 py-20">
      <h1 className="text-4xl font-semibold tracking-tight bg-gradient-to-r from-violet-300 via-indigo-300 to-amber-300 bg-clip-text text-transparent mb-3">
        Solix Finance AI
      </h1>
      <p className="text-slate-400 mb-12 text-center max-w-md">
        AI-powered finance, accounting, tax, and Excel automation — built for CA firms and finance professionals.
      </p>
      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-5 max-w-6xl w-full">
        {MODULES.map(({ href, title, desc, icon: Icon, color }) => (
          <Link key={href} href={href} className={`rounded-2xl border bg-gradient-to-br ${color} backdrop-blur-xl p-6 hover:scale-[1.02] transition`}>
            <Icon size={22} className="mb-3 text-slate-200" />
            <h2 className="font-medium mb-1">{title}</h2>
            <p className="text-xs text-slate-400">{desc}</p>
          </Link>
        ))}
      </div>
    </main>
  );
}

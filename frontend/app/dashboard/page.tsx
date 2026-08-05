"use client";

import { useEffect, useState } from "react";
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, PieChart, Pie, Cell,
} from "recharts";
import {
  TrendingUp, TrendingDown, Wallet, Receipt, Landmark, ArrowDownCircle,
  ArrowUpCircle, PieChart as PieIcon, Layers, Download, FileDown, Loader2,
} from "lucide-react";

/**
 * Fetches live KPIs from /api/dashboard/summary (backed by posted journal
 * entries — see app.routers.dashboard + app.services.dashboard_engine).
 * If no journal entries have been posted yet (data_points === 0) or the
 * backend is unreachable, this silently falls back to the MOCK_* data
 * below so the page still demos well on a fresh install.
 */

const MOCK_KPIS = [
  { label: "Revenue (MTD)", value: "₹18,40,000", change: "+12.4%", up: true, icon: TrendingUp, color: "text-emerald-300" },
  { label: "Expenses (MTD)", value: "₹9,20,000", change: "+4.1%", up: false, icon: TrendingDown, color: "text-red-300" },
  { label: "Cash Position", value: "₹32,15,000", change: "+6.8%", up: true, icon: Wallet, color: "text-violet-300" },
  { label: "GST Liability", value: "₹1,65,600", change: "Due in 6 days", up: null, icon: Receipt, color: "text-amber-300" },
  { label: "TDS Payable", value: "₹42,000", change: "Due in 12 days", up: null, icon: Landmark, color: "text-amber-300" },
  { label: "Receivables", value: "₹6,80,000", change: "-3.2%", up: true, icon: ArrowDownCircle, color: "text-sky-300" },
  { label: "Payables", value: "₹3,10,000", change: "+1.5%", up: false, icon: ArrowUpCircle, color: "text-orange-300" },
  { label: "Profit Margin", value: "27.3%", change: "+2.1 pts", up: true, icon: PieIcon, color: "text-emerald-300" },
  { label: "Working Capital", value: "₹14,90,000", change: "Healthy", up: true, icon: Layers, color: "text-indigo-300" },
];

const MOCK_TREND = [
  { month: "Feb", revenue: 1250000, expenses: 780000 },
  { month: "Mar", revenue: 1420000, expenses: 810000 },
  { month: "Apr", revenue: 1360000, expenses: 850000 },
  { month: "May", revenue: 1590000, expenses: 870000 },
  { month: "Jun", revenue: 1680000, expenses: 900000 },
  { month: "Jul", revenue: 1840000, expenses: 920000 },
];

const MOCK_CASHFLOW = [
  { month: "Feb", net: 470000 },
  { month: "Mar", net: 610000 },
  { month: "Apr", net: 510000 },
  { month: "May", net: 720000 },
  { month: "Jun", net: 780000 },
  { month: "Jul", net: 920000 },
];

const MOCK_EXPENSE_BREAKDOWN = [
  { name: "Salaries", value: 480000, color: "#8b5cf6" },
  { name: "Rent", value: 120000, color: "#6366f1" },
  { name: "Marketing", value: 95000, color: "#f59e0b" },
  { name: "Utilities", value: 60000, color: "#10b981" },
  { name: "Other", value: 165000, color: "#64748b" },
];

function INR(n: number) {
  return "₹" + n.toLocaleString("en-IN");
}

export default function DashboardPage() {
  const [loading, setLoading] = useState(true);
  const [isLive, setIsLive] = useState(false);
  const [kpiCards, setKpiCards] = useState(MOCK_KPIS);
  const [trend, setTrend] = useState(MOCK_TREND);
  const [expenseBreakdown, setExpenseBreakdown] = useState(MOCK_EXPENSE_BREAKDOWN);
  const [cashflow, setCashflow] = useState(MOCK_CASHFLOW);

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch("/api/dashboard/summary");
        const data = await res.json();
        if (res.ok && data.data_points > 0) {
          const k = data.kpis;
          setKpiCards([
            { label: "Revenue (period)", value: INR(k.revenue), change: "", up: null, icon: TrendingUp, color: "text-emerald-300" },
            { label: "Expenses (period)", value: INR(k.expenses), change: "", up: null, icon: TrendingDown, color: "text-red-300" },
            { label: "Cash Position", value: INR(k.cash_position), change: "", up: null, icon: Wallet, color: "text-violet-300" },
            { label: "GST Liability", value: INR(k.gst_liability), change: "", up: null, icon: Receipt, color: "text-amber-300" },
            { label: "TDS Payable", value: INR(k.tds_payable), change: "", up: null, icon: Landmark, color: "text-amber-300" },
            { label: "Receivables", value: INR(k.receivables), change: "", up: null, icon: ArrowDownCircle, color: "text-sky-300" },
            { label: "Payables", value: INR(k.payables), change: "", up: null, icon: ArrowUpCircle, color: "text-orange-300" },
            { label: "Profit Margin", value: k.profit_margin_pct !== null ? `${k.profit_margin_pct}%` : "—", change: "", up: null, icon: PieIcon, color: "text-emerald-300" },
            { label: "Working Capital", value: INR(k.working_capital), change: "", up: null, icon: Layers, color: "text-indigo-300" },
          ] as any);
          setTrend(data.monthly_trend.map((m: any) => ({ month: m.month, revenue: m.revenue, expenses: m.expenses })));
          setCashflow(data.monthly_trend.map((m: any) => ({ month: m.month, net: m.revenue - m.expenses })));
          if (data.expense_breakdown.length > 0) {
            const palette = ["#8b5cf6", "#6366f1", "#f59e0b", "#10b981", "#64748b", "#0ea5e9"];
            setExpenseBreakdown(data.expense_breakdown.map((e: any, i: number) => ({ ...e, color: palette[i % palette.length] })));
          }
          setIsLive(true);
        }
        // If data_points is 0 (no journal entries posted yet), silently keep the demo data — no error to show, this is expected for a fresh install.
      } catch {
        // Backend unreachable — keep demo data, don't show an error on a page that's meant to just work.
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <main className="min-h-screen bg-[#0a0a12] text-slate-100 relative overflow-hidden">
      <div className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute top-[-15%] left-[5%] h-[600px] w-[600px] rounded-full bg-violet-600/15 blur-[130px]" />
        <div className="absolute bottom-[-15%] right-[5%] h-[600px] w-[600px] rounded-full bg-emerald-600/10 blur-[130px]" />
      </div>

      <div className="max-w-7xl mx-auto px-6 py-12">
        <header className="mb-8 flex items-end justify-between flex-wrap gap-3">
          <div>
            <h1 className="text-3xl font-semibold tracking-tight bg-gradient-to-r from-violet-300 to-emerald-300 bg-clip-text text-transparent">
              Dashboard
            </h1>
            <p className="text-slate-400 mt-1 text-sm">{isLive ? "Live business overview from your posted journal entries." : "Sample data shown — post journal entries via the Accounting module to go live."}</p>
          </div>
          <div className="flex items-center gap-3">
            {loading ? (
              <span className="text-xs text-slate-500 flex items-center gap-1.5"><Loader2 size={12} className="animate-spin" /> Loading...</span>
            ) : (
              <span className={`text-xs rounded-full px-3 py-1 border ${isLive ? "border-emerald-400/30 text-emerald-300" : "border-white/10 text-slate-500"}`}>{isLive ? "Live data" : "Demo data"}</span>
            )}
            <a href="/api/dashboard/export/excel" className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-emerald-600/20 border border-emerald-400/30 hover:bg-emerald-600/30 transition"><Download size={13} /> Excel</a>
            <a href="/api/dashboard/export/pdf" className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-violet-600/20 border border-violet-400/30 hover:bg-violet-600/30 transition"><FileDown size={13} /> PDF</a>
          </div>
        </header>

        {/* KPI cards */}
        <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-3 gap-4 mb-8">
          {kpiCards.map(({ label, value, change, up, icon: Icon, color }: any) => (
            <div key={label} className="rounded-2xl border border-white/10 bg-white/5 backdrop-blur-xl p-5 hover:bg-white/[0.07] transition">
              <div className="flex items-center justify-between mb-3">
                <Icon size={18} className={color} />
                {up !== null && change && (
                  <span className={`text-xs ${up ? "text-emerald-300" : "text-red-300"}`}>{change}</span>
                )}
                {up === null && change && <span className="text-xs text-amber-300">{change}</span>}
              </div>
              <div className="text-xl font-semibold">{value}</div>
              <div className="text-xs text-slate-400 mt-1">{label}</div>
            </div>
          ))}
        </div>

        {/* Charts */}
        <div className="grid lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 rounded-2xl border border-white/10 bg-white/5 backdrop-blur-xl p-6">
            <h2 className="text-sm font-medium text-slate-300 mb-4">Revenue vs Expenses (6 months)</h2>
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={trend}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                <XAxis dataKey="month" stroke="#94a3b8" fontSize={12} />
                <YAxis stroke="#94a3b8" fontSize={12} tickFormatter={(v) => `₹${v / 100000}L`} />
                <Tooltip
                  contentStyle={{ background: "#111122", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 8 }}
                  formatter={(v: number) => INR(v)}
                />
                <Line type="monotone" dataKey="revenue" stroke="#10b981" strokeWidth={2} dot={false} name="Revenue" />
                <Line type="monotone" dataKey="expenses" stroke="#f59e0b" strokeWidth={2} dot={false} name="Expenses" />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="rounded-2xl border border-white/10 bg-white/5 backdrop-blur-xl p-6">
            <h2 className="text-sm font-medium text-slate-300 mb-4">Expense Breakdown</h2>
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie data={expenseBreakdown} dataKey="value" nameKey="name" innerRadius={45} outerRadius={80} paddingAngle={2}>
                  {expenseBreakdown.map((entry, i) => <Cell key={i} fill={entry.color} />)}
                </Pie>
                <Tooltip formatter={(v: number) => INR(v)} contentStyle={{ background: "#111122", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 8 }} />
              </PieChart>
            </ResponsiveContainer>
            <div className="grid grid-cols-2 gap-1.5 mt-2 text-xs">
              {expenseBreakdown.map((e) => (
                <div key={e.name} className="flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full" style={{ background: e.color }} />
                  <span className="text-slate-400">{e.name}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="lg:col-span-3 rounded-2xl border border-white/10 bg-white/5 backdrop-blur-xl p-6">
            <h2 className="text-sm font-medium text-slate-300 mb-4">Net Cash Flow (6 months)</h2>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={cashflow}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                <XAxis dataKey="month" stroke="#94a3b8" fontSize={12} />
                <YAxis stroke="#94a3b8" fontSize={12} tickFormatter={(v) => `₹${v / 100000}L`} />
                <Tooltip formatter={(v: number) => INR(v)} contentStyle={{ background: "#111122", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 8 }} />
                <Bar dataKey="net" fill="#8b5cf6" radius={[6, 6, 0, 0]} name="Net Cash Flow" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </main>
  );
}

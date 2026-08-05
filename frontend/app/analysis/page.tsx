"use client";

import { useState } from "react";
import { TrendingUp, Percent, LineChart, Scale, Layers, GitBranch, Loader2 } from "lucide-react";

type Tab = "npv" | "irr" | "cagr" | "breakEven" | "dcf" | "scenario";

const TABS: { id: Tab; label: string; icon: any }[] = [
  { id: "npv", label: "NPV", icon: TrendingUp },
  { id: "irr", label: "IRR", icon: Percent },
  { id: "cagr", label: "CAGR", icon: LineChart },
  { id: "breakEven", label: "Break-even", icon: Scale },
  { id: "dcf", label: "DCF Valuation", icon: Layers },
  { id: "scenario", label: "Scenario Analysis", icon: GitBranch },
];

function INR(n: number) {
  return "₹" + n.toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

export default function AnalysisPage() {
  const [tab, setTab] = useState<Tab>("npv");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<any>(null);

  // Shared cash-flow input (used for NPV + IRR)
  const [cashFlows, setCashFlows] = useState("-1000,300,300,300,300,300");
  const [rate, setRate] = useState("10");

  // CAGR
  const [begVal, setBegVal] = useState("100000");
  const [endVal, setEndVal] = useState("200000");
  const [years, setYears] = useState("5");

  // Break-even
  const [fixedCosts, setFixedCosts] = useState("500000");
  const [price, setPrice] = useState("1000");
  const [varCost, setVarCost] = useState("600");

  // DCF
  const [dcfCashFlows, setDcfCashFlows] = useState("100000,110000,121000,133100,146410");
  const [discountRate, setDiscountRate] = useState("10");
  const [terminalGrowth, setTerminalGrowth] = useState("3");

  // Scenario
  const [scenarios, setScenarios] = useState([
    { name: "Best", revenue: "500000", cost: "300000", probability_pct: "30" },
    { name: "Base", revenue: "400000", cost: "300000", probability_pct: "50" },
    { name: "Worst", revenue: "300000", cost: "300000", probability_pct: "20" },
  ]);

  async function callApi(action: string, payload: any) {
    setLoading(true); setError(""); setResult(null);
    try {
      const res = await fetch("/api/analysis", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action, ...payload }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || data.error || "Request failed");
      setResult(data);
    } catch (e: any) { setError(e.message); } finally { setLoading(false); }
  }

  const parseCsv = (s: string) => s.split(",").map((x) => parseFloat(x.trim())).filter((n) => !isNaN(n));

  return (
    <main className="min-h-screen bg-[#0a0a12] text-slate-100 relative overflow-hidden">
      <div className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute top-[-10%] left-[20%] h-[500px] w-[500px] rounded-full bg-indigo-600/15 blur-[120px]" />
        <div className="absolute bottom-[-10%] right-[20%] h-[500px] w-[500px] rounded-full bg-emerald-600/15 blur-[120px]" />
      </div>

      <div className="max-w-4xl mx-auto px-6 py-12">
        <header className="mb-8">
          <h1 className="text-3xl font-semibold tracking-tight bg-gradient-to-r from-indigo-300 to-emerald-300 bg-clip-text text-transparent">
            Financial Analysis
          </h1>
          <p className="text-slate-400 mt-1 text-sm">NPV, IRR, CAGR, Break-even, DCF Valuation, and Scenario Analysis.</p>
        </header>

        <div className="flex flex-wrap gap-2 mb-6">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button key={id} onClick={() => { setTab(id); setResult(null); setError(""); }}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm border transition
                ${tab === id ? "bg-indigo-600/20 border-indigo-400/40 text-indigo-200" : "bg-white/5 border-white/10 text-slate-300 hover:bg-white/10"}`}>
              <Icon size={16} /> {label}
            </button>
          ))}
        </div>

        <div className="rounded-2xl border border-white/10 bg-white/5 backdrop-blur-xl p-6 shadow-2xl space-y-4">
          {tab === "npv" && (
            <>
              <div>
                <label className="text-xs uppercase tracking-wide text-slate-400">Cash Flows (comma-separated, period 0 first)</label>
                <input className="mt-1 w-full rounded-lg bg-black/30 border border-white/10 p-3 text-sm font-mono" value={cashFlows} onChange={(e) => setCashFlows(e.target.value)} />
              </div>
              <div>
                <label className="text-xs uppercase tracking-wide text-slate-400">Discount Rate (%)</label>
                <input className="mt-1 w-32 rounded-lg bg-black/30 border border-white/10 p-3 text-sm" value={rate} onChange={(e) => setRate(e.target.value)} />
              </div>
              <button onClick={() => callApi("npv", { rate_pct: parseFloat(rate), cash_flows: parseCsv(cashFlows) })} disabled={loading}
                className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-emerald-600 hover:from-indigo-500 hover:to-emerald-500 disabled:opacity-50 font-medium text-sm transition">
                {loading ? <Loader2 className="animate-spin" size={16} /> : <TrendingUp size={16} />} Calculate NPV
              </button>
              {result?.npv !== undefined && (
                <div className="text-sm pt-2"><span className="text-slate-400">Net Present Value: </span><span className={`font-medium ${result.npv >= 0 ? "text-emerald-300" : "text-red-300"}`}>{INR(result.npv)}</span></div>
              )}
            </>
          )}

          {tab === "irr" && (
            <>
              <div>
                <label className="text-xs uppercase tracking-wide text-slate-400">Cash Flows (comma-separated, period 0 first)</label>
                <input className="mt-1 w-full rounded-lg bg-black/30 border border-white/10 p-3 text-sm font-mono" value={cashFlows} onChange={(e) => setCashFlows(e.target.value)} />
              </div>
              <button onClick={() => callApi("irr", { cash_flows: parseCsv(cashFlows) })} disabled={loading}
                className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-emerald-600 hover:from-indigo-500 hover:to-emerald-500 disabled:opacity-50 font-medium text-sm transition">
                {loading ? <Loader2 className="animate-spin" size={16} /> : <Percent size={16} />} Calculate IRR
              </button>
              {result?.irr_pct !== undefined && (
                <div className="text-sm pt-2"><span className="text-slate-400">Internal Rate of Return: </span><span className="font-medium text-emerald-300">{result.irr_pct}%</span></div>
              )}
            </>
          )}

          {tab === "cagr" && (
            <>
              <div className="grid sm:grid-cols-3 gap-4">
                <div><label className="text-xs uppercase tracking-wide text-slate-400">Beginning Value (₹)</label>
                  <input className="mt-1 w-full rounded-lg bg-black/30 border border-white/10 p-3 text-sm" value={begVal} onChange={(e) => setBegVal(e.target.value)} /></div>
                <div><label className="text-xs uppercase tracking-wide text-slate-400">Ending Value (₹)</label>
                  <input className="mt-1 w-full rounded-lg bg-black/30 border border-white/10 p-3 text-sm" value={endVal} onChange={(e) => setEndVal(e.target.value)} /></div>
                <div><label className="text-xs uppercase tracking-wide text-slate-400">Years</label>
                  <input className="mt-1 w-full rounded-lg bg-black/30 border border-white/10 p-3 text-sm" value={years} onChange={(e) => setYears(e.target.value)} /></div>
              </div>
              <button onClick={() => callApi("cagr", { beginning_value: parseFloat(begVal), ending_value: parseFloat(endVal), years: parseFloat(years) })} disabled={loading}
                className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-emerald-600 hover:from-indigo-500 hover:to-emerald-500 disabled:opacity-50 font-medium text-sm transition">
                {loading ? <Loader2 className="animate-spin" size={16} /> : <LineChart size={16} />} Calculate CAGR
              </button>
              {result?.cagr_pct !== undefined && (
                <div className="text-sm pt-2"><span className="text-slate-400">CAGR: </span><span className="font-medium text-emerald-300">{result.cagr_pct}%</span></div>
              )}
            </>
          )}

          {tab === "breakEven" && (
            <>
              <div className="grid sm:grid-cols-3 gap-4">
                <div><label className="text-xs uppercase tracking-wide text-slate-400">Fixed Costs (₹)</label>
                  <input className="mt-1 w-full rounded-lg bg-black/30 border border-white/10 p-3 text-sm" value={fixedCosts} onChange={(e) => setFixedCosts(e.target.value)} /></div>
                <div><label className="text-xs uppercase tracking-wide text-slate-400">Price per Unit (₹)</label>
                  <input className="mt-1 w-full rounded-lg bg-black/30 border border-white/10 p-3 text-sm" value={price} onChange={(e) => setPrice(e.target.value)} /></div>
                <div><label className="text-xs uppercase tracking-wide text-slate-400">Variable Cost per Unit (₹)</label>
                  <input className="mt-1 w-full rounded-lg bg-black/30 border border-white/10 p-3 text-sm" value={varCost} onChange={(e) => setVarCost(e.target.value)} /></div>
              </div>
              <button onClick={() => callApi("breakEven", { fixed_costs: parseFloat(fixedCosts), price_per_unit: parseFloat(price), variable_cost_per_unit: parseFloat(varCost) })} disabled={loading}
                className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-emerald-600 hover:from-indigo-500 hover:to-emerald-500 disabled:opacity-50 font-medium text-sm transition">
                {loading ? <Loader2 className="animate-spin" size={16} /> : <Scale size={16} />} Calculate Break-even
              </button>
              {result?.break_even_units !== undefined && (
                <dl className="grid grid-cols-2 gap-3 text-sm pt-2">
                  <div className="flex justify-between"><dt className="text-slate-400">Contribution Margin</dt><dd>{INR(result.contribution_margin_per_unit)}/unit</dd></div>
                  <div className="flex justify-between"><dt className="text-slate-400">CM Ratio</dt><dd>{result.contribution_margin_ratio_pct}%</dd></div>
                  <div className="flex justify-between"><dt className="text-slate-400">Break-even Units</dt><dd>{result.break_even_units.toLocaleString("en-IN")}</dd></div>
                  <div className="flex justify-between"><dt className="text-slate-400">Break-even Revenue</dt><dd className="text-emerald-300">{INR(result.break_even_revenue)}</dd></div>
                </dl>
              )}
            </>
          )}

          {tab === "dcf" && (
            <>
              <div>
                <label className="text-xs uppercase tracking-wide text-slate-400">Projected Free Cash Flows (comma-separated, periods 1..n)</label>
                <input className="mt-1 w-full rounded-lg bg-black/30 border border-white/10 p-3 text-sm font-mono" value={dcfCashFlows} onChange={(e) => setDcfCashFlows(e.target.value)} />
              </div>
              <div className="grid sm:grid-cols-2 gap-4">
                <div><label className="text-xs uppercase tracking-wide text-slate-400">Discount Rate (%)</label>
                  <input className="mt-1 w-full rounded-lg bg-black/30 border border-white/10 p-3 text-sm" value={discountRate} onChange={(e) => setDiscountRate(e.target.value)} /></div>
                <div><label className="text-xs uppercase tracking-wide text-slate-400">Terminal Growth Rate (%)</label>
                  <input className="mt-1 w-full rounded-lg bg-black/30 border border-white/10 p-3 text-sm" value={terminalGrowth} onChange={(e) => setTerminalGrowth(e.target.value)} /></div>
              </div>
              <button onClick={() => callApi("dcf", { projected_cash_flows: parseCsv(dcfCashFlows), discount_rate_pct: parseFloat(discountRate), terminal_growth_rate_pct: parseFloat(terminalGrowth) })} disabled={loading}
                className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-emerald-600 hover:from-indigo-500 hover:to-emerald-500 disabled:opacity-50 font-medium text-sm transition">
                {loading ? <Loader2 className="animate-spin" size={16} /> : <Layers size={16} />} Run DCF
              </button>
              {result?.enterprise_value !== undefined && (
                <dl className="grid grid-cols-2 gap-3 text-sm pt-2">
                  <div className="flex justify-between"><dt className="text-slate-400">PV of Forecast Cash Flows</dt><dd>{INR(result.pv_of_forecast_cash_flows)}</dd></div>
                  <div className="flex justify-between"><dt className="text-slate-400">Terminal Value</dt><dd>{INR(result.terminal_value)}</dd></div>
                  <div className="flex justify-between"><dt className="text-slate-400">PV of Terminal Value</dt><dd>{INR(result.pv_of_terminal_value)}</dd></div>
                  <div className="flex justify-between col-span-2 border-t border-white/10 pt-2 font-medium"><dt>Enterprise Value</dt><dd className="text-emerald-300">{INR(result.enterprise_value)}</dd></div>
                </dl>
              )}
            </>
          )}

          {tab === "scenario" && (
            <>
              <div className="space-y-2">
                {scenarios.map((s, i) => (
                  <div key={i} className="grid grid-cols-4 gap-2">
                    <input placeholder="Name" className="rounded-lg bg-black/30 border border-white/10 px-3 py-2 text-sm" value={s.name}
                      onChange={(e) => setScenarios((prev) => prev.map((x, idx) => idx === i ? { ...x, name: e.target.value } : x))} />
                    <input placeholder="Revenue" className="rounded-lg bg-black/30 border border-white/10 px-3 py-2 text-sm" value={s.revenue}
                      onChange={(e) => setScenarios((prev) => prev.map((x, idx) => idx === i ? { ...x, revenue: e.target.value } : x))} />
                    <input placeholder="Cost" className="rounded-lg bg-black/30 border border-white/10 px-3 py-2 text-sm" value={s.cost}
                      onChange={(e) => setScenarios((prev) => prev.map((x, idx) => idx === i ? { ...x, cost: e.target.value } : x))} />
                    <input placeholder="Probability %" className="rounded-lg bg-black/30 border border-white/10 px-3 py-2 text-sm" value={s.probability_pct}
                      onChange={(e) => setScenarios((prev) => prev.map((x, idx) => idx === i ? { ...x, probability_pct: e.target.value } : x))} />
                  </div>
                ))}
              </div>
              <button onClick={() => callApi("scenarioAnalysis", {
                scenarios: scenarios.map((s) => ({ name: s.name, revenue: parseFloat(s.revenue), cost: parseFloat(s.cost), probability_pct: parseFloat(s.probability_pct) })),
              })} disabled={loading}
                className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-emerald-600 hover:from-indigo-500 hover:to-emerald-500 disabled:opacity-50 font-medium text-sm transition">
                {loading ? <Loader2 className="animate-spin" size={16} /> : <GitBranch size={16} />} Run Scenario Analysis
              </button>
              {result?.scenarios && (
                <div className="pt-2 space-y-2">
                  {result.scenarios.map((s: any, i: number) => (
                    <div key={i} className="flex justify-between text-sm"><span className="text-slate-300">{s.name} ({s.probability_pct}%)</span><span className={s.profit >= 0 ? "text-emerald-300" : "text-red-300"}>{INR(s.profit)}</span></div>
                  ))}
                  <div className="flex justify-between text-sm border-t border-white/10 pt-2 font-medium"><span>Expected Profit</span><span className="text-emerald-300">{INR(result.expected_profit)}</span></div>
                  <p className="text-xs text-slate-500">Best case: {result.best_case} · Worst case: {result.worst_case}</p>
                </div>
              )}
            </>
          )}
        </div>

        {error && <div className="mt-6 rounded-xl border border-red-400/30 bg-red-500/10 p-4 text-sm text-red-200">{error}</div>}
      </div>
    </main>
  );
}

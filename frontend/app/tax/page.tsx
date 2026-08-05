"use client";

import { useState } from "react";
import { Receipt, Landmark, Wallet, Loader2 } from "lucide-react";

type Tab = "gst" | "tds" | "incomeTax";

const TABS: { id: Tab; label: string; icon: any }[] = [
  { id: "gst", label: "GST Calculator", icon: Receipt },
  { id: "tds", label: "TDS Calculator", icon: Landmark },
  { id: "incomeTax", label: "Income Tax", icon: Wallet },
];

const TDS_SECTIONS = [
  { value: "194A", label: "194A — Interest (10%)" },
  { value: "194C", label: "194C — Contractor (1%)" },
  { value: "194H", label: "194H — Commission/Brokerage (5%)" },
  { value: "194I", label: "194I — Rent (10%)" },
  { value: "194J", label: "194J — Professional/Technical Services (10%)" },
  { value: "194Q", label: "194Q — Purchase of Goods (0.1%)" },
];

function INR(n: number) {
  return "₹" + n.toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

export default function TaxPage() {
  const [tab, setTab] = useState<Tab>("gst");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // GST state
  const [gstValue, setGstValue] = useState("10000");
  const [gstRate, setGstRate] = useState("18");
  const [interstate, setInterstate] = useState(false);
  const [gstResult, setGstResult] = useState<any>(null);

  // TDS state
  const [tdsAmount, setTdsAmount] = useState("100000");
  const [tdsSection, setTdsSection] = useState("194J");
  const [hasPan, setHasPan] = useState(true);
  const [tdsResult, setTdsResult] = useState<any>(null);

  // Income tax state
  const [salary, setSalary] = useState("1200000");
  const [otherIncome, setOtherIncome] = useState("0");
  const [taxResult, setTaxResult] = useState<any>(null);

  async function callTaxApi(action: string, payload: any) {
    const res = await fetch("/api/tax", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, ...payload }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || data.error || "Request failed");
    return data;
  }

  async function runGst() {
    setLoading(true); setError(""); setGstResult(null);
    try {
      const r = await callTaxApi("gstCalculate", {
        taxable_value: parseFloat(gstValue) || 0,
        gst_rate_pct: parseFloat(gstRate) || 0,
        is_interstate: interstate,
      });
      setGstResult(r);
    } catch (e: any) { setError(e.message); } finally { setLoading(false); }
  }

  async function runTds() {
    setLoading(true); setError(""); setTdsResult(null);
    try {
      const r = await callTaxApi("tdsCalculate", {
        amount_paid: parseFloat(tdsAmount) || 0,
        section: tdsSection,
        has_pan: hasPan,
      });
      setTdsResult(r);
    } catch (e: any) { setError(e.message); } finally { setLoading(false); }
  }

  async function runIncomeTax() {
    setLoading(true); setError(""); setTaxResult(null);
    try {
      const r = await callTaxApi("incomeTaxNewRegime", {
        gross_salary: parseFloat(salary) || 0,
        other_income: parseFloat(otherIncome) || 0,
      });
      setTaxResult(r);
    } catch (e: any) { setError(e.message); } finally { setLoading(false); }
  }

  return (
    <main className="min-h-screen bg-[#0a0a12] text-slate-100 relative overflow-hidden">
      <div className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute top-[-10%] left-[20%] h-[500px] w-[500px] rounded-full bg-amber-600/15 blur-[120px]" />
        <div className="absolute bottom-[-10%] right-[20%] h-[500px] w-[500px] rounded-full bg-violet-600/15 blur-[120px]" />
      </div>

      <div className="max-w-4xl mx-auto px-6 py-12">
        <header className="mb-8">
          <h1 className="text-3xl font-semibold tracking-tight bg-gradient-to-r from-amber-300 to-violet-300 bg-clip-text text-transparent">
            Indian Tax Module
          </h1>
          <p className="text-slate-400 mt-1 text-sm">
            GST, TDS, and Income Tax calculators. Rates reflect FY 2025-26 — always confirm against the latest CBDT/CBIC notifications before filing.
          </p>
        </header>

        <div className="flex flex-wrap gap-2 mb-6">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => { setTab(id); setError(""); }}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm border transition
                ${tab === id ? "bg-amber-600/20 border-amber-400/40 text-amber-200" : "bg-white/5 border-white/10 text-slate-300 hover:bg-white/10"}`}
            >
              <Icon size={16} /> {label}
            </button>
          ))}
        </div>

        <div className="rounded-2xl border border-white/10 bg-white/5 backdrop-blur-xl p-6 shadow-2xl space-y-4">
          {tab === "gst" && (
            <>
              <div className="grid sm:grid-cols-2 gap-4">
                <div>
                  <label className="text-xs uppercase tracking-wide text-slate-400">Taxable Value (₹)</label>
                  <input className="mt-1 w-full rounded-lg bg-black/30 border border-white/10 p-3 text-sm" value={gstValue} onChange={(e) => setGstValue(e.target.value)} />
                </div>
                <div>
                  <label className="text-xs uppercase tracking-wide text-slate-400">GST Rate (%)</label>
                  <select className="mt-1 w-full rounded-lg bg-black/30 border border-white/10 p-3 text-sm" value={gstRate} onChange={(e) => setGstRate(e.target.value)}>
                    {["0", "5", "12", "18", "28"].map((r) => <option key={r} value={r}>{r}%</option>)}
                  </select>
                </div>
              </div>
              <label className="flex items-center gap-2 text-sm text-slate-300">
                <input type="checkbox" checked={interstate} onChange={(e) => setInterstate(e.target.checked)} />
                Interstate supply (IGST applies instead of CGST+SGST)
              </label>
              <button onClick={runGst} disabled={loading} className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-amber-600 to-violet-600 hover:from-amber-500 hover:to-violet-500 disabled:opacity-50 font-medium text-sm transition">
                {loading ? <Loader2 className="animate-spin" size={16} /> : <Receipt size={16} />} Calculate GST
              </button>
              {gstResult && (
                <dl className="grid grid-cols-2 gap-3 text-sm pt-2">
                  {gstResult.igst > 0 && <div className="flex justify-between col-span-2"><dt className="text-slate-400">IGST</dt><dd>{INR(gstResult.igst)}</dd></div>}
                  {gstResult.cgst > 0 && <><div className="flex justify-between"><dt className="text-slate-400">CGST</dt><dd>{INR(gstResult.cgst)}</dd></div>
                  <div className="flex justify-between"><dt className="text-slate-400">SGST</dt><dd>{INR(gstResult.sgst)}</dd></div></>}
                  <div className="flex justify-between col-span-2 border-t border-white/10 pt-2 font-medium"><dt>Invoice Total</dt><dd className="text-amber-300">{INR(gstResult.invoice_total)}</dd></div>
                </dl>
              )}
            </>
          )}

          {tab === "tds" && (
            <>
              <div className="grid sm:grid-cols-2 gap-4">
                <div>
                  <label className="text-xs uppercase tracking-wide text-slate-400">Amount Paid (₹)</label>
                  <input className="mt-1 w-full rounded-lg bg-black/30 border border-white/10 p-3 text-sm" value={tdsAmount} onChange={(e) => setTdsAmount(e.target.value)} />
                </div>
                <div>
                  <label className="text-xs uppercase tracking-wide text-slate-400">Section</label>
                  <select className="mt-1 w-full rounded-lg bg-black/30 border border-white/10 p-3 text-sm" value={tdsSection} onChange={(e) => setTdsSection(e.target.value)}>
                    {TDS_SECTIONS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
                  </select>
                </div>
              </div>
              <label className="flex items-center gap-2 text-sm text-slate-300">
                <input type="checkbox" checked={hasPan} onChange={(e) => setHasPan(e.target.checked)} />
                Deductee has provided PAN
              </label>
              <button onClick={runTds} disabled={loading} className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-amber-600 to-violet-600 hover:from-amber-500 hover:to-violet-500 disabled:opacity-50 font-medium text-sm transition">
                {loading ? <Loader2 className="animate-spin" size={16} /> : <Landmark size={16} />} Calculate TDS
              </button>
              {tdsResult && (
                <dl className="grid grid-cols-2 gap-3 text-sm pt-2">
                  <div className="flex justify-between"><dt className="text-slate-400">Rate Applied</dt><dd>{tdsResult.rate_applied_pct}%</dd></div>
                  <div className="flex justify-between"><dt className="text-slate-400">TDS Amount</dt><dd>{INR(tdsResult.tds_amount)}</dd></div>
                  <div className="flex justify-between col-span-2 border-t border-white/10 pt-2 font-medium"><dt>Net Payment</dt><dd className="text-amber-300">{INR(tdsResult.net_payment)}</dd></div>
                  {!hasPan && <p className="col-span-2 text-xs text-red-300">No PAN → flat 20% TDS applies under Section 206AA.</p>}
                </dl>
              )}
            </>
          )}

          {tab === "incomeTax" && (
            <>
              <div className="grid sm:grid-cols-2 gap-4">
                <div>
                  <label className="text-xs uppercase tracking-wide text-slate-400">Gross Salary (₹/year)</label>
                  <input className="mt-1 w-full rounded-lg bg-black/30 border border-white/10 p-3 text-sm" value={salary} onChange={(e) => setSalary(e.target.value)} />
                </div>
                <div>
                  <label className="text-xs uppercase tracking-wide text-slate-400">Other Income (₹/year)</label>
                  <input className="mt-1 w-full rounded-lg bg-black/30 border border-white/10 p-3 text-sm" value={otherIncome} onChange={(e) => setOtherIncome(e.target.value)} />
                </div>
              </div>
              <p className="text-xs text-slate-500">New Tax Regime, FY 2025-26 — includes ₹75,000 standard deduction and Section 87A rebate (nil tax up to ₹12L taxable income).</p>
              <button onClick={runIncomeTax} disabled={loading} className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-amber-600 to-violet-600 hover:from-amber-500 hover:to-violet-500 disabled:opacity-50 font-medium text-sm transition">
                {loading ? <Loader2 className="animate-spin" size={16} /> : <Wallet size={16} />} Calculate Tax
              </button>
              {taxResult && (
                <dl className="grid grid-cols-2 gap-3 text-sm pt-2">
                  <div className="flex justify-between"><dt className="text-slate-400">Taxable Income</dt><dd>{INR(taxResult.taxable_income)}</dd></div>
                  <div className="flex justify-between"><dt className="text-slate-400">Sec 87A Rebate</dt><dd>{taxResult.rebate_87a_applied ? "Applied ✓" : "Not applicable"}</dd></div>
                  <div className="flex justify-between"><dt className="text-slate-400">Health &amp; Edu Cess (4%)</dt><dd>{INR(taxResult.health_education_cess)}</dd></div>
                  <div className="flex justify-between"><dt className="text-slate-400">Effective Rate</dt><dd>{taxResult.effective_tax_rate_pct}%</dd></div>
                  <div className="flex justify-between col-span-2 border-t border-white/10 pt-2 font-medium"><dt>Total Tax Payable</dt><dd className="text-amber-300">{INR(taxResult.total_tax_payable)}</dd></div>
                </dl>
              )}
            </>
          )}
        </div>

        {error && (
          <div className="mt-6 rounded-xl border border-red-400/30 bg-red-500/10 p-4 text-sm text-red-200">
            {error}
          </div>
        )}
      </div>
    </main>
  );
}

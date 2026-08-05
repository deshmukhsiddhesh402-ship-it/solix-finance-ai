"use client";

import { useState } from "react";
import { Plus, Trash2, Calculator, Loader2 } from "lucide-react";

type AccountType = "asset" | "liability" | "equity" | "income" | "expense";

type LedgerLine = {
  account_name: string;
  account_type: AccountType;
  debit: string;
  credit: string;
};

const ACCOUNT_TYPES: AccountType[] = ["asset", "liability", "equity", "income", "expense"];

const STARTER_LINES: LedgerLine[] = [
  { account_name: "Cash", account_type: "asset", debit: "500000", credit: "" },
  { account_name: "Capital", account_type: "equity", debit: "", credit: "500000" },
  { account_name: "Sales Revenue", account_type: "income", debit: "", credit: "180000" },
  { account_name: "Cash", account_type: "asset", debit: "180000", credit: "" },
  { account_name: "Rent Expense", account_type: "expense", debit: "30000", credit: "" },
  { account_name: "Cash", account_type: "asset", debit: "", credit: "30000" },
];

export default function AccountingPage() {
  const [lines, setLines] = useState<LedgerLine[]>(STARTER_LINES);
  const [trialBalance, setTrialBalance] = useState<any>(null);
  const [pnl, setPnl] = useState<any>(null);
  const [balanceSheet, setBalanceSheet] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  function updateLine(i: number, patch: Partial<LedgerLine>) {
    setLines((prev) => prev.map((l, idx) => (idx === i ? { ...l, ...patch } : l)));
  }

  function addLine() {
    setLines((prev) => [...prev, { account_name: "", account_type: "asset", debit: "", credit: "" }]);
  }

  function removeLine(i: number) {
    setLines((prev) => prev.filter((_, idx) => idx !== i));
  }

  async function callAccountingApi(action: string, payload: any) {
    const res = await fetch("/api/accounting", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, ...payload }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || data.error || "Request failed");
    return data;
  }

  async function runFullBooks() {
    setLoading(true);
    setError("");
    setTrialBalance(null);
    setPnl(null);
    setBalanceSheet(null);
    try {
      const payload = {
        lines: lines
          .filter((l) => l.account_name)
          .map((l) => ({
            account_name: l.account_name,
            account_type: l.account_type,
            debit: parseFloat(l.debit) || 0,
            credit: parseFloat(l.credit) || 0,
          })),
      };
      const tb = await callAccountingApi("trialBalance", payload);
      setTrialBalance(tb);
      const p = await callAccountingApi("profitAndLoss", payload);
      setPnl(p);
      const bs = await callAccountingApi("balanceSheet", payload);
      setBalanceSheet(bs);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-[#0a0a12] text-slate-100 relative overflow-hidden">
      <div className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute top-[-10%] left-[15%] h-[500px] w-[500px] rounded-full bg-emerald-600/15 blur-[120px]" />
        <div className="absolute bottom-[-10%] right-[15%] h-[500px] w-[500px] rounded-full bg-violet-600/15 blur-[120px]" />
      </div>

      <div className="max-w-6xl mx-auto px-6 py-12">
        <header className="mb-8">
          <h1 className="text-3xl font-semibold tracking-tight bg-gradient-to-r from-emerald-300 to-violet-300 bg-clip-text text-transparent">
            Accounting Core
          </h1>
          <p className="text-slate-400 mt-1 text-sm">
            Enter journal lines → get an instant Trial Balance, Profit &amp; Loss, and Balance Sheet.
          </p>
        </header>

        {/* Journal entry table */}
        <div className="rounded-2xl border border-white/10 bg-white/5 backdrop-blur-xl p-6 shadow-2xl mb-6">
          <div className="grid grid-cols-12 gap-2 text-xs uppercase tracking-wide text-slate-400 mb-2 px-1">
            <div className="col-span-4">Account name</div>
            <div className="col-span-3">Type</div>
            <div className="col-span-2">Debit (₹)</div>
            <div className="col-span-2">Credit (₹)</div>
            <div className="col-span-1"></div>
          </div>

          <div className="space-y-2">
            {lines.map((l, i) => (
              <div key={i} className="grid grid-cols-12 gap-2">
                <input
                  className="col-span-4 rounded-lg bg-black/30 border border-white/10 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/40"
                  value={l.account_name}
                  placeholder="e.g. Cash"
                  onChange={(e) => updateLine(i, { account_name: e.target.value })}
                />
                <select
                  className="col-span-3 rounded-lg bg-black/30 border border-white/10 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/40"
                  value={l.account_type}
                  onChange={(e) => updateLine(i, { account_type: e.target.value as AccountType })}
                >
                  {ACCOUNT_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
                </select>
                <input
                  className="col-span-2 rounded-lg bg-black/30 border border-white/10 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/40"
                  value={l.debit}
                  placeholder="0"
                  onChange={(e) => updateLine(i, { debit: e.target.value })}
                />
                <input
                  className="col-span-2 rounded-lg bg-black/30 border border-white/10 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/40"
                  value={l.credit}
                  placeholder="0"
                  onChange={(e) => updateLine(i, { credit: e.target.value })}
                />
                <button onClick={() => removeLine(i)} className="col-span-1 flex items-center justify-center text-slate-500 hover:text-red-400 transition">
                  <Trash2 size={16} />
                </button>
              </div>
            ))}
          </div>

          <div className="flex items-center gap-3 mt-4">
            <button
              onClick={addLine}
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-white/5 border border-white/10 hover:bg-white/10 text-sm transition"
            >
              <Plus size={16} /> Add line
            </button>
            <button
              onClick={runFullBooks}
              disabled={loading}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-emerald-600 to-violet-600
                         hover:from-emerald-500 hover:to-violet-500 disabled:opacity-50 font-medium text-sm transition"
            >
              {loading ? <Loader2 className="animate-spin" size={16} /> : <Calculator size={16} />}
              {loading ? "Calculating..." : "Generate Books"}
            </button>
          </div>
        </div>

        {error && (
          <div className="rounded-xl border border-red-400/30 bg-red-500/10 p-4 text-sm text-red-200 mb-6">
            {error}
          </div>
        )}

        {/* Results */}
        {(trialBalance || pnl || balanceSheet) && (
          <div className="grid md:grid-cols-3 gap-6">
            {trialBalance && (
              <div className="rounded-2xl border border-white/10 bg-white/5 backdrop-blur-xl p-5">
                <h2 className="text-sm font-medium text-emerald-300 mb-3">Trial Balance</h2>
                <table className="w-full text-xs">
                  <thead className="text-slate-400">
                    <tr><th className="text-left pb-2">Account</th><th className="text-right pb-2">Dr</th><th className="text-right pb-2">Cr</th></tr>
                  </thead>
                  <tbody>
                    {trialBalance.rows.map((r: any, idx: number) => (
                      <tr key={idx} className="border-t border-white/5">
                        <td className="py-1.5">{r.account}</td>
                        <td className="py-1.5 text-right">{r.debit ? r.debit.toLocaleString("en-IN") : ""}</td>
                        <td className="py-1.5 text-right">{r.credit ? r.credit.toLocaleString("en-IN") : ""}</td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot>
                    <tr className="border-t border-white/20 font-medium">
                      <td className="py-2">Total</td>
                      <td className="py-2 text-right">{trialBalance.total_debit.toLocaleString("en-IN")}</td>
                      <td className="py-2 text-right">{trialBalance.total_credit.toLocaleString("en-IN")}</td>
                    </tr>
                  </tfoot>
                </table>
              </div>
            )}

            {pnl && (
              <div className="rounded-2xl border border-white/10 bg-white/5 backdrop-blur-xl p-5">
                <h2 className="text-sm font-medium text-violet-300 mb-3">Profit &amp; Loss</h2>
                <dl className="text-xs space-y-2">
                  <div className="flex justify-between"><dt className="text-slate-400">Total Income</dt><dd>₹{pnl.total_income.toLocaleString("en-IN")}</dd></div>
                  <div className="flex justify-between"><dt className="text-slate-400">Total Expense</dt><dd>₹{pnl.total_expense.toLocaleString("en-IN")}</dd></div>
                  <div className="flex justify-between border-t border-white/10 pt-2 font-medium">
                    <dt>Net Profit</dt><dd className={pnl.net_profit >= 0 ? "text-emerald-300" : "text-red-300"}>₹{pnl.net_profit.toLocaleString("en-IN")}</dd>
                  </div>
                </dl>
              </div>
            )}

            {balanceSheet && (
              <div className="rounded-2xl border border-white/10 bg-white/5 backdrop-blur-xl p-5">
                <h2 className="text-sm font-medium text-indigo-300 mb-3">Balance Sheet</h2>
                <dl className="text-xs space-y-2">
                  <div className="flex justify-between"><dt className="text-slate-400">Total Assets</dt><dd>₹{balanceSheet.total_assets.toLocaleString("en-IN")}</dd></div>
                  <div className="flex justify-between"><dt className="text-slate-400">Total Liabilities</dt><dd>₹{balanceSheet.total_liabilities.toLocaleString("en-IN")}</dd></div>
                  <div className="flex justify-between"><dt className="text-slate-400">Total Equity</dt><dd>₹{balanceSheet.total_equity.toLocaleString("en-IN")}</dd></div>
                  <div className="flex justify-between border-t border-white/10 pt-2 font-medium">
                    <dt>Balances?</dt>
                    <dd className={balanceSheet.balances ? "text-emerald-300" : "text-red-300"}>{balanceSheet.balances ? "Yes ✓" : "No ✗"}</dd>
                  </div>
                </dl>
              </div>
            )}
          </div>
        )}
      </div>
    </main>
  );
}

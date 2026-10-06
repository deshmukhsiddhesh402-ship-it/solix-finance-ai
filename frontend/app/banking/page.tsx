"use client";

import { useState } from "react";
import { Plus, Trash2, Landmark, Loader2 } from "lucide-react";

type TxnType = "credit" | "debit";
type Mode = "NEFT" | "RTGS" | "IMPS" | "UPI" | "CHEQUE" | "";

type BankRow = { id: string; txn_date: string; description: string; amount: string; txn_type: TxnType; mode: Mode };
type BookRow = { id: string; txn_date: string; description: string; amount: string; txn_type: TxnType };

const STARTER_BANK: BankRow[] = [
  { id: "b1", txn_date: "2026-07-01", description: "NEFT from Client A", amount: "50000", txn_type: "credit", mode: "NEFT" },
  { id: "b2", txn_date: "2026-07-03", description: "Rent payment", amount: "20000", txn_type: "debit", mode: "RTGS" },
  { id: "b3", txn_date: "2026-07-05", description: "Bank charges", amount: "500", txn_type: "debit", mode: "" },
];

const STARTER_BOOK: BookRow[] = [
  { id: "j1", txn_date: "2026-07-01", description: "Client A payment received", amount: "50000", txn_type: "credit" },
  { id: "j2", txn_date: "2026-07-02", description: "Rent paid", amount: "20000", txn_type: "debit" },
  { id: "j3", txn_date: "2026-07-06", description: "Cheque issued to supplier", amount: "15000", txn_type: "debit" },
];

const MODES: Mode[] = ["NEFT", "RTGS", "IMPS", "UPI", "CHEQUE", ""];

function INR(n: number) {
  return "₹" + n.toLocaleString("en-IN");
}

export default function BankingPage() {
  const [bankRows, setBankRows] = useState<BankRow[]>(STARTER_BANK);
  const [bookRows, setBookRows] = useState<BookRow[]>(STARTER_BOOK);
  const [balanceAsPerBank, setBalanceAsPerBank] = useState("100000");
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  function newId(prefix: string) {
    return `${prefix}${Date.now()}${Math.floor(Math.random() * 1000)}`;
  }

  async function runReconciliation() {
    setLoading(true); setError(""); setResult(null);
    try {
      const res = await fetch("/api/banking", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "reconcile",
          balance_as_per_bank: parseFloat(balanceAsPerBank) || 0,
          bank_lines: bankRows.map((r) => ({ ...r, amount: parseFloat(r.amount) || 0 })),
          book_lines: bookRows.map((r) => ({ ...r, amount: parseFloat(r.amount) || 0 })),
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || data.error || "Request failed");
      setResult(data);
    } catch (e: any) { setError(e.message); } finally { setLoading(false); }
  }

  return (
    <main className="min-h-screen bg-[#0a0a12] text-slate-100 relative overflow-hidden">
      <div className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute top-[-10%] left-[15%] h-[500px] w-[500px] rounded-full bg-sky-600/15 blur-[120px]" />
        <div className="absolute bottom-[-10%] right-[15%] h-[500px] w-[500px] rounded-full bg-violet-600/15 blur-[120px]" />
      </div>

      <div className="max-w-6xl mx-auto px-6 py-12">
        <header className="mb-8">
          <h1 className="text-3xl font-semibold tracking-tight bg-gradient-to-r from-sky-300 to-violet-300 bg-clip-text text-transparent">
            Banking &amp; Reconciliation
          </h1>
          <p className="text-slate-400 mt-1 text-sm">
            Match your bank statement against your books — matched by amount + transaction type within a 5-day window.
          </p>
        </header>

        <div className="grid lg:grid-cols-2 gap-6 mb-6">
          {/* Bank statement */}
          <div className="rounded-2xl border border-white/10 bg-white/5 backdrop-blur-xl p-5">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-medium text-sky-300">Bank Statement</h2>
              <button
                onClick={() => setBankRows((r) => [...r, { id: newId("b"), txn_date: "", description: "", amount: "", txn_type: "credit", mode: "" }])}
                className="text-xs flex items-center gap-1 text-slate-400 hover:text-sky-300"
              >
                <Plus size={14} /> Add
              </button>
            </div>
            <div className="space-y-2">
              {bankRows.map((r, i) => (
                <div key={r.id} className="grid grid-cols-12 gap-1.5 items-center">
                  <input type="date" className="col-span-3 rounded-lg bg-black/30 border border-white/10 px-2 py-1.5 text-xs" value={r.txn_date}
                    onChange={(e) => setBankRows((rows) => rows.map((x, idx) => idx === i ? { ...x, txn_date: e.target.value } : x))} />
                  <input placeholder="Description" className="col-span-4 rounded-lg bg-black/30 border border-white/10 px-2 py-1.5 text-xs" value={r.description}
                    onChange={(e) => setBankRows((rows) => rows.map((x, idx) => idx === i ? { ...x, description: e.target.value } : x))} />
                  <input placeholder="Amt" className="col-span-2 rounded-lg bg-black/30 border border-white/10 px-2 py-1.5 text-xs" value={r.amount}
                    onChange={(e) => setBankRows((rows) => rows.map((x, idx) => idx === i ? { ...x, amount: e.target.value } : x))} />
                  <select className="col-span-2 rounded-lg bg-black/30 border border-white/10 px-1 py-1.5 text-xs" value={r.txn_type}
                    onChange={(e) => setBankRows((rows) => rows.map((x, idx) => idx === i ? { ...x, txn_type: e.target.value as TxnType } : x))}>
                    <option value="credit">Cr</option><option value="debit">Dr</option>
                  </select>
                  <button onClick={() => setBankRows((rows) => rows.filter((_, idx) => idx !== i))} className="col-span-1 text-slate-500 hover:text-red-400"><Trash2 size={14} /></button>
                </div>
              ))}
            </div>
          </div>

          {/* Books */}
          <div className="rounded-2xl border border-white/10 bg-white/5 backdrop-blur-xl p-5">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-medium text-violet-300">Book (Cash/Bank Ledger)</h2>
              <button
                onClick={() => setBookRows((r) => [...r, { id: newId("j"), txn_date: "", description: "", amount: "", txn_type: "credit" }])}
                className="text-xs flex items-center gap-1 text-slate-400 hover:text-violet-300"
              >
                <Plus size={14} /> Add
              </button>
            </div>
            <div className="space-y-2">
              {bookRows.map((r, i) => (
                <div key={r.id} className="grid grid-cols-12 gap-1.5 items-center">
                  <input type="date" className="col-span-3 rounded-lg bg-black/30 border border-white/10 px-2 py-1.5 text-xs" value={r.txn_date}
                    onChange={(e) => setBookRows((rows) => rows.map((x, idx) => idx === i ? { ...x, txn_date: e.target.value } : x))} />
                  <input placeholder="Description" className="col-span-5 rounded-lg bg-black/30 border border-white/10 px-2 py-1.5 text-xs" value={r.description}
                    onChange={(e) => setBookRows((rows) => rows.map((x, idx) => idx === i ? { ...x, description: e.target.value } : x))} />
                  <input placeholder="Amt" className="col-span-2 rounded-lg bg-black/30 border border-white/10 px-2 py-1.5 text-xs" value={r.amount}
                    onChange={(e) => setBookRows((rows) => rows.map((x, idx) => idx === i ? { ...x, amount: e.target.value } : x))} />
                  <select className="col-span-1 rounded-lg bg-black/30 border border-white/10 px-1 py-1.5 text-xs" value={r.txn_type}
                    onChange={(e) => setBookRows((rows) => rows.map((x, idx) => idx === i ? { ...x, txn_type: e.target.value as TxnType } : x))}>
                    <option value="credit">Cr</option><option value="debit">Dr</option>
                  </select>
                  <button onClick={() => setBookRows((rows) => rows.filter((_, idx) => idx !== i))} className="col-span-1 text-slate-500 hover:text-red-400"><Trash2 size={14} /></button>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="rounded-2xl border border-white/10 bg-white/5 backdrop-blur-xl p-5 mb-6 flex items-center gap-4 flex-wrap">
          <div>
            <label className="text-xs uppercase tracking-wide text-slate-400">Balance as per Bank Statement (₹)</label>
            <input className="mt-1 w-48 rounded-lg bg-black/30 border border-white/10 px-3 py-2 text-sm" value={balanceAsPerBank} onChange={(e) => setBalanceAsPerBank(e.target.value)} />
          </div>
          <button onClick={runReconciliation} disabled={loading}
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-sky-600 to-violet-600 hover:from-sky-500 hover:to-violet-500 disabled:opacity-50 font-medium text-sm transition self-end">
            {loading ? <Loader2 className="animate-spin" size={16} /> : <Landmark size={16} />} Reconcile
          </button>
        </div>

        {error && <div className="rounded-xl border border-red-400/30 bg-red-500/10 p-4 text-sm text-red-200 mb-6">{error}</div>}

        {result && (
          <div className="grid lg:grid-cols-2 gap-6">
            <div className="rounded-2xl border border-white/10 bg-white/5 backdrop-blur-xl p-5">
              <h2 className="text-sm font-medium text-emerald-300 mb-3">Matched ({result.matched_count})</h2>
              <ul className="text-xs space-y-1.5">
                {result.matched.map((m: any, i: number) => (
                  <li key={i} className="flex justify-between text-slate-300">
                    <span>{m.txn_type === "credit" ? "Cr" : "Dr"} · {m.bank_date}</span>
                    <span>{INR(m.amount)}</span>
                  </li>
                ))}
                {result.matched.length === 0 && <li className="text-slate-500">No matches found.</li>}
              </ul>

              <h2 className="text-sm font-medium text-orange-300 mt-4 mb-2">Outstanding Cheques (in books, not yet in bank)</h2>
              <ul className="text-xs space-y-1.5">
                {result.outstanding_cheques.map((c: any) => (
                  <li key={c.id} className="flex justify-between text-slate-300"><span>{c.description}</span><span>{INR(c.amount)}</span></li>
                ))}
                {result.outstanding_cheques.length === 0 && <li className="text-slate-500">None</li>}
              </ul>

              <h2 className="text-sm font-medium text-sky-300 mt-4 mb-2">Deposits Not Yet Credited</h2>
              <ul className="text-xs space-y-1.5">
                {result.deposits_not_credited.map((c: any) => (
                  <li key={c.id} className="flex justify-between text-slate-300"><span>{c.description}</span><span>{INR(c.amount)}</span></li>
                ))}
                {result.deposits_not_credited.length === 0 && <li className="text-slate-500">None</li>}
              </ul>

              <h2 className="text-sm font-medium text-amber-300 mt-4 mb-2">Bank-only Items (not yet in books)</h2>
              <ul className="text-xs space-y-1.5">
                {result.bank_only_items.map((c: any) => (
                  <li key={c.id} className="flex justify-between text-slate-300"><span>{c.description} {c.mode && `(${c.mode})`}</span><span>{c.txn_type === "debit" ? "-" : "+"}{INR(c.amount)}</span></li>
                ))}
                {result.bank_only_items.length === 0 && <li className="text-slate-500">None</li>}
              </ul>
            </div>

            <div className="rounded-2xl border border-white/10 bg-white/5 backdrop-blur-xl p-5">
              <h2 className="text-sm font-medium text-violet-300 mb-3">Bank Reconciliation Statement</h2>
              <dl className="text-sm space-y-2">
                <div className="flex justify-between"><dt className="text-slate-400">Balance as per Bank Statement</dt><dd>{INR(result.reconciliation_statement.balance_as_per_bank)}</dd></div>
                <div className="flex justify-between"><dt className="text-slate-400">Add: Deposits not yet credited</dt><dd>+{INR(result.reconciliation_statement.add_deposits_not_credited)}</dd></div>
                <div className="flex justify-between"><dt className="text-slate-400">Less: Outstanding cheques</dt><dd>-{INR(result.reconciliation_statement.less_outstanding_cheques)}</dd></div>
                <div className="flex justify-between border-t border-white/10 pt-2 font-medium"><dt>Balance as per Books</dt><dd className="text-violet-300">{INR(result.reconciliation_statement.balance_as_per_books)}</dd></div>
              </dl>
              <p className="text-xs text-slate-500 mt-4">Note: bank-only items (e.g. bank charges) aren&apos;t yet in your books — post a journal entry for them so both sides eventually match exactly.</p>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}

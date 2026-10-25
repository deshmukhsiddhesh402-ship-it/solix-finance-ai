"use client";

import { useState } from "react";
import { BookOpen, Calculator, CheckCircle2, CircleAlert, Plus, RotateCcw, Trash2, Wallet } from "lucide-react";

type Mode = "journal-entry" | "accounting-cycle" | "cash-book";
type JournalLine = { account: string; debit: string; credit: string };

const STARTER_LINES: JournalLine[] = [
  { account: "Cash", debit: "1000.00", credit: "" },
  { account: "Owner's Capital", debit: "", credit: "1000.00" },
];

const inputClass =
  "w-full min-w-0 rounded-xl border border-white/10 bg-slate-950/70 px-3 py-2.5 text-sm text-slate-100 outline-none transition focus:border-teal-400/70 focus:ring-2 focus:ring-teal-400/15 placeholder:text-slate-600";
const labelClass = "mb-1.5 block text-xs font-medium text-slate-400";

function formatMoney(value: unknown) {
  const amount = Number(value);
  if (!Number.isFinite(amount)) return String(value ?? "—");
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR" }).format(amount);
}

export default function AccountingSimulatorPage() {
  const [mode, setMode] = useState<Mode>("journal-entry");
  const [narration, setNarration] = useState("Introduced capital in cash");
  const [lines, setLines] = useState<JournalLine[]>(STARTER_LINES);
  const [openingBalance, setOpeningBalance] = useState("5000.00");
  const [receiptDescription, setReceiptDescription] = useState("Cash sales");
  const [receiptAmount, setReceiptAmount] = useState("1500.00");
  const [paymentDescription, setPaymentDescription] = useState("Office expenses");
  const [paymentAmount, setPaymentAmount] = useState("450.00");
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const debitTotal = lines.reduce((sum, line) => sum + (Number(line.debit) || 0), 0);
  const creditTotal = lines.reduce((sum, line) => sum + (Number(line.credit) || 0), 0);
  const isJournalMode = mode !== "cash-book";

  function updateLine(index: number, patch: Partial<JournalLine>) {
    setLines((current) => current.map((line, i) => (i === index ? { ...line, ...patch } : line)));
  }

  function resetPractice() {
    setNarration("Introduced capital in cash");
    setLines(STARTER_LINES);
    setOpeningBalance("5000.00");
    setReceiptDescription("Cash sales");
    setReceiptAmount("1500.00");
    setPaymentDescription("Office expenses");
    setPaymentAmount("450.00");
    setResult(null);
    setError("");
  }

  async function runPractice() {
    setLoading(true);
    setError("");
    setResult(null);

    const journalEntry = {
      narration,
      lines: lines.map((line) => ({
        account: line.account.trim(),
        debit: line.debit.trim() || "0",
        credit: line.credit.trim() || "0",
      })),
    };

    let action = mode;
    let payload: Record<string, unknown>;
    if (mode === "cash-book") {
      payload = {
        opening_balance: openingBalance || "0",
        receipts: receiptAmount.trim()
          ? [{ description: receiptDescription.trim(), amount: receiptAmount.trim() }]
          : [],
        payments: paymentAmount.trim()
          ? [{ description: paymentDescription.trim(), amount: paymentAmount.trim() }]
          : [],
      };
    } else if (mode === "accounting-cycle") {
      payload = { entries: [journalEntry] };
    } else {
      payload = journalEntry;
    }

    try {
      const response = await fetch("/api/accounting-simulator", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-solix-simulator-action": action,
        },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok) {
        const detail = data?.detail;
        throw new Error(Array.isArray(detail) ? detail.map((item: { msg?: string }) => item.msg).join("; ") : detail || "Practice calculation failed.");
      }
      setResult(data as Record<string, unknown>);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="relative min-h-screen overflow-hidden bg-[#080d18] px-4 py-6 text-slate-100 sm:px-6 sm:py-10">
      <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
        <div className="absolute -left-24 top-12 h-72 w-72 rounded-full bg-teal-500/10 blur-[100px]" />
        <div className="absolute -right-20 top-72 h-80 w-80 rounded-full bg-violet-500/10 blur-[110px]" />
      </div>

      <div className="relative mx-auto max-w-6xl">
        <header className="mb-8 flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
          <div>
            <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-teal-400/20 bg-teal-400/5 px-3 py-1.5 text-xs font-medium text-teal-200">
              <span className="h-1.5 w-1.5 rounded-full bg-teal-300" />
              SOLIX · LEARNING LAB
            </div>
            <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">Accounting Simulator</h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">
              Practise journal entries, follow the accounting cycle, and understand cash-book balances with deterministic calculations.
            </p>
          </div>
          <button onClick={resetPractice} type="button" className="inline-flex min-h-10 items-center justify-center gap-2 self-start rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm text-slate-300 transition hover:bg-white/10 sm:self-auto">
            <RotateCcw size={15} /> Reset example
          </button>
        </header>

        <section className="mb-6 rounded-2xl border border-amber-300/20 bg-amber-200/[0.04] p-4">
          <div className="flex items-start gap-3">
            <BookOpen className="mt-0.5 shrink-0 text-amber-200" size={18} />
            <div>
              <p className="text-sm font-semibold text-amber-100">Practice mode only</p>
              <p className="mt-1 text-xs leading-5 text-slate-400">
                Results are calculated for learning and are not saved, posted to a company ledger, or a substitute for professional review.
              </p>
            </div>
          </div>
        </section>

        <div className="grid gap-6 lg:grid-cols-[minmax(0,1.2fr)_minmax(320px,0.8fr)]">
          <section className="min-w-0 rounded-2xl border border-white/10 bg-white/[0.035] p-4 shadow-2xl sm:p-6">
            <div className="mb-5 grid grid-cols-3 gap-2" role="tablist" aria-label="Practice type">
              {([
                { id: "journal-entry", label: "Journal Entry", icon: BookOpen },
                { id: "accounting-cycle", label: "Accounting Cycle", icon: Calculator },
                { id: "cash-book", label: "Cash Book", icon: Wallet },
              ] as const).map((tab) => {
                const Icon = tab.icon;
                const active = mode === tab.id;
                return (
                  <button
                    key={tab.id}
                    role="tab"
                    aria-selected={active}
                    onClick={() => { setMode(tab.id); setResult(null); setError(""); }}
                    className={`flex min-h-16 flex-col items-center justify-center gap-1.5 rounded-xl border px-2 py-2 text-center text-[11px] font-medium transition sm:flex-row sm:text-xs ${active ? "border-teal-300/40 bg-teal-300/10 text-teal-100" : "border-white/10 bg-slate-950/40 text-slate-400 hover:bg-white/5"}`}
                  >
                    <Icon size={16} /> {tab.label}
                  </button>
                );
              })}
            </div>

            {isJournalMode ? (
              <>
                <div className="mb-5">
                  <label htmlFor="narration" className={labelClass}>Narration / explanation</label>
                  <input id="narration" className={inputClass} maxLength={500} value={narration} onChange={(event) => setNarration(event.target.value)} placeholder="Why is this entry recorded?" />
                </div>

                <div className="mb-3 flex items-center justify-between gap-3">
                  <h2 className="text-sm font-semibold text-slate-100">Journal lines</h2>
                  <button type="button" onClick={() => setLines((current) => current.length < 100 ? [...current, { account: "", debit: "", credit: "" }] : current)} disabled={lines.length >= 100} className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 px-3 py-2 text-xs text-slate-300 hover:bg-white/5 disabled:opacity-40">
                    <Plus size={14} /> Add line
                  </button>
                </div>

                <div className="space-y-3">
                  {lines.map((line, index) => (
                    <div key={index} className="grid grid-cols-1 gap-2 rounded-xl border border-white/[0.07] bg-slate-950/40 p-3 sm:grid-cols-[minmax(0,1fr)_110px_110px_32px] sm:items-end">
                      <div>
                        <label className={labelClass}>Account</label>
                        <input aria-label={`Account on line ${index + 1}`} className={inputClass} maxLength={120} value={line.account} onChange={(event) => updateLine(index, { account: event.target.value })} placeholder="e.g. Cash" />
                      </div>
                      <div>
                        <label className={labelClass}>Debit ₹</label>
                        <input aria-label={`Debit on line ${index + 1}`} className={inputClass} type="number" min="0" step="0.01" value={line.debit} onChange={(event) => updateLine(index, { debit: event.target.value, credit: event.target.value ? "" : line.credit })} placeholder="0.00" />
                      </div>
                      <div>
                        <label className={labelClass}>Credit ₹</label>
                        <input aria-label={`Credit on line ${index + 1}`} className={inputClass} type="number" min="0" step="0.01" value={line.credit} onChange={(event) => updateLine(index, { credit: event.target.value, debit: event.target.value ? "" : line.debit })} placeholder="0.00" />
                      </div>
                      <button type="button" aria-label={`Remove line ${index + 1}`} disabled={lines.length <= 2} onClick={() => setLines((current) => current.filter((_, i) => i !== index))} className="flex h-10 items-center justify-center rounded-lg text-slate-500 hover:bg-rose-400/10 hover:text-rose-300 disabled:opacity-20">
                        <Trash2 size={15} />
                      </button>
                    </div>
                  ))}
                </div>

                <div className="mt-5 grid grid-cols-2 gap-3">
                  <div className="rounded-xl border border-white/10 bg-slate-950/40 p-3">
                    <p className="text-xs text-slate-500">Total debit</p>
                    <p className="mt-1 text-lg font-semibold tabular-nums">{formatMoney(debitTotal)}</p>
                  </div>
                  <div className="rounded-xl border border-white/10 bg-slate-950/40 p-3">
                    <p className="text-xs text-slate-500">Total credit</p>
                    <p className="mt-1 text-lg font-semibold tabular-nums">{formatMoney(creditTotal)}</p>
                  </div>
                </div>
                <p className={`mt-3 text-xs ${Math.abs(debitTotal - creditTotal) < 0.005 ? "text-teal-300" : "text-amber-200"}`}>
                  {Math.abs(debitTotal - creditTotal) < 0.005 ? "Totals currently balance. Submit to validate the entry." : `Difference: ${formatMoney(Math.abs(debitTotal - creditTotal))} · check both sides before submitting.`}
                </p>
              </>
            ) : (
              <div className="space-y-4">
                <div>
                  <label htmlFor="opening" className={labelClass}>Opening cash balance (₹)</label>
                  <input id="opening" className={inputClass} type="number" min="0" step="0.01" value={openingBalance} onChange={(event) => setOpeningBalance(event.target.value)} />
                </div>
                <div className="rounded-xl border border-teal-300/15 bg-teal-300/[0.04] p-4">
                  <h2 className="mb-3 text-sm font-semibold text-teal-100">Receipt</h2>
                  <label htmlFor="receipt-description" className={labelClass}>Description</label>
                  <input id="receipt-description" className={inputClass + " mb-3"} maxLength={160} value={receiptDescription} onChange={(event) => setReceiptDescription(event.target.value)} />
                  <label htmlFor="receipt-amount" className={labelClass}>Amount (₹) · leave blank to skip</label>
                  <input id="receipt-amount" className={inputClass} type="number" min="0.01" step="0.01" value={receiptAmount} onChange={(event) => setReceiptAmount(event.target.value)} />
                </div>
                <div className="rounded-xl border border-violet-300/15 bg-violet-300/[0.04] p-4">
                  <h2 className="mb-3 text-sm font-semibold text-violet-100">Payment</h2>
                  <label htmlFor="payment-description" className={labelClass}>Description</label>
                  <input id="payment-description" className={inputClass + " mb-3"} maxLength={160} value={paymentDescription} onChange={(event) => setPaymentDescription(event.target.value)} />
                  <label htmlFor="payment-amount" className={labelClass}>Amount (₹) · leave blank to skip</label>
                  <input id="payment-amount" className={inputClass} type="number" min="0.01" step="0.01" value={paymentAmount} onChange={(event) => setPaymentAmount(event.target.value)} />
                </div>
              </div>
            )}

            {error && (
              <div role="alert" className="mt-5 flex items-start gap-2 rounded-xl border border-rose-400/20 bg-rose-400/[0.06] p-3 text-sm text-rose-200">
                <CircleAlert className="mt-0.5 shrink-0" size={16} /> <span>{error}</span>
              </div>
            )}

            <button onClick={runPractice} disabled={loading} type="button" className="mt-6 inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-xl bg-teal-300 px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-teal-200 disabled:cursor-not-allowed disabled:opacity-60">
              {loading ? <span className="animate-spin">◌</span> : <Calculator size={17} />}
              {loading ? "Calculating…" : mode === "journal-entry" ? "Validate journal entry" : mode === "accounting-cycle" ? "Run accounting cycle" : "Calculate cash book"}
            </button>
          </section>

          <aside className="min-w-0 rounded-2xl border border-white/10 bg-white/[0.035] p-4 sm:p-6">
            <div className="mb-5 flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-teal-300/20 bg-teal-300/10 text-teal-200">
                <Calculator size={19} />
              </div>
              <div>
                <h2 className="font-semibold">Calculation results</h2>
                <p className="mt-0.5 text-xs text-slate-500">Returned by the Solix accounting engine</p>
              </div>
            </div>

            {!result && !error && (
              <div className="flex min-h-64 flex-col items-center justify-center rounded-xl border border-dashed border-white/10 px-5 text-center">
                <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-white/5 text-slate-500"><BookOpen size={21} /></div>
                <p className="text-sm font-medium text-slate-300">Your results will appear here</p>
                <p className="mt-2 max-w-xs text-xs leading-5 text-slate-500">Edit the example or enter your own figures, then run a practice calculation.</p>
              </div>
            )}

            {result && (
              <div className="space-y-4">
                <div className="flex items-start gap-2 rounded-xl border border-teal-300/20 bg-teal-300/[0.06] p-3">
                  <CheckCircle2 size={17} className="mt-0.5 shrink-0 text-teal-300" />
                  <div>
                    <p className="text-sm font-semibold text-teal-100">Calculation completed</p>
                    <p className="mt-1 text-xs leading-5 text-slate-400">Practice result only. No records were saved or posted.</p>
                  </div>
                </div>
                {Object.entries(result).filter(([key]) => key !== "mode" && key !== "persisted").map(([key, value]) => (
                  <div key={key} className="rounded-xl border border-white/10 bg-slate-950/50 p-3">
                    <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">{key.replaceAll("_", " ")}</p>
                    {typeof value === "object" && value !== null ? (
                      <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-words text-xs leading-5 text-slate-300">{JSON.stringify(value, null, 2)}</pre>
                    ) : (
                      <p className="break-words text-sm text-slate-100">{String(value)}</p>
                    )}
                  </div>
                ))}
                <div className="rounded-xl border border-white/10 bg-white/[0.025] p-3 text-xs leading-5 text-slate-500">
                  <span className="font-medium text-slate-300">Engine status:</span> {String(result.mode || "practice_only")} · Persisted: {String(result.persisted ?? false)}
                </div>
              </div>
            )}

            <div className="mt-6 border-t border-white/10 pt-5">
              <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-400">What you can practise</h3>
              <ul className="space-y-2.5 text-xs leading-5 text-slate-400">
                <li className="flex gap-2"><CheckCircle2 size={14} className="mt-0.5 shrink-0 text-teal-300" /> Debit and credit balancing</li>
                <li className="flex gap-2"><CheckCircle2 size={14} className="mt-0.5 shrink-0 text-teal-300" /> Journal → ledger → trial balance</li>
                <li className="flex gap-2"><CheckCircle2 size={14} className="mt-0.5 shrink-0 text-teal-300" /> Cash receipts, payments and closing balance</li>
              </ul>
            </div>
          </aside>
        </div>
        <footer className="mt-8 text-center text-xs text-slate-600">Solix Finance AI · Deterministic calculations · Human review remains important</footer>
      </div>
    </main>
  );
}

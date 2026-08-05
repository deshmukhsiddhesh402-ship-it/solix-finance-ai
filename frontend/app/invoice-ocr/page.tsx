"use client";

import { useState, useRef } from "react";
import { UploadCloud, Loader2, Download, FileOutput, CheckCircle2, AlertCircle } from "lucide-react";

type Invoice = {
  vendor_name: string | null;
  vendor_gstin: string | null;
  gstin_format_valid?: boolean;
  invoice_number: string | null;
  invoice_date: string | null;
  taxable_value: number | null;
  cgst_amount: number | null;
  sgst_amount: number | null;
  igst_amount: number | null;
  total_amount: number | null;
  line_items: { description: string; quantity: number | null; amount: number }[];
  confidence_notes: string;
};

function INR(n: number | null) {
  if (n === null || n === undefined) return "—";
  return "₹" + n.toLocaleString("en-IN");
}

export default function InvoiceOcrPage() {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [invoice, setInvoice] = useState<Invoice | null>(null);
  const [journalLines, setJournalLines] = useState<any[] | null>(null);
  const [postingJournal, setPostingJournal] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  async function handleUpload(file: File) {
    setUploading(true); setError(""); setInvoice(null); setJournalLines(null);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch("/api/ocr/extract", { method: "POST", body: formData });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || data.error || "Extraction failed");
      setSessionId(data.session_id);
      setInvoice(data.invoice);
    } catch (e: any) { setError(e.message); } finally { setUploading(false); }
  }

  async function postToJournal() {
    if (!sessionId) return;
    setPostingJournal(true); setError("");
    try {
      const res = await fetch("/api/ocr/journal-entry", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || data.error || "Could not generate journal entry");
      setJournalLines(data.journal_lines);
    } catch (e: any) { setError(e.message); } finally { setPostingJournal(false); }
  }

  return (
    <main className="min-h-screen bg-[#0a0a12] text-slate-100 relative overflow-hidden">
      <div className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute top-[-10%] left-[15%] h-[500px] w-[500px] rounded-full bg-teal-600/15 blur-[120px]" />
        <div className="absolute bottom-[-10%] right-[15%] h-[500px] w-[500px] rounded-full bg-violet-600/15 blur-[120px]" />
      </div>

      <div className="max-w-4xl mx-auto px-6 py-12">
        <header className="mb-8">
          <h1 className="text-3xl font-semibold tracking-tight bg-gradient-to-r from-teal-300 to-violet-300 bg-clip-text text-transparent">
            OCR &amp; Invoice Processing
          </h1>
          <p className="text-slate-400 mt-1 text-sm">Upload an invoice or receipt — vendor, GSTIN, amounts, and tax are extracted automatically.</p>
        </header>

        {!invoice && (
          <div onClick={() => fileInputRef.current?.click()} className="rounded-2xl border-2 border-dashed border-white/15 bg-white/5 backdrop-blur-xl p-12 text-center cursor-pointer hover:border-teal-400/40 transition">
            <UploadCloud className="mx-auto mb-3 text-slate-400" size={32} />
            <p className="text-sm text-slate-300">Click to upload an invoice or receipt</p>
            <p className="text-xs text-slate-500 mt-1">Supports .jpg, .png, .webp, .pdf</p>
            <input ref={fileInputRef} type="file" accept=".jpg,.jpeg,.png,.webp,.pdf" className="hidden"
              onChange={(e) => e.target.files?.[0] && handleUpload(e.target.files[0])} />
            {uploading && <div className="mt-4 flex items-center justify-center gap-2 text-sm text-teal-300"><Loader2 className="animate-spin" size={16} /> Reading document...</div>}
          </div>
        )}

        {error && <div className="rounded-xl border border-red-400/30 bg-red-500/10 p-4 text-sm text-red-200 mt-6">{error}</div>}

        {invoice && (
          <div className="space-y-6">
            <div className="rounded-2xl border border-white/10 bg-white/5 backdrop-blur-xl p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-sm font-medium text-teal-300">Extracted Fields</h2>
                <div className="flex gap-2">
                  <button onClick={postToJournal} disabled={postingJournal} className="flex items-center gap-2 text-xs px-3 py-1.5 rounded-lg bg-violet-600/20 border border-violet-400/30 hover:bg-violet-600/30 disabled:opacity-50 transition">
                    {postingJournal ? <Loader2 className="animate-spin" size={12} /> : <FileOutput size={12} />} Post to Journal Entry
                  </button>
                  {sessionId && (
                    <a href={`/api/ocr/export/${sessionId}`} className="flex items-center gap-2 text-xs px-3 py-1.5 rounded-lg bg-teal-600/20 border border-teal-400/30 hover:bg-teal-600/30 transition">
                      <Download size={12} /> Export Excel
                    </a>
                  )}
                </div>
              </div>

              <dl className="grid sm:grid-cols-2 gap-3 text-sm">
                <div className="flex justify-between border-b border-white/5 pb-2"><dt className="text-slate-400">Vendor</dt><dd>{invoice.vendor_name || "—"}</dd></div>
                <div className="flex justify-between border-b border-white/5 pb-2">
                  <dt className="text-slate-400">GSTIN</dt>
                  <dd className="flex items-center gap-1.5">
                    {invoice.vendor_gstin || "—"}
                    {invoice.vendor_gstin && (invoice.gstin_format_valid
                      ? <CheckCircle2 size={13} className="text-emerald-400" />
                      : <AlertCircle size={13} className="text-red-400" />)}
                  </dd>
                </div>
                <div className="flex justify-between border-b border-white/5 pb-2"><dt className="text-slate-400">Invoice Number</dt><dd>{invoice.invoice_number || "—"}</dd></div>
                <div className="flex justify-between border-b border-white/5 pb-2"><dt className="text-slate-400">Invoice Date</dt><dd>{invoice.invoice_date || "—"}</dd></div>
                <div className="flex justify-between border-b border-white/5 pb-2"><dt className="text-slate-400">Taxable Value</dt><dd>{INR(invoice.taxable_value)}</dd></div>
                <div className="flex justify-between border-b border-white/5 pb-2"><dt className="text-slate-400">CGST</dt><dd>{INR(invoice.cgst_amount)}</dd></div>
                <div className="flex justify-between border-b border-white/5 pb-2"><dt className="text-slate-400">SGST</dt><dd>{INR(invoice.sgst_amount)}</dd></div>
                <div className="flex justify-between border-b border-white/5 pb-2"><dt className="text-slate-400">IGST</dt><dd>{INR(invoice.igst_amount)}</dd></div>
                <div className="flex justify-between font-medium pt-1 sm:col-span-2"><dt>Total Amount</dt><dd className="text-teal-300">{INR(invoice.total_amount)}</dd></div>
              </dl>

              {invoice.confidence_notes && invoice.confidence_notes !== "none" && (
                <p className="text-xs text-amber-300 mt-4 flex items-start gap-1.5"><AlertCircle size={13} className="mt-0.5 shrink-0" /> {invoice.confidence_notes}</p>
              )}

              {invoice.line_items?.length > 0 && (
                <div className="mt-5">
                  <h3 className="text-xs uppercase tracking-wide text-slate-400 mb-2">Line Items</h3>
                  <table className="w-full text-xs">
                    <thead className="text-slate-400"><tr><th className="text-left pb-1">Description</th><th className="text-right pb-1">Qty</th><th className="text-right pb-1">Amount</th></tr></thead>
                    <tbody>
                      {invoice.line_items.map((li, i) => (
                        <tr key={i} className="border-t border-white/5"><td className="py-1.5">{li.description}</td><td className="py-1.5 text-right">{li.quantity ?? "—"}</td><td className="py-1.5 text-right">{INR(li.amount)}</td></tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {journalLines && (
              <div className="rounded-2xl border border-white/10 bg-white/5 backdrop-blur-xl p-6">
                <h2 className="text-sm font-medium text-violet-300 mb-3">Journal Entry</h2>
                <table className="w-full text-xs">
                  <thead className="text-slate-400"><tr><th className="text-left pb-2">Account</th><th className="text-right pb-2">Debit</th><th className="text-right pb-2">Credit</th></tr></thead>
                  <tbody>
                    {journalLines.map((l, i) => (
                      <tr key={i} className="border-t border-white/5">
                        <td className="py-1.5">{l.account_name}</td>
                        <td className="py-1.5 text-right">{l.debit ? INR(l.debit) : ""}</td>
                        <td className="py-1.5 text-right">{l.credit ? INR(l.credit) : ""}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>
    </main>
  );
}

"use client";

import { useState, useRef } from "react";
import { UploadCloud, Download, Loader2, CheckCircle2, AlertTriangle } from "lucide-react";

export default function ExcelAutomationPage() {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<any>(null);
  const [categorizeColumn, setCategorizeColumn] = useState("Description");
  const [dedupe, setDedupe] = useState(true);
  const fileInputRef = useRef<HTMLInputElement>(null);

  async function handleUpload(file: File) {
    setUploading(true); setError(""); setResult(null);
    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("dedupe", String(dedupe));
      if (categorizeColumn.trim()) formData.append("categorize_column", categorizeColumn.trim());

      const res = await fetch("/api/excel-automation/auto-clean", { method: "POST", body: formData });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || data.error || "Upload failed");
      setResult(data);
    } catch (e: any) { setError(e.message); } finally { setUploading(false); }
  }

  const hasErrors = result && (
    Object.keys(result.errors_detected.missing_values).length > 0 ||
    Object.keys(result.errors_detected.negative_amounts).length > 0 ||
    Object.keys(result.errors_detected.outliers).length > 0
  );

  return (
    <main className="min-h-screen bg-[#0a0a12] text-slate-100 relative overflow-hidden">
      <div className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute top-[-10%] left-[15%] h-[500px] w-[500px] rounded-full bg-emerald-600/15 blur-[120px]" />
        <div className="absolute bottom-[-10%] right-[15%] h-[500px] w-[500px] rounded-full bg-violet-600/15 blur-[120px]" />
      </div>

      <div className="max-w-4xl mx-auto px-6 py-12">
        <header className="mb-8">
          <h1 className="text-3xl font-semibold tracking-tight bg-gradient-to-r from-emerald-300 to-violet-300 bg-clip-text text-transparent">
            Excel Automation
          </h1>
          <p className="text-slate-400 mt-1 text-sm">Auto-clean data, remove duplicates, detect errors, and auto-categorize expenses.</p>
        </header>

        <div className="rounded-2xl border border-white/10 bg-white/5 backdrop-blur-xl p-6 mb-6 space-y-4">
          <div className="flex flex-wrap items-center gap-4">
            <label className="flex items-center gap-2 text-sm text-slate-300">
              <input type="checkbox" checked={dedupe} onChange={(e) => setDedupe(e.target.checked)} />
              Remove duplicate rows
            </label>
            <div className="flex items-center gap-2">
              <label className="text-xs text-slate-400">Categorize expenses using column:</label>
              <input className="rounded-lg bg-black/30 border border-white/10 px-3 py-1.5 text-sm w-40" value={categorizeColumn} onChange={(e) => setCategorizeColumn(e.target.value)} placeholder="Description" />
            </div>
          </div>

          <div
            onClick={() => fileInputRef.current?.click()}
            className="rounded-xl border-2 border-dashed border-white/15 p-10 text-center cursor-pointer hover:border-emerald-400/40 transition"
          >
            <UploadCloud className="mx-auto mb-2 text-slate-400" size={28} />
            <p className="text-sm text-slate-300">Click to upload a .csv or .xlsx file</p>
            <input ref={fileInputRef} type="file" accept=".csv,.xlsx,.xlsm" className="hidden"
              onChange={(e) => e.target.files?.[0] && handleUpload(e.target.files[0])} />
            {uploading && <div className="mt-4 flex items-center justify-center gap-2 text-sm text-emerald-300"><Loader2 className="animate-spin" size={16} /> Cleaning &amp; analyzing...</div>}
          </div>
        </div>

        {error && <div className="rounded-xl border border-red-400/30 bg-red-500/10 p-4 text-sm text-red-200 mb-6">{error}</div>}

        {result && (
          <div className="space-y-6">
            <div className="grid sm:grid-cols-4 gap-4">
              <div className="rounded-xl border border-white/10 bg-white/5 p-4 text-center">
                <div className="text-xl font-semibold">{result.clean_report.empty_rows_removed}</div>
                <div className="text-xs text-slate-400 mt-1">Empty rows removed</div>
              </div>
              <div className="rounded-xl border border-white/10 bg-white/5 p-4 text-center">
                <div className="text-xl font-semibold">{result.duplicates_removed}</div>
                <div className="text-xs text-slate-400 mt-1">Duplicates removed</div>
              </div>
              <div className="rounded-xl border border-white/10 bg-white/5 p-4 text-center">
                <div className="text-xl font-semibold">{result.clean_report.columns_coerced_to_numeric.length}</div>
                <div className="text-xs text-slate-400 mt-1">Columns fixed to numeric</div>
              </div>
              <div className="rounded-xl border border-white/10 bg-white/5 p-4 text-center">
                <div className="text-xl font-semibold">{result.row_count}</div>
                <div className="text-xs text-slate-400 mt-1">Final row count</div>
              </div>
            </div>

            <div className={`rounded-xl border p-4 flex items-start gap-3 text-sm ${hasErrors ? "border-amber-400/30 bg-amber-500/10 text-amber-200" : "border-emerald-400/30 bg-emerald-500/10 text-emerald-200"}`}>
              {hasErrors ? <AlertTriangle size={18} className="shrink-0 mt-0.5" /> : <CheckCircle2 size={18} className="shrink-0 mt-0.5" />}
              <div>
                {hasErrors ? (
                  <ul className="space-y-1">
                    {Object.entries(result.errors_detected.missing_values).map(([col, n]: any) => <li key={col}>{col}: {n} missing values</li>)}
                    {Object.entries(result.errors_detected.negative_amounts).map(([col, n]: any) => <li key={col}>{col}: {n} unexpected negative amounts</li>)}
                    {Object.entries(result.errors_detected.outliers).map(([col, n]: any) => <li key={col}>{col}: {n} statistical outliers</li>)}
                  </ul>
                ) : "No data quality issues detected."}
              </div>
            </div>

            <div className="rounded-2xl border border-white/10 bg-white/5 backdrop-blur-xl p-5 overflow-x-auto">
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-sm font-medium text-emerald-300">Preview (first 10 rows)</h2>
                <a href={`/api/excel-automation/download/${result.session_id}`} className="flex items-center gap-2 text-xs px-3 py-1.5 rounded-lg bg-emerald-600/20 border border-emerald-400/30 hover:bg-emerald-600/30 transition">
                  <Download size={14} /> Download cleaned .xlsx
                </a>
              </div>
              <table className="w-full text-xs">
                <thead className="text-slate-400"><tr>{result.columns.map((c: string) => <th key={c} className="text-left pb-2 pr-4">{c}</th>)}</tr></thead>
                <tbody>
                  {result.preview.map((row: any, i: number) => (
                    <tr key={i} className="border-t border-white/5">
                      {result.columns.map((c: string) => <td key={c} className="py-1.5 pr-4">{String(row[c])}</td>)}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}

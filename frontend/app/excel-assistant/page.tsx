"use client";

import { useState } from "react";
import { Wand2, Bug, FileCode2, Table2, Loader2 } from "lucide-react";

type Action = "explain" | "generate" | "fix" | "vba" | "officeScript" | "pivotPlan";

const TABS: { id: Action; label: string; icon: any }[] = [
  { id: "explain", label: "Explain Formula", icon: Table2 },
  { id: "generate", label: "Generate Formula", icon: Wand2 },
  { id: "fix", label: "Fix Formula", icon: Bug },
  { id: "vba", label: "VBA Macro", icon: FileCode2 },
  { id: "officeScript", label: "Office Script", icon: FileCode2 },
  { id: "pivotPlan", label: "Pivot Table Plan", icon: Table2 },
];

export default function ExcelAssistantPage() {
  const [tab, setTab] = useState<Action>("explain");
  const [inputs, setInputs] = useState<Record<string, string>>({});
  const [result, setResult] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const fieldsForTab: Record<Action, { key: string; label: string; placeholder: string }[]> = {
    explain: [{ key: "formula", label: "Formula", placeholder: "=XLOOKUP(A2,Sheet2!A:A,Sheet2!B:B)" }],
    generate: [{ key: "description", label: "What do you want the formula to do?", placeholder: "Sum sales for the current month only" }],
    fix: [
      { key: "formula", label: "Broken formula", placeholder: "=VLOOKUP(A2,B:C,3,FALSE)" },
      { key: "error_description", label: "Error / issue", placeholder: "Returns #REF! after inserting a column" },
    ],
    vba: [{ key: "task_description", label: "Describe the macro", placeholder: "Loop through Sheet1 and highlight rows where column C > 10000" }],
    officeScript: [{ key: "task_description", label: "Describe the script", placeholder: "Remove duplicate rows based on column A across the active worksheet" }],
    pivotPlan: [
      { key: "data_description", label: "Source data description", placeholder: "Sales data with columns: Date, Region, Product, Revenue" },
      { key: "goal", label: "Analysis goal", placeholder: "Monthly revenue by region and product" },
    ],
  };

  async function handleSubmit() {
    setLoading(true);
    setError("");
    setResult("");
    try {
      const res = await fetch("/api/excel-ai", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: tab, ...inputs }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Request failed");
      setResult(Object.values(data)[0] as string);
    } catch (e: any) {
      setError(e.message || "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-[#0a0a12] text-slate-100 relative overflow-hidden">
      {/* Ambient glow background */}
      <div className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute top-[-10%] left-[10%] h-[500px] w-[500px] rounded-full bg-violet-600/20 blur-[120px]" />
        <div className="absolute bottom-[-10%] right-[10%] h-[500px] w-[500px] rounded-full bg-indigo-600/20 blur-[120px]" />
      </div>

      <div className="max-w-5xl mx-auto px-6 py-12">
        <header className="mb-8">
          <h1 className="text-3xl font-semibold tracking-tight bg-gradient-to-r from-violet-300 to-indigo-300 bg-clip-text text-transparent">
            AI Excel Assistant
          </h1>
          <p className="text-slate-400 mt-1 text-sm">
            Explain, generate, and fix formulas. Build VBA macros, Office Scripts, and Pivot Table plans — powered by Claude.
          </p>
        </header>

        {/* Tabs */}
        <div className="flex flex-wrap gap-2 mb-6">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => { setTab(id); setInputs({}); setResult(""); setError(""); }}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm border transition
                ${tab === id
                  ? "bg-violet-600/20 border-violet-400/40 text-violet-200"
                  : "bg-white/5 border-white/10 text-slate-300 hover:bg-white/10"}`}
            >
              <Icon size={16} /> {label}
            </button>
          ))}
        </div>

        {/* Input card (glassmorphism) */}
        <div className="rounded-2xl border border-white/10 bg-white/5 backdrop-blur-xl p-6 space-y-4 shadow-2xl">
          {fieldsForTab[tab].map((f) => (
            <div key={f.key}>
              <label className="text-xs uppercase tracking-wide text-slate-400">{f.label}</label>
              <textarea
                className="mt-1 w-full rounded-lg bg-black/30 border border-white/10 p-3 text-sm font-mono
                           focus:outline-none focus:ring-2 focus:ring-violet-500/50 resize-y min-h-[60px]"
                placeholder={f.placeholder}
                value={inputs[f.key] || ""}
                onChange={(e) => setInputs((prev) => ({ ...prev, [f.key]: e.target.value }))}
              />
            </div>
          ))}

          <button
            onClick={handleSubmit}
            disabled={loading}
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600
                       hover:from-violet-500 hover:to-indigo-500 disabled:opacity-50 font-medium text-sm transition"
          >
            {loading ? <Loader2 className="animate-spin" size={16} /> : <Wand2 size={16} />}
            {loading ? "Thinking..." : "Run"}
          </button>
        </div>

        {/* Result */}
        {error && (
          <div className="mt-6 rounded-xl border border-red-400/30 bg-red-500/10 p-4 text-sm text-red-200">
            {error}
          </div>
        )}
        {result && (
          <div className="mt-6 rounded-2xl border border-white/10 bg-white/5 backdrop-blur-xl p-6">
            <h2 className="text-xs uppercase tracking-wide text-slate-400 mb-2">Result</h2>
            <pre className="whitespace-pre-wrap text-sm font-mono text-slate-100 leading-relaxed">{result}</pre>
          </div>
        )}
      </div>
    </main>
  );
}

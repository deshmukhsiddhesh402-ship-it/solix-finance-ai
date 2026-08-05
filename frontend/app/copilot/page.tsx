"use client";

import { useState } from "react";
import { Sparkles, Send, Loader2, Bot, User, Table2 } from "lucide-react";

type Message = { role: "user" | "assistant"; content: string; data?: any; toolUsed?: string };

const SUGGESTIONS = [
  "Show me expenses above ₹50,000",
  "Why did profit decrease this month?",
  "Predict next month's cash flow",
  "Generate GST summary",
];

function INR(n: number) {
  return "₹" + n.toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

function DataPanel({ toolUsed, data }: { toolUsed: string; data: any }) {
  if (toolUsed === "filter_transactions" && data.transactions) {
    return (
      <div className="mt-3 rounded-lg border border-white/10 bg-black/20 p-3 overflow-x-auto">
        <table className="w-full text-xs">
          <thead className="text-slate-400"><tr><th className="text-left pb-1.5">Date</th><th className="text-left pb-1.5">Account</th><th className="text-right pb-1.5">Amount</th></tr></thead>
          <tbody>
            {data.transactions.map((t: any, i: number) => (
              <tr key={i} className="border-t border-white/5"><td className="py-1">{t.date}</td><td className="py-1">{t.account_name}</td><td className="py-1 text-right">{INR(t.amount)}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }
  if (toolUsed === "compare_periods" && data.top_drivers) {
    return (
      <div className="mt-3 rounded-lg border border-white/10 bg-black/20 p-3">
        <table className="w-full text-xs">
          <thead className="text-slate-400"><tr><th className="text-left pb-1.5">Account</th><th className="text-right pb-1.5">{data.period_a.label}</th><th className="text-right pb-1.5">{data.period_b.label}</th><th className="text-right pb-1.5">Change</th></tr></thead>
          <tbody>
            {data.top_drivers.map((d: any, i: number) => (
              <tr key={i} className="border-t border-white/5">
                <td className="py-1">{d.account}</td><td className="py-1 text-right">{INR(d.period_a)}</td><td className="py-1 text-right">{INR(d.period_b)}</td>
                <td className={`py-1 text-right ${d.change > 0 === (d.type === "income") ? "text-emerald-300" : "text-red-300"}`}>{d.change > 0 ? "+" : ""}{INR(d.change)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }
  if (toolUsed === "predict_cash_flow" && data.predictions) {
    return (
      <div className="mt-3 rounded-lg border border-white/10 bg-black/20 p-3 text-xs">
        <div className="flex gap-4 flex-wrap">
          {data.predictions.map((p: number, i: number) => (
            <div key={i}><span className="text-slate-400">Month +{i + 1}: </span><span className="font-medium">{INR(p)}</span></div>
          ))}
        </div>
        <p className="text-slate-500 mt-2">{data.caveat}</p>
      </div>
    );
  }
  if (toolUsed === "gst_summary" && data.by_account) {
    return (
      <div className="mt-3 rounded-lg border border-white/10 bg-black/20 p-3 text-xs space-y-1">
        {Object.entries(data.by_account).map(([k, v]: any) => (
          <div key={k} className="flex justify-between"><span className="text-slate-400">{k}</span><span>{INR(v)}</span></div>
        ))}
        <div className="flex justify-between border-t border-white/10 pt-1.5 mt-1.5 font-medium"><span>Total</span><span>{INR(data.total_gst_liability)}</span></div>
      </div>
    );
  }
  return null;
}

export default function CopilotPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function ask(q: string) {
    if (!q.trim()) return;
    setMessages((prev) => [...prev, { role: "user", content: q }]);
    setQuestion("");
    setLoading(true); setError("");
    try {
      const res = await fetch("/api/copilot", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || data.error || "Request failed");
      setMessages((prev) => [...prev, { role: "assistant", content: data.answer, data: data.data, toolUsed: data.tool_used }]);
    } catch (e: any) {
      setError(e.message);
    } finally { setLoading(false); }
  }

  return (
    <main className="min-h-screen bg-[#0a0a12] text-slate-100 relative overflow-hidden flex flex-col">
      <div className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute top-[-10%] left-[10%] h-[500px] w-[500px] rounded-full bg-violet-600/15 blur-[120px]" />
        <div className="absolute bottom-[-10%] right-[10%] h-[500px] w-[500px] rounded-full bg-emerald-600/15 blur-[120px]" />
      </div>

      <div className="max-w-3xl mx-auto px-6 py-12 w-full flex-1 flex flex-col">
        <header className="mb-6">
          <h1 className="text-3xl font-semibold tracking-tight bg-gradient-to-r from-violet-300 to-emerald-300 bg-clip-text text-transparent flex items-center gap-2">
            <Sparkles size={26} /> AI Finance Copilot
          </h1>
          <p className="text-slate-400 mt-1 text-sm">Ask about your books in plain language. Answers are grounded in your real posted ledger data.</p>
        </header>

        {messages.length === 0 && (
          <div className="grid sm:grid-cols-2 gap-2 mb-6">
            {SUGGESTIONS.map((s) => (
              <button key={s} onClick={() => ask(s)} className="text-left text-xs px-3 py-2.5 rounded-xl bg-white/5 border border-white/10 hover:bg-white/10 transition text-slate-300">
                {s}
              </button>
            ))}
          </div>
        )}

        <div className="flex-1 space-y-4 mb-4 overflow-y-auto max-h-[55vh] pr-1">
          {messages.map((m, i) => (
            <div key={i} className={`flex gap-3 ${m.role === "user" ? "justify-end" : ""}`}>
              {m.role === "assistant" && <Bot size={20} className="text-violet-300 mt-1 shrink-0" />}
              <div className={`rounded-2xl px-4 py-3 text-sm max-w-[85%] ${m.role === "user" ? "bg-violet-600/20 border border-violet-400/30" : "bg-white/5 border border-white/10"}`}>
                <p className="whitespace-pre-wrap">{m.content}</p>
                {m.toolUsed && m.data && <DataPanel toolUsed={m.toolUsed} data={m.data} />}
              </div>
              {m.role === "user" && <User size={20} className="text-slate-400 mt-1 shrink-0" />}
            </div>
          ))}
          {loading && <div className="flex gap-3"><Bot size={20} className="text-violet-300 mt-1" /><div className="rounded-2xl px-4 py-3 bg-white/5 border border-white/10"><Loader2 className="animate-spin" size={16} /></div></div>}
        </div>

        <div className="flex gap-2">
          <input
            className="flex-1 rounded-xl bg-black/30 border border-white/10 px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500/40"
            placeholder="Ask about your finances..."
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && ask(question)}
          />
          <button onClick={() => ask(question)} disabled={loading || !question.trim()} className="px-4 rounded-xl bg-gradient-to-r from-violet-600 to-emerald-600 hover:from-violet-500 hover:to-emerald-500 disabled:opacity-50 transition">
            <Send size={18} />
          </button>
        </div>

        {error && <div className="mt-4 rounded-xl border border-red-400/30 bg-red-500/10 p-4 text-sm text-red-200">{error}</div>}
      </div>
    </main>
  );
}

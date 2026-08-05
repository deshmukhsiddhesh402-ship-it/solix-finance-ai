"use client";

import { useState, useRef } from "react";
import { UploadCloud, Send, FileText, Loader2, Bot, User } from "lucide-react";

type Message = { role: "user" | "assistant"; content: string; sources?: any[] };

export default function ChatPage() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const [chunkCount, setChunkCount] = useState<number | null>(null);
  const [retrievalMode, setRetrievalMode] = useState<"semantic" | "keyword" | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [question, setQuestion] = useState("");
  const [uploading, setUploading] = useState(false);
  const [asking, setAsking] = useState(false);
  const [error, setError] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  async function handleUpload(file: File) {
    setUploading(true); setError("");
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch("/api/chat/upload", { method: "POST", body: formData });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || data.error || "Upload failed");
      setSessionId(data.session_id);
      setFileName(data.filename);
      setChunkCount(data.chunk_count);
      setRetrievalMode(data.mode);
      setMessages([{ role: "assistant", content: `Loaded "${data.filename}" (${data.chunk_count} chunks indexed). Ask me anything about it.` }]);
    } catch (e: any) { setError(e.message); } finally { setUploading(false); }
  }

  async function handleAsk() {
    if (!sessionId || !question.trim()) return;
    const q = question.trim();
    setMessages((prev) => [...prev, { role: "user", content: q }]);
    setQuestion("");
    setAsking(true); setError("");
    try {
      const res = await fetch("/api/chat/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, question: q }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || data.error || "Request failed");
      setMessages((prev) => [...prev, { role: "assistant", content: data.answer, sources: data.sources }]);
    } catch (e: any) {
      setError(e.message);
    } finally { setAsking(false); }
  }

  return (
    <main className="min-h-screen bg-[#0a0a12] text-slate-100 relative overflow-hidden flex flex-col">
      <div className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute top-[-10%] left-[10%] h-[500px] w-[500px] rounded-full bg-violet-600/15 blur-[120px]" />
        <div className="absolute bottom-[-10%] right-[10%] h-[500px] w-[500px] rounded-full bg-sky-600/15 blur-[120px]" />
      </div>

      <div className="max-w-3xl mx-auto px-6 py-12 w-full flex-1 flex flex-col">
        <header className="mb-6">
          <h1 className="text-3xl font-semibold tracking-tight bg-gradient-to-r from-violet-300 to-sky-300 bg-clip-text text-transparent">
            AI Chat
          </h1>
          <p className="text-slate-400 mt-1 text-sm">Upload an Excel file, PDF, or bank statement and ask questions about it.</p>
        </header>

        {!sessionId ? (
          <div
            onClick={() => fileInputRef.current?.click()}
            className="rounded-2xl border-2 border-dashed border-white/15 bg-white/5 backdrop-blur-xl p-12 text-center cursor-pointer hover:border-violet-400/40 transition"
          >
            <UploadCloud className="mx-auto mb-3 text-slate-400" size={32} />
            <p className="text-sm text-slate-300">Click to upload a document</p>
            <p className="text-xs text-slate-500 mt-1">Supports .pdf, .xlsx, .docx, .txt, .csv, .md</p>
            <input ref={fileInputRef} type="file" accept=".pdf,.xlsx,.xlsm,.docx,.txt,.csv,.md" className="hidden"
              onChange={(e) => e.target.files?.[0] && handleUpload(e.target.files[0])} />
            {uploading && <div className="mt-4 flex items-center justify-center gap-2 text-sm text-violet-300"><Loader2 className="animate-spin" size={16} /> Extracting &amp; indexing...</div>}
          </div>
        ) : (
          <>
            <div className="rounded-xl border border-white/10 bg-white/5 px-4 py-2 mb-4 flex items-center justify-between gap-2 text-xs text-slate-400">
              <span className="flex items-center gap-2"><FileText size={14} /> {fileName} · {chunkCount} chunks indexed</span>
              <span className={`px-2 py-0.5 rounded-full text-[10px] uppercase tracking-wide ${retrievalMode === "semantic" ? "bg-emerald-500/15 text-emerald-300 border border-emerald-400/30" : "bg-amber-500/15 text-amber-300 border border-amber-400/30"}`}>
                {retrievalMode === "semantic" ? "Semantic search" : "Keyword search (add VOYAGE_API_KEY for semantic)"}
              </span>
            </div>

            <div className="flex-1 space-y-4 mb-4 overflow-y-auto max-h-[50vh] pr-1">
              {messages.map((m, i) => (
                <div key={i} className={`flex gap-3 ${m.role === "user" ? "justify-end" : ""}`}>
                  {m.role === "assistant" && <Bot size={20} className="text-violet-300 mt-1 shrink-0" />}
                  <div className={`rounded-2xl px-4 py-3 text-sm max-w-[80%] ${m.role === "user" ? "bg-violet-600/20 border border-violet-400/30" : "bg-white/5 border border-white/10"}`}>
                    <p className="whitespace-pre-wrap">{m.content}</p>
                    {m.sources && m.sources.length > 0 && (
                      <details className="mt-2 text-xs text-slate-400">
                        <summary className="cursor-pointer">Sources ({m.sources.length})</summary>
                        <ul className="mt-1 space-y-1">
                          {m.sources.map((s: any, idx: number) => (
                            <li key={idx} className="border-l-2 border-white/10 pl-2"><span className="text-slate-500">{s.document}:</span> {s.excerpt}...</li>
                          ))}
                        </ul>
                      </details>
                    )}
                  </div>
                  {m.role === "user" && <User size={20} className="text-slate-400 mt-1 shrink-0" />}
                </div>
              ))}
              {asking && <div className="flex gap-3"><Bot size={20} className="text-violet-300 mt-1" /><div className="rounded-2xl px-4 py-3 bg-white/5 border border-white/10"><Loader2 className="animate-spin" size={16} /></div></div>}
            </div>

            <div className="flex gap-2">
              <input
                className="flex-1 rounded-xl bg-black/30 border border-white/10 px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500/40"
                placeholder="Ask about this document..."
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleAsk()}
              />
              <button onClick={handleAsk} disabled={asking || !question.trim()} className="px-4 rounded-xl bg-gradient-to-r from-violet-600 to-sky-600 hover:from-violet-500 hover:to-sky-500 disabled:opacity-50 transition">
                <Send size={18} />
              </button>
            </div>
          </>
        )}

        {error && <div className="mt-4 rounded-xl border border-red-400/30 bg-red-500/10 p-4 text-sm text-red-200">{error}</div>}
      </div>
    </main>
  );
}

"use client";

import { useState } from "react";
import { GraduationCap, Send, Loader2, CheckCircle2, XCircle } from "lucide-react";

const TOPICS = ["Excel", "Advanced Excel", "Tally Prime", "Power BI", "GST", "TDS", "ITR Filing", "Accounting", "Finance", "US CMA"];
const LEVELS = ["beginner", "intermediate", "advanced"];

type QuizQuestion = { question: string; options: string[]; correct_index: number; explanation: string };

export default function LearningPage() {
  const [mode, setMode] = useState<"tutor" | "quiz">("tutor");
  const [topic, setTopic] = useState("Excel");
  const [level, setLevel] = useState("beginner");
  const [question, setQuestion] = useState("How do I use VLOOKUP?");
  const [answer, setAnswer] = useState("");
  const [quiz, setQuiz] = useState<QuizQuestion[] | null>(null);
  const [selectedAnswers, setSelectedAnswers] = useState<Record<number, number>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function callApi(action: string, payload: any) {
    const res = await fetch("/api/learning", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, ...payload }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || data.error || "Request failed");
    return data;
  }

  async function askTutor() {
    setLoading(true); setError(""); setAnswer("");
    try {
      const data = await callApi("ask", { topic, level, question });
      setAnswer(data.answer);
    } catch (e: any) { setError(e.message); } finally { setLoading(false); }
  }

  async function generateQuiz() {
    setLoading(true); setError(""); setQuiz(null); setSelectedAnswers({});
    try {
      const data = await callApi("generateQuiz", { topic, level, num_questions: 5 });
      setQuiz(data.questions);
    } catch (e: any) { setError(e.message); } finally { setLoading(false); }
  }

  return (
    <main className="min-h-screen bg-[#0a0a12] text-slate-100 relative overflow-hidden">
      <div className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute top-[-10%] left-[15%] h-[500px] w-[500px] rounded-full bg-fuchsia-600/15 blur-[120px]" />
        <div className="absolute bottom-[-10%] right-[15%] h-[500px] w-[500px] rounded-full bg-indigo-600/15 blur-[120px]" />
      </div>

      <div className="max-w-3xl mx-auto px-6 py-12">
        <header className="mb-8">
          <h1 className="text-3xl font-semibold tracking-tight bg-gradient-to-r from-fuchsia-300 to-indigo-300 bg-clip-text text-transparent">
            Learning Mode
          </h1>
          <p className="text-slate-400 mt-1 text-sm">Excel, Tally Prime, Power BI, GST, TDS, ITR, Accounting, Finance, and US CMA — ask a tutor or take a quiz.</p>
        </header>

        <div className="flex gap-2 mb-6">
          <button onClick={() => setMode("tutor")} className={`px-4 py-2 rounded-xl text-sm border transition ${mode === "tutor" ? "bg-fuchsia-600/20 border-fuchsia-400/40 text-fuchsia-200" : "bg-white/5 border-white/10 text-slate-300"}`}>Ask a Tutor</button>
          <button onClick={() => setMode("quiz")} className={`px-4 py-2 rounded-xl text-sm border transition ${mode === "quiz" ? "bg-fuchsia-600/20 border-fuchsia-400/40 text-fuchsia-200" : "bg-white/5 border-white/10 text-slate-300"}`}>Take a Quiz</button>
        </div>

        <div className="rounded-2xl border border-white/10 bg-white/5 backdrop-blur-xl p-6 space-y-4">
          <div className="grid sm:grid-cols-2 gap-4">
            <div>
              <label className="text-xs uppercase tracking-wide text-slate-400">Topic</label>
              <select className="mt-1 w-full rounded-lg bg-black/30 border border-white/10 p-3 text-sm" value={topic} onChange={(e) => setTopic(e.target.value)}>
                {TOPICS.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs uppercase tracking-wide text-slate-400">Level</label>
              <select className="mt-1 w-full rounded-lg bg-black/30 border border-white/10 p-3 text-sm" value={level} onChange={(e) => setLevel(e.target.value)}>
                {LEVELS.map((l) => <option key={l} value={l}>{l}</option>)}
              </select>
            </div>
          </div>

          {mode === "tutor" ? (
            <>
              <div>
                <label className="text-xs uppercase tracking-wide text-slate-400">Your question</label>
                <textarea className="mt-1 w-full rounded-lg bg-black/30 border border-white/10 p-3 text-sm min-h-[80px]" value={question} onChange={(e) => setQuestion(e.target.value)} />
              </div>
              <button onClick={askTutor} disabled={loading} className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-fuchsia-600 to-indigo-600 hover:from-fuchsia-500 hover:to-indigo-500 disabled:opacity-50 font-medium text-sm transition">
                {loading ? <Loader2 className="animate-spin" size={16} /> : <Send size={16} />} Ask
              </button>
              {answer && <div className="rounded-xl border border-white/10 bg-black/20 p-4 text-sm whitespace-pre-wrap leading-relaxed">{answer}</div>}
            </>
          ) : (
            <>
              <button onClick={generateQuiz} disabled={loading} className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-fuchsia-600 to-indigo-600 hover:from-fuchsia-500 hover:to-indigo-500 disabled:opacity-50 font-medium text-sm transition">
                {loading ? <Loader2 className="animate-spin" size={16} /> : <GraduationCap size={16} />} Generate Quiz (5 questions)
              </button>

              {quiz && (
                <div className="space-y-5 pt-2">
                  {quiz.map((q, qi) => {
                    const selected = selectedAnswers[qi];
                    const answered = selected !== undefined;
                    return (
                      <div key={qi} className="rounded-xl border border-white/10 bg-black/20 p-4">
                        <p className="text-sm font-medium mb-3">{qi + 1}. {q.question}</p>
                        <div className="space-y-2">
                          {q.options.map((opt, oi) => {
                            const isCorrect = oi === q.correct_index;
                            const isSelected = oi === selected;
                            let style = "border-white/10 hover:bg-white/5";
                            if (answered && isCorrect) style = "border-emerald-400/50 bg-emerald-500/10";
                            else if (answered && isSelected && !isCorrect) style = "border-red-400/50 bg-red-500/10";
                            return (
                              <button key={oi} disabled={answered}
                                onClick={() => setSelectedAnswers((prev) => ({ ...prev, [qi]: oi }))}
                                className={`w-full text-left px-3 py-2 rounded-lg border text-xs flex items-center justify-between transition ${style}`}>
                                <span>{opt}</span>
                                {answered && isCorrect && <CheckCircle2 size={14} className="text-emerald-400 shrink-0" />}
                                {answered && isSelected && !isCorrect && <XCircle size={14} className="text-red-400 shrink-0" />}
                              </button>
                            );
                          })}
                        </div>
                        {answered && <p className="text-xs text-slate-400 mt-2">{q.explanation}</p>}
                      </div>
                    );
                  })}
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

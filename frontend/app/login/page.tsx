"use client";

import { useState } from "react";
import { signIn } from "next-auth/react";
import { Mail, Loader2 } from "lucide-react";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [otp, setOtp] = useState("");
  const [otpSent, setOtpSent] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [devOtp, setDevOtp] = useState("");

  async function requestOtp() {
    setLoading(true); setError("");
    try {
      const res = await fetch("/api/otp/request", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Could not send OTP");
      setOtpSent(true);
      if (data.dev_otp) setDevOtp(data.dev_otp); // local dev convenience only
    } catch (e: any) { setError(e.message); } finally { setLoading(false); }
  }

  async function verifyOtp() {
    setLoading(true); setError("");
    const result = await signIn("otp", { email, otp, redirect: false });
    setLoading(false);
    if (result?.error) setError("Invalid or expired OTP");
    else window.location.href = "/";
  }

  return (
    <main className="min-h-screen bg-[#0a0a12] text-slate-100 flex items-center justify-center px-6">
      <div className="w-full max-w-sm rounded-2xl border border-white/10 bg-white/5 backdrop-blur-xl p-8">
        <h1 className="text-2xl font-semibold bg-gradient-to-r from-violet-300 to-indigo-300 bg-clip-text text-transparent mb-1">Sign in</h1>
        <p className="text-sm text-slate-400 mb-6">Access Solix Finance AI</p>

        <div className="space-y-3 mb-6">
          <button onClick={() => signIn("google")} className="w-full rounded-xl bg-white/10 hover:bg-white/15 border border-white/10 px-4 py-2.5 text-sm transition">
            Continue with Google
          </button>
          <button onClick={() => signIn("azure-ad")} className="w-full rounded-xl bg-white/10 hover:bg-white/15 border border-white/10 px-4 py-2.5 text-sm transition">
            Continue with Microsoft
          </button>
        </div>

        <div className="flex items-center gap-3 mb-6">
          <div className="h-px bg-white/10 flex-1" /><span className="text-xs text-slate-500">or</span><div className="h-px bg-white/10 flex-1" />
        </div>

        <div className="space-y-3">
          <div className="flex gap-2">
            <input type="email" placeholder="you@company.com" value={email} onChange={(e) => setEmail(e.target.value)}
              className="flex-1 rounded-lg bg-black/30 border border-white/10 px-3 py-2.5 text-sm" />
            <button onClick={requestOtp} disabled={loading || !email} className="px-3 rounded-lg bg-violet-600/20 border border-violet-400/30 hover:bg-violet-600/30 disabled:opacity-50 transition">
              {loading ? <Loader2 className="animate-spin" size={16} /> : <Mail size={16} />}
            </button>
          </div>

          {otpSent && (
            <>
              <input placeholder="Enter 6-digit OTP" value={otp} onChange={(e) => setOtp(e.target.value)}
                className="w-full rounded-lg bg-black/30 border border-white/10 px-3 py-2.5 text-sm" />
              {devOtp && <p className="text-xs text-amber-300">Dev mode — your OTP is {devOtp} (wire a real SMS/email provider before production)</p>}
              <button onClick={verifyOtp} disabled={loading || otp.length < 4} className="w-full rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 disabled:opacity-50 px-4 py-2.5 text-sm font-medium transition">
                Verify &amp; Sign in
              </button>
            </>
          )}
        </div>

        {error && <p className="text-xs text-red-300 mt-4">{error}</p>}
      </div>
    </main>
  );
}

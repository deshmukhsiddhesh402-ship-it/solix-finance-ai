"use client";

import { useEffect, useState } from "react";
import Script from "next/script";
import { Check, Loader2 } from "lucide-react";

type Plan = {
  label: string;
  price_inr_per_month: number;
  duration_days?: number;
  limits: Record<string, number | null>;
};

const PLAN_ORDER = ["trial", "pro", "enterprise"];

function formatLimit(key: string, value: number | null) {
  const label = key.replace(/_/g, " ").replace("per month", "/mo");
  return `${value === null ? "Unlimited" : value} ${label}`;
}

export default function PricingPage() {
  const [plans, setPlans] = useState<Record<string, Plan> | null>(null);
  const [orgId, setOrgId] = useState("");
  const [loadingPlan, setLoadingPlan] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [scriptReady, setScriptReady] = useState(false);

  useEffect(() => {
    fetch("/api/billing/plans").then((r) => r.json()).then((d) => setPlans(d.plans)).catch(() => {});
  }, []);

  async function subscribe(planKey: string) {
    if (!orgId.trim()) {
      setMessage("Enter your Organization ID first (find this in Enterprise Admin).");
      return;
    }
    setLoadingPlan(planKey);
    setMessage("");
    try {
      const orderRes = await fetch("/api/billing/create-order", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ org_id: orgId, plan: planKey }),
      });
      const order = await orderRes.json();
      if (!orderRes.ok) throw new Error(order.detail || order.error || "Could not create order");

      if (!scriptReady || !(window as any).Razorpay) {
        throw new Error("Payment widget is still loading — try again in a moment.");
      }

      const rzp = new (window as any).Razorpay({
        key: order.key_id,
        amount: order.amount,
        currency: order.currency,
        order_id: order.order_id,
        name: "Solix Finance AI",
        description: `${plans?.[planKey]?.label} plan — monthly`,
        handler: async (response: any) => {
          setMessage("Verifying payment...");
          const verifyRes = await fetch("/api/billing/verify-payment", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              org_id: orgId, plan: planKey,
              razorpay_order_id: response.razorpay_order_id,
              razorpay_payment_id: response.razorpay_payment_id,
              razorpay_signature: response.razorpay_signature,
            }),
          });
          const verifyData = await verifyRes.json();
          setMessage(verifyRes.ok ? `✓ ${verifyData.message}` : `Payment could not be verified: ${verifyData.detail}`);
        },
        theme: { color: "#8b5cf6" },
      });
      rzp.open();
    } catch (e: any) {
      setMessage(e.message);
    } finally {
      setLoadingPlan(null);
    }
  }

  return (
    <>
      <Script src="https://checkout.razorpay.com/v1/checkout.js" onLoad={() => setScriptReady(true)} />
      <main className="min-h-screen bg-[#0a0a12] text-slate-100 relative overflow-hidden">
        <div className="pointer-events-none absolute inset-0 -z-10">
          <div className="absolute top-[-10%] left-[20%] h-[500px] w-[500px] rounded-full bg-violet-600/15 blur-[120px]" />
          <div className="absolute bottom-[-10%] right-[20%] h-[500px] w-[500px] rounded-full bg-emerald-600/15 blur-[120px]" />
        </div>

        <div className="max-w-5xl mx-auto px-6 py-12">
          <header className="mb-8 text-center">
            <h1 className="text-3xl font-semibold tracking-tight bg-gradient-to-r from-violet-300 to-emerald-300 bg-clip-text text-transparent">
              Pricing
            </h1>
            <p className="text-slate-400 mt-1 text-sm">Simple monthly plans. Billed via Razorpay — UPI, cards, and netbanking supported.</p>
          </header>

          <div className="max-w-xs mx-auto mb-8">
            <input
              placeholder="Your Organization ID"
              value={orgId}
              onChange={(e) => setOrgId(e.target.value)}
              className="w-full rounded-lg bg-black/30 border border-white/10 px-3 py-2 text-sm text-center"
            />
          </div>

          {!plans ? (
            <p className="text-center text-slate-500 text-sm">Loading plans...</p>
          ) : (
            <div className="grid sm:grid-cols-3 gap-6">
              {PLAN_ORDER.map((key) => {
                const plan = plans[key];
                if (!plan) return null;
                const isPaid = plan.price_inr_per_month > 0;
                return (
                  <div key={key} className={`rounded-2xl border p-6 backdrop-blur-xl ${key === "pro" ? "border-violet-400/40 bg-violet-600/10" : "border-white/10 bg-white/5"}`}>
                    <h2 className="text-lg font-medium mb-1">{plan.label}</h2>
                    <p className="text-2xl font-semibold mb-4">
                      {plan.price_inr_per_month === 0 ? "Free" : `₹${plan.price_inr_per_month.toLocaleString("en-IN")}`}
                      {isPaid && <span className="text-sm text-slate-400 font-normal">/month</span>}
                    </p>
                    <ul className="space-y-2 text-xs text-slate-300 mb-6">
                      {Object.entries(plan.limits).map(([k, v]) => (
                        <li key={k} className="flex items-center gap-2"><Check size={13} className="text-emerald-400 shrink-0" /> {formatLimit(k, v)}</li>
                      ))}
                    </ul>
                    <button
                      onClick={() => isPaid ? subscribe(key) : setMessage("You're already on (or can switch to) the Trial plan by default — no payment needed.")}
                      disabled={loadingPlan === key}
                      className={`w-full py-2.5 rounded-xl text-sm font-medium transition ${key === "pro" ? "bg-gradient-to-r from-violet-600 to-emerald-600 hover:from-violet-500 hover:to-emerald-500" : "bg-white/10 hover:bg-white/15"}`}
                    >
                      {loadingPlan === key ? <Loader2 className="animate-spin mx-auto" size={16} /> : isPaid ? "Subscribe" : "Current default"}
                    </button>
                  </div>
                );
              })}
            </div>
          )}

          {message && <p className="text-center text-sm text-amber-300 mt-8">{message}</p>}
        </div>
      </main>
    </>
  );
}

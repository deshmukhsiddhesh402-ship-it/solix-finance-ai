"use client";

import { useEffect, useState } from "react";
import { ShieldCheck, ScrollText, KeyRound, Loader2, Copy, Trash2, AlertTriangle } from "lucide-react";

const ROLE_COLORS: Record<string, string> = {
  admin: "text-violet-300 border-violet-400/30 bg-violet-600/10",
  accountant: "text-emerald-300 border-emerald-400/30 bg-emerald-600/10",
  auditor: "text-sky-300 border-sky-400/30 bg-sky-600/10",
};

export default function AdminPage() {
  const [matrix, setMatrix] = useState<any>(null);
  const [orgId, setOrgId] = useState("");
  const [token, setToken] = useState("");
  const [auditLog, setAuditLog] = useState<any[] | null>(null);
  const [apiKeys, setApiKeys] = useState<any[] | null>(null);
  const [newKeyName, setNewKeyName] = useState("");
  const [newKeyPlaintext, setNewKeyPlaintext] = useState<string | null>(null);
  const [loading, setLoading] = useState<string>("");
  const [error, setError] = useState("");

  useEffect(() => {
    fetch("/api/enterprise/permissions-matrix").then((r) => r.json()).then(setMatrix).catch(() => {});
  }, []);

  async function authedFetch(url: string, options: RequestInit = {}) {
    return fetch(url, { ...options, headers: { ...options.headers, Authorization: `Bearer ${token}` } });
  }

  async function loadAuditLog() {
    setLoading("audit"); setError(""); setAuditLog(null);
    try {
      const res = await authedFetch(`/api/enterprise/audit-log?org_id=${encodeURIComponent(orgId)}`);
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Could not load audit log");
      setAuditLog(data.entries);
    } catch (e: any) { setError(e.message); } finally { setLoading(""); }
  }

  async function loadApiKeys() {
    setLoading("keys"); setError("");
    try {
      const res = await authedFetch(`/api/enterprise/api-keys?org_id=${encodeURIComponent(orgId)}`);
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Could not load API keys");
      setApiKeys(data.keys);
    } catch (e: any) { setError(e.message); } finally { setLoading(""); }
  }

  async function createApiKey() {
    if (!newKeyName.trim()) return;
    setLoading("create-key"); setError(""); setNewKeyPlaintext(null);
    try {
      const res = await authedFetch("/api/enterprise/api-keys", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ org_id: orgId, name: newKeyName }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Could not create API key");
      setNewKeyPlaintext(data.plaintext_key);
      setNewKeyName("");
      loadApiKeys();
    } catch (e: any) { setError(e.message); } finally { setLoading(""); }
  }

  return (
    <main className="min-h-screen bg-[#0a0a12] text-slate-100 relative overflow-hidden">
      <div className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute top-[-10%] left-[15%] h-[500px] w-[500px] rounded-full bg-violet-600/15 blur-[120px]" />
        <div className="absolute bottom-[-10%] right-[15%] h-[500px] w-[500px] rounded-full bg-sky-600/15 blur-[120px]" />
      </div>

      <div className="max-w-4xl mx-auto px-6 py-12 space-y-8">
        <header>
          <h1 className="text-3xl font-semibold tracking-tight bg-gradient-to-r from-violet-300 to-sky-300 bg-clip-text text-transparent">
            Enterprise Admin
          </h1>
          <p className="text-slate-400 mt-1 text-sm">Roles &amp; permissions, audit trail, and API keys for multi-company access.</p>
        </header>

        {/* Role permissions reference */}
        <section className="rounded-2xl border border-white/10 bg-white/5 backdrop-blur-xl p-6">
          <h2 className="text-sm font-medium text-violet-300 mb-4 flex items-center gap-2"><ShieldCheck size={16} /> Roles &amp; Permissions</h2>
          {!matrix ? <p className="text-xs text-slate-500">Loading...</p> : (
            <div className="grid sm:grid-cols-3 gap-4">
              {Object.entries(matrix).map(([role, perms]: any) => (
                <div key={role} className={`rounded-xl border p-4 ${ROLE_COLORS[role] || "border-white/10"}`}>
                  <div className="text-sm font-medium capitalize mb-2">{role}</div>
                  <div className="space-y-1.5 text-xs">
                    {Object.entries(perms).map(([resource, actions]: any) => (
                      <div key={resource}>
                        <span className="text-slate-400">{resource.replace(/_/g, " ")}: </span>
                        <span>{actions.length > 0 ? actions.join(", ") : "no access"}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Org/token input for authenticated sections */}
        <section className="rounded-2xl border border-white/10 bg-white/5 backdrop-blur-xl p-6">
          <p className="text-xs text-slate-400 mb-3 flex items-start gap-1.5"><AlertTriangle size={13} className="mt-0.5 shrink-0" /> Audit log and API key management require an org ID and your access token (from login). This is a dev-facing panel — a production admin UI would pull these from your session automatically.</p>
          <div className="grid sm:grid-cols-2 gap-3">
            <input placeholder="Organization ID" value={orgId} onChange={(e) => setOrgId(e.target.value)} className="rounded-lg bg-black/30 border border-white/10 px-3 py-2 text-sm" />
            <input placeholder="Access token" value={token} onChange={(e) => setToken(e.target.value)} className="rounded-lg bg-black/30 border border-white/10 px-3 py-2 text-sm" />
          </div>
        </section>

        {/* Audit log */}
        <section className="rounded-2xl border border-white/10 bg-white/5 backdrop-blur-xl p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-medium text-sky-300 flex items-center gap-2"><ScrollText size={16} /> Audit Log</h2>
            <button onClick={loadAuditLog} disabled={!orgId || !token || loading === "audit"} className="text-xs px-3 py-1.5 rounded-lg bg-sky-600/20 border border-sky-400/30 hover:bg-sky-600/30 disabled:opacity-50 transition flex items-center gap-1.5">
              {loading === "audit" ? <Loader2 className="animate-spin" size={12} /> : null} Load
            </button>
          </div>
          {auditLog && (
            <div className="space-y-2 text-xs max-h-64 overflow-y-auto">
              {auditLog.length === 0 && <p className="text-slate-500">No audit entries yet.</p>}
              {auditLog.map((entry) => (
                <div key={entry.id} className="border-t border-white/5 pt-2">
                  <div className="flex justify-between text-slate-300"><span>{entry.action} — {entry.entity_type}</span><span className="text-slate-500">{entry.created_at}</span></div>
                  {entry.changes && Object.keys(entry.changes).length > 0 && (
                    <div className="text-slate-500 mt-1">
                      {Object.entries(entry.changes).map(([field, c]: any) => (
                        <div key={field}>{field}: {String(c.before)} → {String(c.after)}</div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </section>

        {/* API Keys */}
        <section className="rounded-2xl border border-white/10 bg-white/5 backdrop-blur-xl p-6">
          <h2 className="text-sm font-medium text-emerald-300 mb-4 flex items-center gap-2"><KeyRound size={16} /> API Keys</h2>
          <div className="flex gap-2 mb-4">
            <input placeholder="Key name (e.g. Zapier integration)" value={newKeyName} onChange={(e) => setNewKeyName(e.target.value)} className="flex-1 rounded-lg bg-black/30 border border-white/10 px-3 py-2 text-sm" />
            <button onClick={createApiKey} disabled={!orgId || !token || !newKeyName.trim() || loading === "create-key"} className="px-4 rounded-lg bg-emerald-600/20 border border-emerald-400/30 hover:bg-emerald-600/30 disabled:opacity-50 text-sm transition">
              {loading === "create-key" ? <Loader2 className="animate-spin" size={14} /> : "Create"}
            </button>
          </div>

          {newKeyPlaintext && (
            <div className="rounded-lg border border-amber-400/30 bg-amber-500/10 p-3 mb-4 text-xs">
              <p className="text-amber-200 mb-1.5">Save this now — it won&apos;t be shown again:</p>
              <div className="flex items-center gap-2 font-mono bg-black/30 rounded px-2 py-1.5">
                <span className="flex-1 truncate">{newKeyPlaintext}</span>
                <button onClick={() => navigator.clipboard.writeText(newKeyPlaintext)} className="text-slate-400 hover:text-white"><Copy size={13} /></button>
              </div>
            </div>
          )}

          <button onClick={loadApiKeys} disabled={!orgId || !token || loading === "keys"} className="text-xs px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 hover:bg-white/10 disabled:opacity-50 transition mb-3">
            Refresh list
          </button>

          {apiKeys && (
            <div className="space-y-2 text-xs">
              {apiKeys.length === 0 && <p className="text-slate-500">No active API keys.</p>}
              {apiKeys.map((k) => (
                <div key={k.id} className="flex items-center justify-between border-t border-white/5 pt-2">
                  <div><span className="text-slate-300">{k.name}</span> <span className="text-slate-500 font-mono ml-2">{k.masked_key}</span></div>
                  <span className="text-slate-500">{k.created_at?.slice(0, 10)}</span>
                </div>
              ))}
            </div>
          )}
        </section>

        {error && <div className="rounded-xl border border-red-400/30 bg-red-500/10 p-4 text-sm text-red-200">{error}</div>}
      </div>
    </main>
  );
}

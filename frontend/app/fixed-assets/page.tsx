"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { Archive, Calculator, History, Loader2, Pencil, Plus, X } from "lucide-react";

type DepreciationMethod = "straight_line" | "wdv";

type FixedAsset = {
  id: string;
  asset_name: string;
  purchase_date: string;
  cost_decimal?: string;
  salvage_value_decimal?: string;
  cost?: number | string;
  salvage_value?: number | string;
  useful_life_years: number;
  depreciation_method: DepreciationMethod;
  is_active: boolean;
};

type AssetForm = {
  asset_name: string;
  purchase_date: string;
  cost: string;
  salvage_value: string;
  useful_life_years: string;
  depreciation_method: DepreciationMethod;
};

type PreviewRow = {
  period: number;
  opening_value: string;
  depreciation: string;
  closing_value: string;
};

type PreviewResult = {
  method: DepreciationMethod;
  wdv_rate_pct: string | null;
  schedule: PreviewRow[];
  disclaimer: string;
};

type AuditEvent = {
  id: string;
  action: string;
  user_id: string | null;
  created_at: string | null;
  changes: Record<string, unknown> | null;
};

const EMPTY_FORM: AssetForm = {
  asset_name: "",
  purchase_date: "",
  cost: "",
  salvage_value: "0.00",
  useful_life_years: "",
  depreciation_method: "straight_line",
};

async function requestJson(path: string, init?: RequestInit) {
  const response = await fetch(path, init);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail || data.error || "Request failed.");
  }
  return data;
}

function formatINR(raw: string | number | undefined) {
  const value = String(raw ?? "0");
  const parts = value.split(".");
  const wholeRaw = parts[0] || "0";
  const negative = wholeRaw.startsWith("-");
  const whole = (negative ? wholeRaw.slice(1) : wholeRaw).replace(/\D/g, "") || "0";
  const lastThree = whole.slice(-3);
  const prefix = whole.slice(0, -3).replace(/\B(?=(\d{2})+(?!\d))/g, ",");
  const fraction = (parts[1] || "").replace(/\D/g, "").padEnd(2, "0").slice(0, 2);
  return (negative ? "-" : "") + "₹" + (prefix ? prefix + "," : "") + lastThree + "." + fraction;
}

function amountFor(asset: FixedAsset, field: "cost" | "salvage_value") {
  if (field === "cost") return asset.cost_decimal ?? asset.cost ?? "0";
  return asset.salvage_value_decimal ?? asset.salvage_value ?? "0";
}

export default function FixedAssetsPage() {
  const [assets, setAssets] = useState<FixedAsset[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [includeArchived, setIncludeArchived] = useState(false);
  const [formOpen, setFormOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<AssetForm>(EMPTY_FORM);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [previewAsset, setPreviewAsset] = useState<FixedAsset | null>(null);
  const [wdvRate, setWdvRate] = useState("");
  const [preview, setPreview] = useState<PreviewResult | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [historyAsset, setHistoryAsset] = useState<FixedAsset | null>(null);
  const [history, setHistory] = useState<AuditEvent[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  const loadAssets = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const query = new URLSearchParams({
        include_inactive: String(includeArchived),
        limit: "50",
        offset: "0",
      });
      const data = await requestJson("/api/fixed-assets?" + query.toString());
      setAssets(Array.isArray(data.assets) ? data.assets : []);
      setTotal(typeof data.total === "number" ? data.total : 0);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load fixed assets.");
    } finally {
      setLoading(false);
    }
  }, [includeArchived]);

  useEffect(() => {
    void loadAssets();
  }, [loadAssets]);

  function startCreate() {
    setEditingId(null);
    setForm(EMPTY_FORM);
    setFormOpen(true);
    setError("");
    setNotice("");
  }

  function startEdit(asset: FixedAsset) {
    setEditingId(asset.id);
    setForm({
      asset_name: asset.asset_name,
      purchase_date: asset.purchase_date,
      cost: String(amountFor(asset, "cost")),
      salvage_value: String(amountFor(asset, "salvage_value")),
      useful_life_years: String(asset.useful_life_years),
      depreciation_method: asset.depreciation_method,
    });
    setFormOpen(true);
    setError("");
    setNotice("");
  }

  function closeForm() {
    setFormOpen(false);
    setEditingId(null);
    setForm(EMPTY_FORM);
  }

  async function saveAsset(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setNotice("");

    if (!form.asset_name.trim() || !form.purchase_date || !form.cost.trim() || !form.useful_life_years.trim()) {
      setError("Enter the asset name, purchase date, cost and useful life.");
      return;
    }

    const years = Number(form.useful_life_years);
    if (!Number.isInteger(years) || years < 1 || years > 32767) {
      setError("Useful life must be a whole number between 1 and 32767 years.");
      return;
    }

    const payload = {
      asset_name: form.asset_name,
      purchase_date: form.purchase_date,
      cost: form.cost,
      salvage_value: form.salvage_value || "0.00",
      useful_life_years: years,
      depreciation_method: form.depreciation_method,
    };

    setSaving(true);
    try {
      if (editingId) {
        await requestJson("/api/fixed-assets/" + encodeURIComponent(editingId), {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        setNotice("Fixed asset updated.");
      } else {
        await requestJson("/api/fixed-assets", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        setNotice("Fixed asset created.");
      }
      closeForm();
      await loadAssets();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save the fixed asset.");
    } finally {
      setSaving(false);
    }
  }

  async function archiveAsset(asset: FixedAsset) {
    if (!window.confirm("Archive " + asset.asset_name + "? Its history will be preserved.")) return;
    setError("");
    setNotice("");
    try {
      await requestJson("/api/fixed-assets/" + encodeURIComponent(asset.id) + "/archive", {
        method: "POST",
      });
      setNotice("Fixed asset archived. Historical records are preserved.");
      await loadAssets();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not archive the fixed asset.");
    }
  }

  function openPreview(asset: FixedAsset) {
    setPreviewAsset(asset);
    setPreview(null);
    setWdvRate("");
    setError("");
  }

  async function runPreview() {
    if (!previewAsset) return;
    if (previewAsset.depreciation_method === "wdv" && !wdvRate.trim()) {
      setError("Enter the WDV rate to use. Solix does not assume a statutory rate.");
      return;
    }

    setPreviewLoading(true);
    setError("");
    try {
      const body = previewAsset.depreciation_method === "wdv" ? { wdv_rate_pct: wdvRate } : {};
      const data = await requestJson(
        "/api/fixed-assets/" + encodeURIComponent(previewAsset.id) + "/depreciation-preview",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }
      );
      setPreview(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not generate the preview.");
    } finally {
      setPreviewLoading(false);
    }
  }

  async function openHistory(asset: FixedAsset) {
    setHistoryAsset(asset);
    setHistory([]);
    setHistoryLoading(true);
    setError("");
    try {
      const data = await requestJson(
        "/api/fixed-assets/" + encodeURIComponent(asset.id) + "/audit-history?limit=20&offset=0"
      );
      setHistory(Array.isArray(data.events) ? data.events : []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load audit history.");
    } finally {
      setHistoryLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-[#0a0a12] text-slate-100 relative overflow-hidden">
      <div className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute top-[-10%] left-[10%] h-[480px] w-[480px] rounded-full bg-teal-600/15 blur-[120px]" />
        <div className="absolute bottom-[-10%] right-[10%] h-[480px] w-[480px] rounded-full bg-indigo-600/15 blur-[120px]" />
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-10">
        <header className="mb-7 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-3xl font-semibold tracking-tight bg-gradient-to-r from-teal-300 to-indigo-300 bg-clip-text text-transparent">
              Fixed Asset Register
            </h1>
            <p className="text-slate-400 mt-1 text-sm">
              Manage asset details, review non-posting depreciation previews and inspect audit history.
            </p>
          </div>
          <button
            type="button"
            onClick={startCreate}
            className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-teal-600 to-indigo-600 px-4 py-2.5 text-sm font-medium hover:from-teal-500 hover:to-indigo-500"
          >
            <Plus size={16} /> Add asset
          </button>
        </header>

        {error && <div role="alert" className="mb-5 rounded-xl border border-red-400/30 bg-red-500/10 p-4 text-sm text-red-200">{error}</div>}
        {notice && <div role="status" className="mb-5 rounded-xl border border-teal-400/30 bg-teal-500/10 p-4 text-sm text-teal-100">{notice}</div>}

        {formOpen && (
          <form onSubmit={saveAsset} className="mb-7 rounded-2xl border border-white/10 bg-white/5 p-5 sm:p-6">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-medium">{editingId ? "Edit fixed asset" : "New fixed asset"}</h2>
              <button type="button" onClick={closeForm} aria-label="Close form" className="rounded-lg p-2 text-slate-400 hover:bg-white/10">
                <X size={16} />
              </button>
            </div>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <label className="text-xs text-slate-400">
                Asset name
                <input required maxLength={255} value={form.asset_name} onChange={(e) => setForm({ ...form, asset_name: e.target.value })} className="mt-1 w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2.5 text-sm text-slate-100" />
              </label>
              <label className="text-xs text-slate-400">
                Purchase date
                <input required type="date" value={form.purchase_date} onChange={(e) => setForm({ ...form, purchase_date: e.target.value })} className="mt-1 w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2.5 text-sm text-slate-100" />
              </label>
              <label className="text-xs text-slate-400">
                Cost (₹)
                <input required type="number" min="0" step="0.01" inputMode="decimal" value={form.cost} onChange={(e) => setForm({ ...form, cost: e.target.value })} className="mt-1 w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2.5 text-sm text-slate-100" />
              </label>
              <label className="text-xs text-slate-400">
                Salvage value (₹)
                <input required type="number" min="0" step="0.01" inputMode="decimal" value={form.salvage_value} onChange={(e) => setForm({ ...form, salvage_value: e.target.value })} className="mt-1 w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2.5 text-sm text-slate-100" />
              </label>
              <label className="text-xs text-slate-400">
                Useful life (years)
                <input required type="number" min="1" max="32767" step="1" value={form.useful_life_years} onChange={(e) => setForm({ ...form, useful_life_years: e.target.value })} className="mt-1 w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2.5 text-sm text-slate-100" />
              </label>
              <label className="text-xs text-slate-400">
                Depreciation method
                <select value={form.depreciation_method} onChange={(e) => setForm({ ...form, depreciation_method: e.target.value as DepreciationMethod })} className="mt-1 w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2.5 text-sm text-slate-100">
                  <option value="straight_line">Straight-line</option>
                  <option value="wdv">Written-down value (WDV)</option>
                </select>
              </label>
            </div>
            <div className="mt-5 flex flex-wrap gap-2">
              <button type="submit" disabled={saving} className="flex items-center gap-2 rounded-xl bg-teal-600 px-4 py-2.5 text-sm font-medium hover:bg-teal-500 disabled:opacity-50">
                {saving ? <Loader2 size={15} className="animate-spin" /> : null}
                {saving ? "Saving..." : editingId ? "Save changes" : "Create asset"}
              </button>
              <button type="button" onClick={closeForm} className="rounded-xl border border-white/10 px-4 py-2.5 text-sm text-slate-300 hover:bg-white/5">Cancel</button>
            </div>
            <p className="mt-3 text-xs text-slate-500">Amounts are sent as decimal strings; the backend validates precision and salvage value.</p>
          </form>
        )}

        <section className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-slate-400">{total} asset{total === 1 ? "" : "s"} in this view</p>
          <label className="flex items-center gap-2 text-xs text-slate-400">
            <input type="checkbox" checked={includeArchived} onChange={(e) => setIncludeArchived(e.target.checked)} className="accent-teal-500" />
            Include archived assets
          </label>
        </section>

        {loading ? (
          <div className="flex items-center gap-2 py-12 text-sm text-slate-400"><Loader2 size={16} className="animate-spin" /> Loading fixed assets...</div>
        ) : assets.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-white/15 bg-white/[0.03] p-10 text-center">
            <p className="text-sm text-slate-300">No fixed assets found.</p>
            <p className="mt-1 text-xs text-slate-500">Add an asset to start a tenant-scoped register. No journal entry is created by this form.</p>
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {assets.map((asset) => (
              <article key={asset.id} className="rounded-2xl border border-white/10 bg-white/5 p-5">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h2 className="font-medium text-slate-100">{asset.asset_name}</h2>
                    <p className="mt-1 text-xs text-slate-500">Purchased {asset.purchase_date}</p>
                  </div>
                  <span className={asset.is_active ? "rounded-full border border-teal-400/30 bg-teal-500/10 px-2.5 py-1 text-[11px] text-teal-200" : "rounded-full border border-slate-500/30 bg-slate-500/10 px-2.5 py-1 text-[11px] text-slate-400"}>
                    {asset.is_active ? "Active" : "Archived"}
                  </span>
                </div>
                <dl className="mt-4 grid grid-cols-2 gap-3 text-xs">
                  <div><dt className="text-slate-500">Cost</dt><dd className="mt-1 font-medium text-slate-200">{formatINR(amountFor(asset, "cost"))}</dd></div>
                  <div><dt className="text-slate-500">Salvage value</dt><dd className="mt-1 font-medium text-slate-200">{formatINR(amountFor(asset, "salvage_value"))}</dd></div>
                  <div><dt className="text-slate-500">Useful life</dt><dd className="mt-1 text-slate-300">{asset.useful_life_years} years</dd></div>
                  <div><dt className="text-slate-500">Method</dt><dd className="mt-1 text-slate-300">{asset.depreciation_method === "wdv" ? "WDV" : "Straight-line"}</dd></div>
                </dl>
                <div className="mt-5 flex flex-wrap gap-2 border-t border-white/10 pt-4">
                  {asset.is_active && (
                    <button type="button" onClick={() => startEdit(asset)} className="flex items-center gap-1.5 rounded-lg border border-white/10 px-3 py-2 text-xs text-slate-300 hover:bg-white/5">
                      <Pencil size={13} /> Edit
                    </button>
                  )}
                  <button type="button" onClick={() => openPreview(asset)} className="flex items-center gap-1.5 rounded-lg border border-white/10 px-3 py-2 text-xs text-slate-300 hover:bg-white/5">
                    <Calculator size={13} /> Preview
                  </button>
                  <button type="button" onClick={() => void openHistory(asset)} className="flex items-center gap-1.5 rounded-lg border border-white/10 px-3 py-2 text-xs text-slate-300 hover:bg-white/5">
                    <History size={13} /> History
                  </button>
                  {asset.is_active && (
                    <button type="button" onClick={() => void archiveAsset(asset)} className="flex items-center gap-1.5 rounded-lg border border-red-400/20 px-3 py-2 text-xs text-red-200 hover:bg-red-500/10">
                      <Archive size={13} /> Archive
                    </button>
                  )}
                </div>
              </article>
            ))}
          </div>
        )}

        {previewAsset && (
          <section className="mt-7 rounded-2xl border border-white/10 bg-white/5 p-5 sm:p-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="font-medium">Depreciation preview · {previewAsset.asset_name}</h2>
                <p className="mt-1 text-xs text-slate-500">Preview only. This does not post a journal entry.</p>
              </div>
              <button type="button" onClick={() => { setPreviewAsset(null); setPreview(null); }} aria-label="Close depreciation preview" className="rounded-lg p-2 text-slate-400 hover:bg-white/10"><X size={16} /></button>
            </div>
            {previewAsset.depreciation_method === "wdv" && (
              <label className="mt-4 block max-w-xs text-xs text-slate-400">
                User-supplied WDV rate (%)
                <input type="number" min="0.01" max="100" step="0.01" value={wdvRate} onChange={(e) => setWdvRate(e.target.value)} className="mt-1 w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2.5 text-sm text-slate-100" />
              </label>
            )}
            <button type="button" onClick={() => void runPreview()} disabled={previewLoading} className="mt-4 flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-medium hover:bg-indigo-500 disabled:opacity-50">
              {previewLoading ? <Loader2 size={15} className="animate-spin" /> : <Calculator size={15} />} Generate preview
            </button>
            {preview && (
              <div className="mt-5 overflow-x-auto">
                <p className="mb-3 text-xs text-slate-400">{preview.method === "wdv" ? "WDV rate: " + preview.wdv_rate_pct + "%" : "Straight-line schedule"}</p>
                <table className="w-full min-w-[520px] text-xs">
                  <thead className="text-slate-400">
                    <tr><th className="pb-2 text-left">Period</th><th className="pb-2 text-right">Opening value</th><th className="pb-2 text-right">Depreciation</th><th className="pb-2 text-right">Closing value</th></tr>
                  </thead>
                  <tbody>
                    {preview.schedule.map((row) => (
                      <tr key={row.period} className="border-t border-white/5">
                        <td className="py-2">{row.period}</td>
                        <td className="py-2 text-right">{formatINR(row.opening_value)}</td>
                        <td className="py-2 text-right">{formatINR(row.depreciation)}</td>
                        <td className="py-2 text-right">{formatINR(row.closing_value)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <p className="mt-4 text-xs leading-relaxed text-amber-200/80">{preview.disclaimer}</p>
              </div>
            )}
          </section>
        )}

        {historyAsset && (
          <section className="mt-7 rounded-2xl border border-white/10 bg-white/5 p-5 sm:p-6">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="font-medium">Audit history · {historyAsset.asset_name}</h2>
                <p className="mt-1 text-xs text-slate-500">Read access depends on the audit-log permission for this organization.</p>
              </div>
              <button type="button" onClick={() => setHistoryAsset(null)} aria-label="Close audit history" className="rounded-lg p-2 text-slate-400 hover:bg-white/10"><X size={16} /></button>
            </div>
            {historyLoading ? (
              <p className="mt-4 flex items-center gap-2 text-xs text-slate-400"><Loader2 size={14} className="animate-spin" /> Loading history...</p>
            ) : history.length === 0 ? (
              <p className="mt-4 text-xs text-slate-500">No audit events are available in this page, or your role cannot view them.</p>
            ) : (
              <div className="mt-4 space-y-3">
                {history.map((event) => (
                  <article key={event.id} className="rounded-xl border border-white/10 bg-black/20 p-3">
                    <div className="flex flex-wrap justify-between gap-2 text-xs">
                      <span className="font-medium text-slate-200">{event.action}</span>
                      <time className="text-slate-500">{event.created_at ? new Date(event.created_at).toLocaleString() : "Time unavailable"}</time>
                    </div>
                    <pre className="mt-2 overflow-x-auto whitespace-pre-wrap break-words text-[11px] text-slate-400">{JSON.stringify(event.changes, null, 2)}</pre>
                  </article>
                ))}
              </div>
            )}
          </section>
        )}

        <p className="mt-7 text-xs text-slate-500">
          Solix displays backend-calculated amounts and schedules. WDV rates are user-supplied, not statutory recommendations. A qualified professional must review accounting treatment before any journal is posted.
        </p>
      </div>
    </main>
  );
}

"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { Archive, ArrowLeftRight, History, Loader2, Package, Pencil, Plus, X } from "lucide-react";

type CostingMethod = "FIFO" | "LIFO" | "WAVG";
type TransactionType = "purchase" | "sale";

type InventoryItem = {
  id: string;
  sku: string;
  name: string;
  costing_method: CostingMethod;
  is_active: boolean;
};

type ItemForm = {
  sku: string;
  name: string;
  costing_method: CostingMethod;
};

type MovementForm = {
  txn_type: TransactionType;
  txn_date: string;
  quantity: string;
  unit_cost: string;
  reference_no: string;
};

type InventoryTransaction = {
  id: string;
  txn_type: TransactionType;
  txn_date: string;
  quantity_decimal?: string;
  quantity: number;
  unit_cost_decimal?: string | null;
  unit_cost?: number | null;
  reference_no: string | null;
  sequence_no: number;
};

const EMPTY_ITEM_FORM: ItemForm = { sku: "", name: "", costing_method: "FIFO" };
const EMPTY_MOVEMENT_FORM: MovementForm = {
  txn_type: "purchase",
  txn_date: "",
  quantity: "",
  unit_cost: "",
  reference_no: "",
};

async function requestJson(path: string, init?: RequestInit) {
  const response = await fetch(path, init);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail || data.error || "Request failed.");
  }
  return data;
}

function formatINR(raw: string | number | null | undefined, minimumFractionDigits = 2) {
  const value = String(raw ?? "0");
  const parts = value.split(".");
  const wholeRaw = parts[0] || "0";
  const negative = wholeRaw.startsWith("-");
  const whole = (negative ? wholeRaw.slice(1) : wholeRaw).replace(/\D/g, "") || "0";
  const lastThree = whole.slice(-3);
  const prefix = whole.slice(0, -3).replace(/\B(?=(\d{2})+(?!\d))/g, ",");
  const sourceFraction = (parts[1] || "").replace(/\D/g, "");
  const fractionDigits = Math.max(minimumFractionDigits, Math.min(sourceFraction.length, 4));
  const fraction = sourceFraction.padEnd(fractionDigits, "0").slice(0, fractionDigits);
  return (negative ? "-" : "") + "₹" + (prefix ? prefix + "," : "") + lastThree + "." + fraction;
}

function formatQuantity(raw: string | number | null | undefined) {
  return String(raw ?? "0");
}

export default function InventoryPage() {
  const [items, setItems] = useState<InventoryItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [includeArchived, setIncludeArchived] = useState(false);
  const [costingMethod, setCostingMethod] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [itemFormOpen, setItemFormOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [itemForm, setItemForm] = useState<ItemForm>(EMPTY_ITEM_FORM);
  const [movementItem, setMovementItem] = useState<InventoryItem | null>(null);
  const [movementForm, setMovementForm] = useState<MovementForm>(EMPTY_MOVEMENT_FORM);
  const [movementSaving, setMovementSaving] = useState(false);
  const [ledgerItem, setLedgerItem] = useState<InventoryItem | null>(null);
  const [transactions, setTransactions] = useState<InventoryTransaction[]>([]);
  const [transactionsLoading, setTransactionsLoading] = useState(false);
  const [orderingNote, setOrderingNote] = useState("");
  const [valuationItem, setValuationItem] = useState<InventoryItem | null>(null);
  const [valuation, setValuation] = useState<any>(null);
  const [valuationLoading, setValuationLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const loadItems = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const query = new URLSearchParams({
        include_inactive: String(includeArchived),
        limit: "50",
        offset: "0",
      });
      if (costingMethod) query.set("costing_method", costingMethod);
      if (search.trim()) query.set("search", search.trim());
      const data = await requestJson("/api/inventory/items?" + query.toString());
      setItems(Array.isArray(data.items) ? data.items : []);
      setTotal(typeof data.total === "number" ? data.total : 0);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load inventory items.");
    } finally {
      setLoading(false);
    }
  }, [includeArchived, costingMethod, search]);

  useEffect(() => {
    void loadItems();
  }, [loadItems]);

  function startCreateItem() {
    setEditingId(null);
    setItemForm(EMPTY_ITEM_FORM);
    setItemFormOpen(true);
    setError("");
    setNotice("");
  }

  function startEditItem(item: InventoryItem) {
    setEditingId(item.id);
    setItemForm({ sku: item.sku, name: item.name, costing_method: item.costing_method });
    setItemFormOpen(true);
    setError("");
    setNotice("");
  }

  function closeItemForm() {
    setItemFormOpen(false);
    setEditingId(null);
    setItemForm(EMPTY_ITEM_FORM);
  }

  async function saveItem(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setNotice("");
    if (!itemForm.sku.trim() || !itemForm.name.trim()) {
      setError("Enter both SKU and item name.");
      return;
    }

    setSaving(true);
    try {
      const path = editingId
        ? "/api/inventory/items/" + encodeURIComponent(editingId)
        : "/api/inventory/items";
      await requestJson(path, {
        method: editingId ? "PATCH" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(itemForm),
      });
      setNotice(editingId ? "Inventory item updated." : "Inventory item created.");
      closeItemForm();
      await loadItems();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save the inventory item.");
    } finally {
      setSaving(false);
    }
  }

  function startMovement(item: InventoryItem) {
    setMovementItem(item);
    setMovementForm(EMPTY_MOVEMENT_FORM);
    setError("");
    setNotice("");
  }

  function closeMovement() {
    setMovementItem(null);
    setMovementForm(EMPTY_MOVEMENT_FORM);
  }

  async function saveMovement(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!movementItem) return;
    setError("");
    setNotice("");

    if (!movementForm.txn_date || !movementForm.quantity.trim() || !movementForm.reference_no.trim()) {
      setError("Enter transaction date, quantity and reference number.");
      return;
    }
    if (movementForm.txn_type === "purchase" && !movementForm.unit_cost.trim()) {
      setError("Enter the unit cost for a purchase.");
      return;
    }

    const payload: Record<string, unknown> = {
      txn_type: movementForm.txn_type,
      txn_date: movementForm.txn_date,
      quantity: movementForm.quantity,
      reference_no: movementForm.reference_no,
    };
    if (movementForm.txn_type === "purchase") payload.unit_cost = movementForm.unit_cost;

    setMovementSaving(true);
    try {
      await requestJson("/api/inventory/items/" + encodeURIComponent(movementItem.id) + "/transactions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const savedItem = movementItem;
      closeMovement();
      setNotice("Movement recorded in the inventory ledger. No general-ledger journal was posted.");
      await Promise.all([loadLedger(savedItem), loadValuation(savedItem)]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not record the inventory movement.");
    } finally {
      setMovementSaving(false);
    }
  }

  async function archiveItem(item: InventoryItem) {
    if (!window.confirm("Archive " + item.sku + " — " + item.name + "? Historical transactions will be preserved.")) return;
    setError("");
    setNotice("");
    try {
      await requestJson("/api/inventory/items/" + encodeURIComponent(item.id) + "/archive", { method: "POST" });
      setNotice("Inventory item archived. Historical transactions are preserved.");
      await loadItems();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not archive the inventory item.");
    }
  }

  async function loadLedger(item: InventoryItem) {
    setLedgerItem(item);
    setTransactionsLoading(true);
    setError("");
    try {
      const data = await requestJson("/api/inventory/items/" + encodeURIComponent(item.id) + "/transactions?limit=50&offset=0");
      setTransactions(Array.isArray(data.transactions) ? data.transactions : []);
      setOrderingNote(data.ordering_note || "");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load the item ledger.");
    } finally {
      setTransactionsLoading(false);
    }
  }

  async function loadValuation(item: InventoryItem) {
    setValuationItem(item);
    setValuationLoading(true);
    setError("");
    try {
      const data = await requestJson("/api/inventory/items/" + encodeURIComponent(item.id) + "/valuation");
      setValuation(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load inventory valuation.");
    } finally {
      setValuationLoading(false);
    }
  }

  function applySearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSearch(searchInput);
  }

  return (
    <main className="min-h-screen bg-[#0a0a12] text-slate-100 relative overflow-hidden">
      <div className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute top-[-10%] left-[10%] h-[480px] w-[480px] rounded-full bg-sky-600/15 blur-[120px]" />
        <div className="absolute bottom-[-10%] right-[10%] h-[480px] w-[480px] rounded-full bg-teal-600/15 blur-[120px]" />
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-10">
        <header className="mb-7 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-3xl font-semibold tracking-tight bg-gradient-to-r from-sky-300 to-teal-300 bg-clip-text text-transparent">
              Inventory Register
            </h1>
            <p className="mt-1 text-sm text-slate-400">Manage SKUs, record purchase and sale movements, and review backend-calculated stock valuation.</p>
          </div>
          <button type="button" onClick={startCreateItem} className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-sky-600 to-teal-600 px-4 py-2.5 text-sm font-medium hover:from-sky-500 hover:to-teal-500">
            <Plus size={16} /> Add item
          </button>
        </header>

        {error && <div role="alert" className="mb-5 rounded-xl border border-red-400/30 bg-red-500/10 p-4 text-sm text-red-200">{error}</div>}
        {notice && <div role="status" className="mb-5 rounded-xl border border-teal-400/30 bg-teal-500/10 p-4 text-sm text-teal-100">{notice}</div>}

        {itemFormOpen && (
          <form onSubmit={saveItem} className="mb-6 rounded-2xl border border-white/10 bg-white/5 p-5">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="font-medium">{editingId ? "Edit inventory item" : "New inventory item"}</h2>
              <button type="button" onClick={closeItemForm} aria-label="Close item form" className="rounded-lg p-2 text-slate-400 hover:bg-white/10"><X size={16} /></button>
            </div>
            <div className="grid gap-4 sm:grid-cols-3">
              <label className="text-xs text-slate-400">SKU
                <input required maxLength={50} value={itemForm.sku} onChange={(e) => setItemForm({ ...itemForm, sku: e.target.value })} className="mt-1 w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2.5 text-sm text-slate-100" />
              </label>
              <label className="text-xs text-slate-400">Item name
                <input required maxLength={255} value={itemForm.name} onChange={(e) => setItemForm({ ...itemForm, name: e.target.value })} className="mt-1 w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2.5 text-sm text-slate-100" />
              </label>
              <label className="text-xs text-slate-400">Costing method
                <select value={itemForm.costing_method} onChange={(e) => setItemForm({ ...itemForm, costing_method: e.target.value as CostingMethod })} className="mt-1 w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2.5 text-sm text-slate-100">
                  <option value="FIFO">FIFO</option>
                  <option value="LIFO">LIFO</option>
                  <option value="WAVG">Weighted average</option>
                </select>
              </label>
            </div>
            <p className="mt-3 text-xs text-slate-500">Costing method cannot be changed after transactions exist. The backend enforces this rule.</p>
            <div className="mt-4 flex flex-wrap gap-2">
              <button type="submit" disabled={saving} className="flex items-center gap-2 rounded-xl bg-sky-600 px-4 py-2.5 text-sm font-medium hover:bg-sky-500 disabled:opacity-50">
                {saving ? <Loader2 size={15} className="animate-spin" /> : null}
                {saving ? "Saving..." : editingId ? "Save changes" : "Create item"}
              </button>
              <button type="button" onClick={closeItemForm} className="rounded-xl border border-white/10 px-4 py-2.5 text-sm text-slate-300 hover:bg-white/5">Cancel</button>
            </div>
          </form>
        )}

        <section className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <form onSubmit={applySearch} className="flex min-w-[250px] flex-1 gap-2">
            <input value={searchInput} onChange={(e) => setSearchInput(e.target.value)} placeholder="Search SKU or item name" maxLength={100} className="min-w-0 flex-1 rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm text-slate-100" />
            <button type="submit" className="rounded-lg border border-white/10 px-3 py-2 text-xs text-slate-300 hover:bg-white/5">Search</button>
          </form>
          <div className="flex flex-wrap items-center gap-3">
            <select value={costingMethod} onChange={(e) => setCostingMethod(e.target.value)} className="rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-xs text-slate-200">
              <option value="">All methods</option>
              <option value="FIFO">FIFO</option>
              <option value="LIFO">LIFO</option>
              <option value="WAVG">Weighted average</option>
            </select>
            <label className="flex items-center gap-2 text-xs text-slate-400">
              <input type="checkbox" checked={includeArchived} onChange={(e) => setIncludeArchived(e.target.checked)} className="accent-sky-500" />
              Include archived
            </label>
          </div>
        </section>

        <p className="mb-3 text-sm text-slate-400">{total} item{total === 1 ? "" : "s"} in this view</p>

        {loading ? (
          <div className="flex items-center gap-2 py-12 text-sm text-slate-400"><Loader2 size={16} className="animate-spin" /> Loading inventory...</div>
        ) : items.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-white/15 bg-white/[0.03] p-10 text-center">
            <Package size={22} className="mx-auto mb-3 text-slate-500" />
            <p className="text-sm text-slate-300">No inventory items found.</p>
            <p className="mt-1 text-xs text-slate-500">Create an item before recording stock movements. No sample inventory is inserted.</p>
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {items.map((item) => (
              <article key={item.id} className="rounded-2xl border border-white/10 bg-white/5 p-5">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-[11px] uppercase tracking-wide text-slate-500">{item.sku}</p>
                    <h2 className="mt-1 font-medium text-slate-100">{item.name}</h2>
                  </div>
                  <span className={item.is_active ? "rounded-full border border-sky-400/30 bg-sky-500/10 px-2.5 py-1 text-[11px] text-sky-200" : "rounded-full border border-slate-500/30 bg-slate-500/10 px-2.5 py-1 text-[11px] text-slate-400"}>
                    {item.is_active ? "Active" : "Archived"}
                  </span>
                </div>
                <p className="mt-3 text-xs text-slate-400">Costing method: <span className="text-slate-200">{item.costing_method}</span></p>
                <div className="mt-5 flex flex-wrap gap-2 border-t border-white/10 pt-4">
                  {item.is_active && (
                    <>
                      <button type="button" onClick={() => startEditItem(item)} className="flex items-center gap-1.5 rounded-lg border border-white/10 px-3 py-2 text-xs text-slate-300 hover:bg-white/5"><Pencil size={13} /> Edit</button>
                      <button type="button" onClick={() => startMovement(item)} className="flex items-center gap-1.5 rounded-lg border border-white/10 px-3 py-2 text-xs text-slate-300 hover:bg-white/5"><ArrowLeftRight size={13} /> Movement</button>
                      <button type="button" onClick={() => void archiveItem(item)} className="flex items-center gap-1.5 rounded-lg border border-red-400/20 px-3 py-2 text-xs text-red-200 hover:bg-red-500/10"><Archive size={13} /> Archive</button>
                    </>
                  )}
                  <button type="button" onClick={() => void loadLedger(item)} className="flex items-center gap-1.5 rounded-lg border border-white/10 px-3 py-2 text-xs text-slate-300 hover:bg-white/5"><History size={13} /> Transactions</button>
                  <button type="button" onClick={() => void loadValuation(item)} className="flex items-center gap-1.5 rounded-lg border border-white/10 px-3 py-2 text-xs text-slate-300 hover:bg-white/5">Valuation</button>
                </div>
              </article>
            ))}
          </div>
        )}

        {movementItem && (
          <form onSubmit={saveMovement} className="mt-7 rounded-2xl border border-white/10 bg-white/5 p-5 sm:p-6">
            <div className="mb-4 flex items-center justify-between gap-3">
              <div><h2 className="font-medium">Record movement · {movementItem.name}</h2><p className="mt-1 text-xs text-slate-500">Sales use the selected costing method; unit cost is not entered for a sale.</p></div>
              <button type="button" onClick={closeMovement} aria-label="Close movement form" className="rounded-lg p-2 text-slate-400 hover:bg-white/10"><X size={16} /></button>
            </div>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <label className="text-xs text-slate-400">Movement type
                <select value={movementForm.txn_type} onChange={(e) => setMovementForm({ ...movementForm, txn_type: e.target.value as TransactionType, unit_cost: "" })} className="mt-1 w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2.5 text-sm text-slate-100">
                  <option value="purchase">Purchase</option><option value="sale">Sale</option>
                </select>
              </label>
              <label className="text-xs text-slate-400">Transaction date
                <input required type="date" value={movementForm.txn_date} onChange={(e) => setMovementForm({ ...movementForm, txn_date: e.target.value })} className="mt-1 w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2.5 text-sm text-slate-100" />
              </label>
              <label className="text-xs text-slate-400">Quantity
                <input required type="number" min="0.0001" step="0.0001" value={movementForm.quantity} onChange={(e) => setMovementForm({ ...movementForm, quantity: e.target.value })} className="mt-1 w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2.5 text-sm text-slate-100" />
              </label>
              {movementForm.txn_type === "purchase" ? (
                <label className="text-xs text-slate-400">Unit cost (₹)
                  <input required type="number" min="0" step="0.0001" value={movementForm.unit_cost} onChange={(e) => setMovementForm({ ...movementForm, unit_cost: e.target.value })} className="mt-1 w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2.5 text-sm text-slate-100" />
                </label>
              ) : (
                <div className="rounded-lg border border-sky-400/20 bg-sky-500/5 p-3 text-xs text-sky-100">Unit cost is calculated by the backend from the item&apos;s FIFO/LIFO/weighted-average layers.</div>
              )}
              <label className="text-xs text-slate-400">Reference number
                <input required maxLength={100} value={movementForm.reference_no} onChange={(e) => setMovementForm({ ...movementForm, reference_no: e.target.value })} className="mt-1 w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2.5 text-sm text-slate-100" />
              </label>
            </div>
            <div className="mt-5 flex flex-wrap gap-2">
              <button type="submit" disabled={movementSaving} className="flex items-center gap-2 rounded-xl bg-sky-600 px-4 py-2.5 text-sm font-medium hover:bg-sky-500 disabled:opacity-50">
                {movementSaving ? <Loader2 size={15} className="animate-spin" /> : null}
                {movementSaving ? "Posting..." : "Record movement"}
              </button>
              <button type="button" onClick={closeMovement} className="rounded-xl border border-white/10 px-4 py-2.5 text-sm text-slate-300 hover:bg-white/5">Cancel</button>
            </div>
            <p className="mt-3 text-xs text-slate-500">The inventory movement and audit event are recorded together. This action does not post a general-ledger journal entry.</p>
          </form>
        )}

        {ledgerItem && (
          <section className="mt-7 rounded-2xl border border-white/10 bg-white/5 p-5 sm:p-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div><h2 className="font-medium">Transaction ledger · {ledgerItem.name}</h2><p className="mt-1 text-xs text-slate-500">{transactions.length} transaction rows on this page</p></div>
              <button type="button" onClick={() => setLedgerItem(null)} aria-label="Close transaction ledger" className="rounded-lg p-2 text-slate-400 hover:bg-white/10"><X size={16} /></button>
            </div>
            {transactionsLoading ? (
              <p className="mt-4 flex items-center gap-2 text-xs text-slate-400"><Loader2 size={14} className="animate-spin" /> Loading transactions...</p>
            ) : transactions.length === 0 ? (
              <p className="mt-4 text-xs text-slate-500">No inventory transactions recorded.</p>
            ) : (
              <div className="mt-4 overflow-x-auto">
                <table className="w-full min-w-[650px] text-xs">
                  <thead className="text-slate-400"><tr><th className="pb-2 text-left">Date</th><th className="pb-2 text-left">Type</th><th className="pb-2 text-right">Quantity</th><th className="pb-2 text-right">Unit cost</th><th className="pb-2 text-left">Reference</th><th className="pb-2 text-right">Sequence</th></tr></thead>
                  <tbody>
                    {transactions.map((row) => (
                      <tr key={row.id} className="border-t border-white/5">
                        <td className="py-2">{row.txn_date}</td>
                        <td className="py-2 capitalize">{row.txn_type}</td>
                        <td className="py-2 text-right">{formatQuantity(row.quantity_decimal ?? row.quantity)}</td>
                        <td className="py-2 text-right">{row.unit_cost_decimal !== null && row.unit_cost_decimal !== undefined ? formatINR(row.unit_cost_decimal, 4) : "Costed on sale"}</td>
                        <td className="py-2">{row.reference_no || "—"}</td>
                        <td className="py-2 text-right">{row.sequence_no}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {orderingNote && <p className="mt-4 text-xs leading-relaxed text-amber-200/70">{orderingNote}</p>}
          </section>
        )}

        {valuationItem && (
          <section className="mt-7 rounded-2xl border border-white/10 bg-white/5 p-5 sm:p-6">
            <div className="flex items-center justify-between gap-3">
              <div><h2 className="font-medium">Inventory valuation · {valuationItem.name}</h2><p className="mt-1 text-xs text-slate-500">Calculated by the backend from the persisted item ledger.</p></div>
              <button type="button" onClick={() => { setValuationItem(null); setValuation(null); }} aria-label="Close valuation" className="rounded-lg p-2 text-slate-400 hover:bg-white/10"><X size={16} /></button>
            </div>
            {valuationLoading ? (
              <p className="mt-4 flex items-center gap-2 text-xs text-slate-400"><Loader2 size={14} className="animate-spin" /> Calculating valuation...</p>
            ) : valuation ? (
              <>
                <div className="mt-4 grid gap-3 sm:grid-cols-3">
                  <div className="rounded-xl border border-white/10 bg-black/20 p-4"><p className="text-xs text-slate-500">Closing quantity</p><p className="mt-1 text-lg font-semibold">{formatQuantity(valuation.valuation?.decimal?.closing_quantity ?? valuation.valuation?.closing_quantity)}</p></div>
                  <div className="rounded-xl border border-white/10 bg-black/20 p-4"><p className="text-xs text-slate-500">Closing inventory value</p><p className="mt-1 text-lg font-semibold">{formatINR(valuation.valuation?.decimal?.closing_inventory_value ?? valuation.valuation?.closing_inventory_value)}</p></div>
                  <div className="rounded-xl border border-white/10 bg-black/20 p-4"><p className="text-xs text-slate-500">Cost of goods sold</p><p className="mt-1 text-lg font-semibold">{formatINR(valuation.valuation?.decimal?.cogs ?? valuation.valuation?.cogs)}</p></div>
                </div>
                <p className="mt-3 text-xs text-slate-400">Method: {valuation.item?.costing_method} · {valuation.transaction_count} transactions</p>
                <p className="mt-3 text-xs leading-relaxed text-amber-200/70">{valuation.ordering_note}</p>
              </>
            ) : null}
          </section>
        )}

        <p className="mt-7 text-xs leading-relaxed text-slate-500">
          Inventory movements are stored in the item ledger and audited. This screen does not post general-ledger journals; review and post any required accounting entries separately.
        </p>
      </div>
    </main>
  );
}

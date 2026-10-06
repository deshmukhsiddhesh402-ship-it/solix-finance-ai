/**
 * Proxy route: forwards Accounting module requests to the FastAPI backend.
 */
import { NextRequest, NextResponse } from "next/server";
import { getBackendAuthHeaders } from "@/lib/backend-auth";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

const ACTION_TO_PATH: Record<string, string> = {
  trialBalance: "/api/accounting/trial-balance",
  profitAndLoss: "/api/accounting/profit-and-loss",
  balanceSheet: "/api/accounting/balance-sheet",
  ratios: "/api/accounting/ratios",
  straightLineDepreciation: "/api/accounting/depreciation/straight-line",
  wdvDepreciation: "/api/accounting/depreciation/wdv",
  inventoryValuation: "/api/accounting/inventory/valuation",
};

export async function POST(req: NextRequest) {
  const auth = await getBackendAuthHeaders();
  if (!auth) return NextResponse.json({ error: "Authentication required." }, { status: 401 });
  const body = await req.json();
  const { action, ...payload } = body;

  const path = ACTION_TO_PATH[action];
  payload.org_id = auth.orgId;
  if (!path) {
    return NextResponse.json({ error: `Unknown action: ${action}` }, { status: 400 });
  }

  try {
    const res = await fetch(`${BACKEND_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...auth.headers },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    return NextResponse.json(
      { error: "Could not reach the Solix backend. Is it running on :8000?" },
      { status: 502 }
    );
  }
}

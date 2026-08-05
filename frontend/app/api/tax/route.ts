/**
 * Proxy route: forwards Indian Tax module requests to the FastAPI backend.
 */
import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

const ACTION_TO_PATH: Record<string, string> = {
  gstCalculate: "/api/tax/gst/calculate",
  gstr3bSummary: "/api/tax/gst/gstr3b-summary",
  tdsCalculate: "/api/tax/tds/calculate",
  incomeTaxNewRegime: "/api/tax/income-tax/new-regime",
};

export async function POST(req: NextRequest) {
  const body = await req.json();
  const { action, ...payload } = body;

  const path = ACTION_TO_PATH[action];
  if (!path) {
    return NextResponse.json({ error: `Unknown action: ${action}` }, { status: 400 });
  }

  try {
    const res = await fetch(`${BACKEND_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
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

/**
 * Proxy route: forwards AI Excel Assistant requests from the browser to the
 * FastAPI backend. Keeping this as a server-side proxy (instead of calling
 * the backend directly from the client) means we can later inject auth
 * tokens/rate limiting here without touching frontend components.
 */
import { NextRequest, NextResponse } from "next/server";
import { getBackendAuthHeaders } from "@/lib/backend-auth";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

// Maps the frontend "action" to the corresponding FastAPI endpoint.
const ACTION_TO_PATH: Record<string, string> = {
  explain: "/api/excel-ai/explain-formula",
  generate: "/api/excel-ai/generate-formula",
  fix: "/api/excel-ai/fix-formula",
  vba: "/api/excel-ai/generate-vba",
  officeScript: "/api/excel-ai/generate-office-script",
  pivotPlan: "/api/excel-ai/plan-pivot-table",
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

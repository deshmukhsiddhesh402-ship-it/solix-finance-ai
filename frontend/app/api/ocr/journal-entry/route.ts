import { NextRequest, NextResponse } from "next/server";
import { getBackendAuthHeaders } from "@/lib/backend-auth";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

export async function POST(req: NextRequest) {
  const auth = await getBackendAuthHeaders();
  if (!auth) return NextResponse.json({ error: "Authentication required." }, { status: 401 });
  const body = await req.json();
  body.org_id = auth.orgId;
  try {
    const res = await fetch(`${BACKEND_URL}/api/ocr/to-journal-entry`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...auth.headers },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    return NextResponse.json({ error: "Could not reach the Solix backend. Is it running on :8000?" }, { status: 502 });
  }
}

import { NextRequest, NextResponse } from "next/server";
import { getBackendAuthHeaders } from "@/lib/backend-auth";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

export async function GET(req: NextRequest) {
  const auth = await getBackendAuthHeaders();
  if (!auth) return NextResponse.json({ error: "Authentication required" }, { status: 401 });

  const params = new URLSearchParams(req.nextUrl.searchParams);
  params.set("org_id", auth.orgId);

  try {
    const res = await fetch(`${BACKEND_URL}/api/dashboard/summary?${params.toString()}`, {
      headers: auth.headers,
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json({ error: "Could not reach the Solix backend. Is it running on :8000?" }, { status: 502 });
  }
}

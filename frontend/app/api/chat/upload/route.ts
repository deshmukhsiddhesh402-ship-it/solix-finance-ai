/**
 * Proxy route for document upload — forwards the multipart form data
 * straight through to FastAPI, which handles extraction + chunking + indexing.
 */
import { NextRequest, NextResponse } from "next/server";
import { getBackendAuthHeaders } from "@/lib/backend-auth";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

export async function POST(req: NextRequest) {
  const auth = await getBackendAuthHeaders();
  if (!auth) return NextResponse.json({ error: "Authentication required" }, { status: 401 });
  try {
    const formData = await req.formData();
    formData.set("org_id", auth.orgId);
    const res = await fetch(`${BACKEND_URL}/api/chat/upload`, {
      method: "POST",
      body: formData,
      headers: auth.headers,
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

import { NextRequest, NextResponse } from "next/server";
import { getBackendAuthHeaders } from "@/lib/backend-auth";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

type BackendMethod = "GET" | "POST" | "PATCH";

export async function proxyFixedAssetRequest(
  request: NextRequest,
  path: string,
  method: BackendMethod,
  body?: unknown,
  forwardedQueryKeys: string[] = []
) {
  const auth = await getBackendAuthHeaders();
  if (!auth) {
    return NextResponse.json({ error: "Authentication required." }, { status: 401 });
  }

  const target = new URL(path, BACKEND_URL);
  target.searchParams.set("org_id", auth.orgId);
  for (const key of forwardedQueryKeys) {
    const value = request.nextUrl.searchParams.get(key);
    if (value !== null) target.searchParams.set(key, value);
  }

  const headers: Record<string, string> = { ...auth.headers };
  const init: RequestInit = { method, headers };
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(body);
  }

  try {
    const response = await fetch(target.toString(), init);
    const data = await response.json().catch(() => ({ error: "Backend returned an invalid response." }));
    return NextResponse.json(data, { status: response.status });
  } catch {
    return NextResponse.json(
      { error: "Could not reach the Solix backend. Is it running on :8000?" },
      { status: 502 }
    );
  }
}

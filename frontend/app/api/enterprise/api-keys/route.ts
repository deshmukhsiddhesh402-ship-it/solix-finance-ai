import { NextRequest, NextResponse } from "next/server";
import { getBackendAuthHeaders } from "@/lib/backend-auth";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

export async function GET(req: NextRequest) {
  const search = req.nextUrl.search;
  const authHeader = req.headers.get("authorization") || "";
  try {
    const res = await fetch(`${BACKEND_URL}/api/enterprise/api-keys${search}`, {
      headers: auth.headers,
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    return NextResponse.json({ error: "Could not reach the Solix backend. Is it running on :8000?" }, { status: 502 });
  }
}

export async function POST(req: NextRequest) {
  const body = await req.json();
  const authHeader = req.headers.get("authorization") || "";
  try {
    const res = await fetch(`${BACKEND_URL}/api/enterprise/api-keys`, {
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

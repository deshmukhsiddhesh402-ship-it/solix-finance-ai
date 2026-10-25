import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

const ACTION_TO_PATH: Record<string, string> = {
  "journal-entry": "/api/accounting-simulator/practice/journal-entry",
  "accounting-cycle": "/api/accounting-simulator/practice/accounting-cycle",
  "cash-book": "/api/accounting-simulator/practice/cash-book",
};

export async function POST(req: NextRequest) {
  const action = req.headers.get("x-solix-simulator-action") || "";
  const path = ACTION_TO_PATH[action];

  if (!path) {
    return NextResponse.json({ detail: "Unsupported simulator action." }, { status: 400 });
  }

  const declaredLength = Number(req.headers.get("content-length") || "0");
  if (declaredLength > 100_000) {
    return NextResponse.json({ detail: "Request is too large for practice mode." }, { status: 413 });
  }

  let payload: unknown;
  try {
    payload = await req.json();
  } catch {
    return NextResponse.json({ detail: "Request body must be valid JSON." }, { status: 400 });
  }

  try {
    const response = await fetch(`${BACKEND_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      cache: "no-store",
    });
    const data = await response.json().catch(() => ({ detail: "Backend returned an invalid response." }));
    return NextResponse.json(data, { status: response.status });
  } catch {
    return NextResponse.json(
      { detail: "Could not reach the Solix backend. Check BACKEND_URL and backend availability." },
      { status: 502 }
    );
  }
}

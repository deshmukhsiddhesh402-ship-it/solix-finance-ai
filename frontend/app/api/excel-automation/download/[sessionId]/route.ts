import { NextRequest, NextResponse } from "next/server";
import { getBackendAuthHeaders } from "@/lib/backend-auth";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

export async function GET(req: NextRequest, { params }: { params: { sessionId: string } }) {
  const auth = await getBackendAuthHeaders();
  if (!auth) return NextResponse.json({ error: "Authentication required." }, { status: 401 });
  try {
    const res = await fetch(`${BACKEND_URL}/api/excel-automation/download/${params.sessionId}?org_id=${encodeURIComponent(auth.orgId)}`, { headers: auth.headers });
    if (!res.ok) {
      const data = await res.json();
      return NextResponse.json(data, { status: res.status });
    }
    const blob = await res.arrayBuffer();
    return new NextResponse(blob, {
      headers: {
        "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "Content-Disposition": "attachment; filename=solix_cleaned_data.xlsx",
      },
    });
  } catch (err) {
    return NextResponse.json(
      { error: "Could not reach the Solix backend. Is it running on :8000?" },
      { status: 502 }
    );
  }
}

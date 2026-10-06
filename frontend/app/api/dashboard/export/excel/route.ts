import { NextRequest, NextResponse } from "next/server";
import { getBackendAuthHeaders } from "@/lib/backend-auth";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

export async function GET(req: NextRequest) {
  const auth = await getBackendAuthHeaders();
  if (!auth) return NextResponse.json({ error: "Authentication required." }, { status: 401 });
  const params = new URLSearchParams(req.nextUrl.searchParams);
  params.set("org_id", auth.orgId);
  const search = `?${params.toString()}`;
  try {
    const res = await fetch(`${BACKEND_URL}/api/dashboard/export/excel${search}`, { headers: auth.headers });
    if (!res.ok) return NextResponse.json(await res.json(), { status: res.status });
    const blob = await res.arrayBuffer();
    return new NextResponse(blob, {
      headers: {
        "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "Content-Disposition": "attachment; filename=solix_dashboard_report.xlsx",
      },
    });
  } catch (err) {
    return NextResponse.json({ error: "Could not reach the Solix backend. Is it running on :8000?" }, { status: 502 });
  }
}

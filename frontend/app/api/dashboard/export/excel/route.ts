import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

export async function GET(req: NextRequest) {
  const search = req.nextUrl.search;
  try {
    const res = await fetch(`${BACKEND_URL}/api/dashboard/export/excel${search}`);
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

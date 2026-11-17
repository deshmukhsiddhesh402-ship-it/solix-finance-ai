import { NextRequest, NextResponse } from "next/server";
import { proxyFixedAssetRequest } from "@/lib/fixed-assets-proxy";

const LIST_QUERY_KEYS = [
  "purchase_date_from",
  "purchase_date_to",
  "depreciation_method",
  "include_inactive",
  "limit",
  "offset",
];

export async function GET(request: NextRequest) {
  return proxyFixedAssetRequest(
    request,
    "/api/accounting/fixed-assets",
    "GET",
    undefined,
    LIST_QUERY_KEYS
  );
}

export async function POST(request: NextRequest) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }
  return proxyFixedAssetRequest(request, "/api/accounting/fixed-assets", "POST", body);
}

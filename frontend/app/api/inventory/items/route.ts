import { NextRequest, NextResponse } from "next/server";
import { proxyInventoryRequest } from "@/lib/inventory-proxy";

const LIST_QUERY_KEYS = ["costing_method", "search", "include_inactive", "limit", "offset"];

export async function GET(request: NextRequest) {
  return proxyInventoryRequest(
    request,
    "/api/accounting/inventory/items",
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
  return proxyInventoryRequest(request, "/api/accounting/inventory/items", "POST", body);
}

import { NextRequest, NextResponse } from "next/server";
import { proxyInventoryRequest } from "@/lib/inventory-proxy";

type RouteContext = { params: Promise<{ segments: string[] }> };

function notFound() {
  return NextResponse.json({ error: "Inventory action not found." }, { status: 404 });
}

async function readJson(request: NextRequest) {
  try {
    return await request.json();
  } catch {
    return null;
  }
}

export async function PATCH(request: NextRequest, context: RouteContext) {
  const { segments: routeSegments } = await context.params;
  const segments = routeSegments || [];
  if (segments.length !== 1) return notFound();

  const body = await readJson(request);
  if (body === null) return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });

  return proxyInventoryRequest(
    request,
    "/api/accounting/inventory/items/" + encodeURIComponent(segments[0]),
    "PATCH",
    body
  );
}

export async function POST(request: NextRequest, context: RouteContext) {
  const segments = context.params.segments || [];
  if (segments.length !== 2) return notFound();

  const itemId = encodeURIComponent(segments[0]);
  const action = segments[1];

  if (action === "archive") {
    return proxyInventoryRequest(
      request,
      "/api/accounting/inventory/items/" + itemId + "/archive",
      "POST"
    );
  }

  if (action === "transactions") {
    const body = await readJson(request);
    if (body === null) return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
    return proxyInventoryRequest(
      request,
      "/api/accounting/inventory/items/" + itemId + "/transactions",
      "POST",
      body
    );
  }

  return notFound();
}

export async function GET(request: NextRequest, context: RouteContext) {
  const segments = context.params.segments || [];
  if (segments.length !== 2) return notFound();

  const itemId = encodeURIComponent(segments[0]);
  const action = segments[1];

  if (action === "transactions") {
    return proxyInventoryRequest(
      request,
      "/api/accounting/inventory/items/" + itemId + "/transactions",
      "GET",
      undefined,
      ["start_date", "end_date", "txn_type", "limit", "offset"]
    );
  }

  if (action === "valuation") {
    return proxyInventoryRequest(
      request,
      "/api/accounting/inventory/items/" + itemId + "/valuation",
      "GET"
    );
  }

  return notFound();
}

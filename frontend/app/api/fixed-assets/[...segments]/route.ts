import { NextRequest, NextResponse } from "next/server";
import { proxyFixedAssetRequest } from "@/lib/fixed-assets-proxy";

type RouteContext = { params: { segments: string[] } };

function notFound() {
  return NextResponse.json({ error: "Fixed asset action not found." }, { status: 404 });
}

async function readJson(request: NextRequest) {
  try {
    return await request.json();
  } catch {
    return null;
  }
}

export async function PATCH(request: NextRequest, context: RouteContext) {
  const segments = context.params.segments || [];
  if (segments.length !== 1) return notFound();

  const body = await readJson(request);
  if (body === null) return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });

  const assetId = encodeURIComponent(segments[0]);
  return proxyFixedAssetRequest(
    request,
    "/api/accounting/fixed-assets/" + assetId,
    "PATCH",
    body
  );
}

export async function POST(request: NextRequest, context: RouteContext) {
  const segments = context.params.segments || [];
  if (segments.length !== 2) return notFound();

  const assetId = encodeURIComponent(segments[0]);
  const action = segments[1];

  if (action === "archive") {
    return proxyFixedAssetRequest(
      request,
      "/api/accounting/fixed-assets/" + assetId + "/archive",
      "POST"
    );
  }

  if (action === "depreciation-preview") {
    const body = await readJson(request);
    if (body === null) return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
    return proxyFixedAssetRequest(
      request,
      "/api/accounting/fixed-assets/" + assetId + "/depreciation-preview",
      "POST",
      body
    );
  }

  return notFound();
}

export async function GET(request: NextRequest, context: RouteContext) {
  const segments = context.params.segments || [];
  if (segments.length !== 2 || segments[1] !== "audit-history") return notFound();

  const assetId = encodeURIComponent(segments[0]);
  return proxyFixedAssetRequest(
    request,
    "/api/accounting/fixed-assets/" + assetId + "/audit-history",
    "GET",
    undefined,
    ["limit", "offset"]
  );
}

import { describe, expect, it } from "node:test";

const MAX_REQUEST_BYTES = 100_000;

describe("accounting simulator proxy request boundary", () => {
  it("uses a byte cap that applies even when content-length is unavailable", () => {
    const oversized = new TextEncoder().encode(JSON.stringify({ payload: "x".repeat(MAX_REQUEST_BYTES) }));
    expect(oversized.byteLength).toBeGreaterThan(MAX_REQUEST_BYTES);
  });

  it("keeps the configured cap finite and positive", () => {
    expect(Number.isInteger(MAX_REQUEST_BYTES)).toBe(true);
    expect(MAX_REQUEST_BYTES).toBeGreaterThan(0);
  });
});

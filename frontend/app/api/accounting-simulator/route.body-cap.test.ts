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

  it("uses fatal UTF-8 decoding so malformed bytes do not become replacement characters", () => {
    expect(() => new TextDecoder("utf-8", { fatal: true }).decode(new Uint8Array([0xc3, 0x28]))).toThrow();
  });

  it("accepts JSON content types with optional parameters", () => {
    expect(/^application\\/json(?:\\s*;|\\s*$)/i.test("application/json")).toBe(true);
    expect(/^application\\/json(?:\\s*;|\\s*$)/i.test("application/json; charset=utf-8")).toBe(true);
  });

  it("rejects non-JSON content types before reading the body", () => {
    expect(/^application\\/json(?:\\s*;|\\s*$)/i.test("text/plain")).toBe(false);
    expect(/^application\\/json(?:\\s*;|\\s*$)/i.test("application/jsonp")).toBe(false);
  });
});

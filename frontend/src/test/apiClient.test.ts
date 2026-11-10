import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { request, ApiClientError, api } from "../api/client";

describe("API Client & RFC 7807 Error Handling", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("successfully parses 200 OK JSON responses", async () => {
    const mockData = { id: "case-123", title: "Test Case" };
    vi.spyOn(global, "fetch").mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => mockData,
    } as Response);

    const result = await api.get<{ id: string; title: string }>("/cases/case-123");
    expect(result).toEqual(mockData);
  });

  it("handles 204 No Content returning an empty object", async () => {
    vi.spyOn(global, "fetch").mockResolvedValueOnce({
      ok: true,
      status: 204,
    } as Response);

    const result = await request("/cases/case-123", { method: "DELETE" });
    expect(result).toEqual({});
  });

  it("extracts RFC 7807 error envelopes from failed responses", async () => {
    const errorPayload = {
      error: {
        code: "ENTITY_NOT_FOUND",
        message: "Case case-404 not found.",
        details: { case_id: "case-404" },
      },
    };

    vi.spyOn(global, "fetch").mockResolvedValue({
      ok: false,
      status: 404,
      statusText: "Not Found",
      json: async () => errorPayload,
    } as unknown as Response);

    await expect(api.get("/cases/case-404")).rejects.toThrowError(ApiClientError);

    try {
      await api.get("/cases/case-404");
    } catch (err) {
      const apiErr = err as ApiClientError;
      expect(apiErr.code).toBe("ENTITY_NOT_FOUND");
      expect(apiErr.status).toBe(404);
      expect(apiErr.message).toBe("Case case-404 not found.");
      expect(apiErr.details).toEqual({ case_id: "case-404" });
    }
  });

  it("falls back to HTTP status when error body is not JSON", async () => {
    vi.spyOn(global, "fetch").mockResolvedValueOnce({
      ok: false,
      status: 502,
      statusText: "Bad Gateway",
      json: async () => {
        throw new Error("Invalid JSON");
      },
    } as unknown as Response);

    try {
      await api.get("/health");
    } catch (err) {
      const apiErr = err as ApiClientError;
      expect(apiErr.status).toBe(502);
      expect(apiErr.code).toBe("HTTP_502");
    }
  });
});

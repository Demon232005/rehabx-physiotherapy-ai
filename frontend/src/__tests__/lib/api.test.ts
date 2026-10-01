import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { getToken, clearSession, api, API_BASE } from "@/lib/api";

describe("getToken", () => {
  it("returns null when window is undefined (SSR)", () => {
    const originalWindow = globalThis.window;
    // @ts-expect-error simulating SSR
    delete globalThis.window;
    expect(getToken()).toBeNull();
    globalThis.window = originalWindow;
  });

  it("returns stored token when present", () => {
    window.localStorage.setItem("rehabx_token", "test-token");
    expect(getToken()).toBe("test-token");
    window.localStorage.removeItem("rehabx_token");
  });

  it("returns null when no token is stored", () => {
    window.localStorage.removeItem("rehabx_token");
    expect(getToken()).toBeNull();
  });
});

describe("clearSession", () => {
  beforeEach(() => {
    window.localStorage.setItem("rehabx_token", "token123");
    window.localStorage.setItem("rehabx_user", '{"id":"1"}');
  });

  afterEach(() => {
    window.localStorage.clear();
  });

  it("removes token from localStorage", () => {
    clearSession();
    expect(window.localStorage.getItem("rehabx_token")).toBeNull();
  });

  it("removes user from localStorage", () => {
    clearSession();
    expect(window.localStorage.getItem("rehabx_user")).toBeNull();
  });
});

describe("api", () => {
  const fakeFetch = vi.fn();

  beforeEach(() => {
    vi.stubGlobal("fetch", fakeFetch);
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("sets Authorization header when token exists", async () => {
    window.localStorage.setItem("rehabx_token", "my-token");
    fakeFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ data: 1 }),
    });

    await api("/test");

    const [, init] = fakeFetch.mock.calls[0];
    expect(init.headers.get("Authorization")).toBe("Bearer my-token");
  });

  it("does not set Authorization header when withAuth is false", async () => {
    window.localStorage.setItem("rehabx_token", "my-token");
    fakeFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ data: 1 }),
    });

    await api("/test", {}, false);

    const [, init] = fakeFetch.mock.calls[0];
    expect(init.headers.get("Authorization")).toBeNull();
  });

  it("sets Content-Type header for string body", async () => {
    fakeFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ data: 1 }),
    });

    await api("/test", {
      method: "POST",
      body: JSON.stringify({ key: "value" }),
    });

    const [, init] = fakeFetch.mock.calls[0];
    expect(init.headers.get("Content-Type")).toBe("application/json");
  });

  it("does not override existing Content-Type", async () => {
    fakeFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ data: 1 }),
    });

    await api("/test", {
      method: "POST",
      headers: { "Content-Type": "text/plain" },
      body: "hello",
    });

    const [, init] = fakeFetch.mock.calls[0];
    expect(init.headers.get("Content-Type")).toBe("text/plain");
  });

  it("calls fetch with correct URL", async () => {
    fakeFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({}),
    });

    await api("/users/me");

    expect(fakeFetch).toHaveBeenCalledWith(
      `${API_BASE}/users/me`,
      expect.anything(),
    );
  });

  it("throws error with status on non-ok response", async () => {
    fakeFetch.mockResolvedValueOnce({
      ok: false,
      status: 404,
      json: async () => ({ detail: "Not found" }),
    });

    await expect(api("/missing")).rejects.toThrow("Not found");
  });

  it("returns parsed JSON on success", async () => {
    fakeFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ id: 1, name: "test" }),
    });

    const result = await api<{ id: number; name: string }>("/data");
    expect(result).toEqual({ id: 1, name: "test" });
  });

  it("returns undefined for 204 response", async () => {
    fakeFetch.mockResolvedValueOnce({
      ok: true,
      status: 204,
    });

    const result = await api("/delete-endpoint");
    expect(result).toBeUndefined();
  });
});

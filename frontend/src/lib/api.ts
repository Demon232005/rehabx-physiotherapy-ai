"use client";

import { useCallback, useEffect, useState } from "react";
import type { ApiError, TokenResponse, UserOut } from "./types";

export const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "/api/v1";

const TOKEN_KEY = "rehabx_token";
const USER_KEY = "rehabx_user";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

function setSession(token: string, user: UserOut): void {
  window.localStorage.setItem(TOKEN_KEY, token);
  window.localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearSession(): void {
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(USER_KEY);
}

export async function api<T>(path: string, init: RequestInit = {}, withAuth = true): Promise<T> {
  const headers = new Headers(init.headers);
  if (withAuth) {
    const token = getToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);
  }
  if (init.body && typeof init.body === "string" && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const res = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!res.ok) {
    let detail: string | undefined;
    try {
      const body = (await res.json()) as ApiError;
      detail = Array.isArray(body.detail)
        ? body.detail.map((d) => d.msg).join("; ")
        : body.detail ?? `Request failed (${res.status})`;
    } catch {
      detail = `Request failed (${res.status})`;
    }
    const err = new Error(detail) as Error & { status?: number };
    err.status = res.status;
    throw err;
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export function useAuth() {
  const [user, setUser] = useState<UserOut | null>(() => {
    if (typeof window === "undefined") return null;
    const cached = window.localStorage.getItem(USER_KEY);
    if (!cached) return null;
    try {
      return JSON.parse(cached) as UserOut;
    } catch {
      return null;
    }
  });
  const [loading, setLoading] = useState<boolean>(() => {
    if (typeof window === "undefined") return true;
    return getToken() !== null;
  });

  useEffect(() => {
    const token = getToken();
    if (!token) return;

    api<UserOut>("/auth/me")
      .then((me) => {
        setUser(me);
        window.localStorage.setItem(USER_KEY, JSON.stringify(me));
      })
      .catch(() => {
        clearSession();
        setUser(null);
      })
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const res = await api<TokenResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }, false);
    const me = await api<UserOut>("/auth/me", {
      headers: { Authorization: `Bearer ${res.access_token}` },
    }, false);
    setSession(res.access_token, me);
    setUser(me);
    return me;
  }, []);

  const register = useCallback(async (email: string, password: string, fullName: string) => {
    await api<UserOut>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, full_name: fullName }),
    }, false);
    return login(email, password);
  }, [login]);

  const logout = useCallback(async () => {
    try {
      await api("/auth/logout", { method: "POST" });
    } catch {
      /* ignore network errors on logout */
    }
    clearSession();
    setUser(null);
  }, []);

  return { user, loading, login, register, logout };
}

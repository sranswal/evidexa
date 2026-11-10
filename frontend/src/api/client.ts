import type { ApiErrorResponse, TokenResponse } from "../types/api";

export class ApiClientError extends Error {
  code: string;
  status: number;
  details?: Record<string, unknown>;

  constructor(message: string, code = "UNKNOWN_ERROR", status = 500, details?: Record<string, unknown>) {
    super(message);
    this.name = "ApiClientError";
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

export const BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api/v1";

let inMemoryAccessToken: string | null = null;
let onUnauthorizedCallback: (() => void) | null = null;

export function setAccessToken(token: string | null): void {
  inMemoryAccessToken = token;
}

export function getAccessToken(): string | null {
  return inMemoryAccessToken;
}

export function setOnUnauthorized(cb: (() => void) | null): void {
  onUnauthorizedCallback = cb;
}

interface RequestOptions extends RequestInit {
  params?: Record<string, string | number | boolean | Array<string | number> | undefined | null>;
  skipAuth?: boolean;
}

export async function request<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  const { params, headers, skipAuth, ...restOptions } = options;

  let url = `${BASE_URL}${endpoint.startsWith("/") ? endpoint : `/${endpoint}`}`;

  if (params) {
    const searchParams = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null) {
        if (Array.isArray(value)) {
          for (const item of value) {
            if (item !== undefined && item !== null) {
              searchParams.append(key, String(item));
            }
          }
        } else {
          searchParams.append(key, String(value));
        }
      }
    }
    const queryString = searchParams.toString();
    if (queryString) {
      url += (url.includes("?") ? "&" : "?") + queryString;
    }
  }

  const defaultHeaders: Record<string, string> = {
    Accept: "application/json",
  };

  if (!(restOptions.body instanceof FormData)) {
    defaultHeaders["Content-Type"] = "application/json";
  }

  if (inMemoryAccessToken && !skipAuth) {
    defaultHeaders["Authorization"] = `Bearer ${inMemoryAccessToken}`;
  }

  const response = await fetch(url, {
    credentials: "include",
    ...restOptions,
    headers: {
      ...defaultHeaders,
      ...headers,
    },
  });

  if (response.status === 401 && !endpoint.includes("/auth/login") && !endpoint.includes("/auth/refresh")) {
    // Attempt token refresh via HttpOnly cookie
    try {
      const refreshRes = await fetch(`${BASE_URL}/auth/refresh`, {
        method: "POST",
        credentials: "include",
        headers: { Accept: "application/json", "Content-Type": "application/json" },
      });
      if (refreshRes.ok) {
        const refreshData = (await refreshRes.json()) as TokenResponse;
        setAccessToken(refreshData.access_token);
        // Retry original request once
        return request<T>(endpoint, {
          ...options,
          headers: {
            ...headers,
            Authorization: `Bearer ${refreshData.access_token}`,
          },
        });
      }
    } catch {
      // Refresh failed
    }

    setAccessToken(null);
    if (onUnauthorizedCallback) {
      onUnauthorizedCallback();
    }
  }

  if (!response.ok) {
    let errorCode = `HTTP_${response.status}`;
    let errorMessage = `Request failed with status ${response.status}: ${response.statusText}`;
    let errorDetails: Record<string, unknown> | undefined;

    try {
      const errorJson = (await response.json()) as ApiErrorResponse;
      if (errorJson.error) {
        errorCode = errorJson.error.code || errorCode;
        errorMessage = errorJson.error.message || errorMessage;
        errorDetails = errorJson.error.details;
      }
    } catch {
      // Body not JSON or empty
    }

    throw new ApiClientError(errorMessage, errorCode, response.status, errorDetails);
  }

  if (response.status === 204) {
    return {} as T;
  }

  return response.json() as Promise<T>;
}

export const api = {
  get: <T>(endpoint: string, params?: RequestOptions["params"]) =>
    request<T>(endpoint, { method: "GET", params }),
  post: <T>(endpoint: string, body?: unknown, params?: RequestOptions["params"]) =>
    request<T>(endpoint, {
      method: "POST",
      body: body instanceof FormData ? body : JSON.stringify(body),
      params,
    }),
  put: <T>(endpoint: string, body?: unknown) =>
    request<T>(endpoint, {
      method: "PUT",
      body: body instanceof FormData ? body : JSON.stringify(body),
    }),
  delete: <T>(endpoint: string) => request<T>(endpoint, { method: "DELETE" }),
};


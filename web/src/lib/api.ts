/**
 * API client (SPEC §6, _LEAN §7).
 *
 * - Relative `api/...` URLs only (works at the Studio domain root or under a path).
 * - The session token lives in localStorage with try/catch and an in-memory
 *   fallback (the Studio iframe can block storage), sent as X-Orvina-Token
 *   (the Studio gateway strips the standard Authorization header).
 * - Error JSON is mapped to the error code; the UI translates `errors.<code>`.
 * - A 401 (only when a token was sent) logs the user out.
 */
import type { Job } from "./types";

export class ApiError extends Error {
  code: string;
  status: number;

  constructor(code: string, status: number) {
    super(code);
    this.code = code;
    this.status = status;
  }
}

const TOKEN_KEY = "orvina-token";
let memoryToken: string | null = null;

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY) ?? memoryToken;
  } catch {
    return memoryToken;
  }
}

export function setToken(token: string | null): void {
  memoryToken = token;
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    // storage blocked: the in-memory fallback still works for this page load
  }
}

function url(path: string): string {
  return `api/${path.replace(/^\/+/, "")}`;
}

function authHeaders(): Record<string, string> {
  const token = getToken();
  // X-Orvina-Token, not Authorization: the Studio gateway strips the
  // standard Authorization header before it reaches the app (401 loop).
  // The server accepts both; see server/api/deps.py.
  return token ? { "X-Orvina-Token": token } : {};
}

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = { ...authHeaders() };
  if (typeof init.body === "string") headers["Content-Type"] = "application/json";
  let res: Response;
  try {
    res = await fetch(url(path), { ...init, headers });
  } catch {
    throw new ApiError("network_error", 0);
  }
  if (res.status === 401 && getToken()) {
    // A valid-looking token that the server rejected: the session is gone.
    setToken(null);
    if (!window.location.hash.startsWith("#/login")) window.location.hash = "#/login";
    throw new ApiError("unauthenticated", 401);
  }
  let body: unknown = null;
  if (res.status !== 204) {
    try {
      body = await res.json();
    } catch {
      body = null;
    }
  }
  if (!res.ok) {
    const code = (body as { error?: { code?: string } } | null)?.error?.code ?? "network_error";
    throw new ApiError(code, res.status);
  }
  return body as T;
}

export const api = {
  get: <T>(p: string) => request<T>(p),
  post: <T>(p: string, body?: unknown) =>
    request<T>(p, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) }),
  /** Form-data POST (the contract sends questions/answers as multipart/form-data). */
  postForm: <T>(p: string, form: Record<string, string>) => {
    const fd = new FormData();
    for (const [k, v] of Object.entries(form)) fd.append(k, v);
    return request<T>(p, { method: "POST", body: fd });
  },
  /**
   * Multipart POST with real upload byte progress (FEAT-02). Built on XHR so
   * `upload.onprogress` is available; resolves to the parsed JSON body.
   */
  postFormProgress: <T>(
    p: string,
    form: FormData,
    onUpload?: (loaded: number, total: number) => void,
  ) => new Promise<T>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", url(p));
    for (const [k, v] of Object.entries(authHeaders())) xhr.setRequestHeader(k, v);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onUpload) onUpload(e.loaded, e.total);
    };
    xhr.onload = () => {
      let body: unknown = null;
      try {
        body = xhr.responseText ? JSON.parse(xhr.responseText) : null;
      } catch {
        body = null;
      }
      if (xhr.status === 401 && getToken()) {
        setToken(null);
        if (!window.location.hash.startsWith("#/login")) window.location.hash = "#/login";
        reject(new ApiError("unauthenticated", 401));
        return;
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(body as T);
      } else {
        const code = (body as { error?: { code?: string } } | null)?.error?.code ?? "network_error";
        reject(new ApiError(code, xhr.status));
      }
    };
    xhr.onerror = () => reject(new ApiError("network_error", 0));
    xhr.send(form);
  }),
  patch: <T>(p: string, body?: unknown) =>
    request<T>(p, { method: "PATCH", body: JSON.stringify(body ?? {}) }),
  del: <T>(p: string) => request<T>(p, { method: "DELETE" }),
};

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** Poll GET api/jobs/{id} every 2 s until the job is done or failed. */
export async function watchJob(jobId: string, onProgress?: (job: Job) => void): Promise<Job> {
  for (;;) {
    const job = await api.get<Job>(`jobs/${jobId}`);
    onProgress?.(job);
    if (job.status === "done" || job.status === "error") return job;
    await sleep(2000);
  }
}

/** Download the .md export (the endpoint needs the Bearer header, so fetch a blob). */
export async function downloadDocumentMd(id: number, title: string): Promise<void> {
  const res = await fetch(url(`documents/${id}/export?format=md`), { headers: authHeaders() });
  if (!res.ok) throw new ApiError("network_error", res.status);
  const blob = await res.blob();
  const a = document.createElement("a");
  const href = URL.createObjectURL(blob);
  a.href = href;
  a.download = `${title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || "ringkasan"}.md`;
  a.click();
  URL.revokeObjectURL(href);
}

/** Download the .ics for an event (the endpoint needs the Bearer header, so fetch a blob). */
export async function downloadEventIcs(id: number, title: string): Promise<void> {
  const res = await fetch(url(`events/${id}.ics`), { headers: authHeaders() });
  if (!res.ok) throw new ApiError("network_error", res.status);
  const blob = await res.blob();
  const a = document.createElement("a");
  const href = URL.createObjectURL(blob);
  a.href = href;
  a.download = `${title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || `agenda-${id}`}.ics`;
  a.click();
  URL.revokeObjectURL(href);
}

/** Download the .md export of a project (the endpoint needs the Bearer header, so fetch a blob). */
export async function downloadProjectMd(id: number, title: string): Promise<void> {
  const res = await fetch(url(`projects/${id}/export?format=md`), { headers: authHeaders() });
  if (!res.ok) throw new ApiError("network_error", res.status);
  const blob = await res.blob();
  const a = document.createElement("a");
  const href = URL.createObjectURL(blob);
  a.href = href;
  a.download = `${title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || "proyek"}.md`;
  a.click();
  URL.revokeObjectURL(href);
}

export function qs(params: Record<string, string | number | undefined>): string {
  const parts = Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== "")
    .map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`);
  return parts.length ? `?${parts.join("&")}` : "";
}

/** The workbench backend: the browser's only server. */
import type { MergedGraph } from "./types";

export class ApiError extends Error {
  constructor(readonly status: number, readonly code: string, message: string, readonly body: unknown = null) {
    super(message);
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const r = await fetch(path, {
    method,
    credentials: "same-origin",
    headers: body === undefined ? {} : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) {
    const err = (data as { error?: { code?: string; message?: string } }).error ?? {};
    throw new ApiError(r.status, err.code ?? "error", err.message ?? r.statusText, data);
  }
  return data as T;
}

export const api = {
  me: () => request<{ signed_in: boolean; store: string }>("GET", "/api/me"),
  login: (password: string) => request<{ signed_in: boolean }>("POST", "/api/login", { password }),
  logout: () => request("POST", "/api/logout"),
  graph: () => request<MergedGraph>("GET", "/api/graph"),
  preview: () => request<SyncPreviewResponse>("POST", "/api/sync/preview"),
  apply: (previewId: string) => request<{ result: unknown }>("POST", "/api/sync/apply", { preview_id: previewId, confirm: true }),
  approve: (change: string) => request<{ change: string; approved_digest: string }>("POST", "/api/approve", { change }),
  session: () => request<SessionStatus>("GET", "/api/session"),
  startSession: (message: string) => request<SessionStatus>("POST", "/api/session", { message }),
  stopSession: () => request<SessionStatus>("DELETE", "/api/session"),
  command: (cmd: Record<string, unknown>) => request<unknown>("POST", "/api/session/commands", cmd),
  sessionConfig: () => request<SessionConfig>("GET", "/api/session/config"),
  setSessionConfig: (category: ConfigCategory, value: string) => request<SessionConfig>("PUT", "/api/session/config", { category, value }),
};

export interface SessionStatus {
  active: boolean;
  key?: string;
  acp_session_id?: string | null;
  model?: string | null;
  thought_level?: string | null;
  error?: string | null;
}

/** The ACP config option categories a person may choose. */
export type ConfigCategory = "model" | "thought_level";

/** One choosable session config option, as the agent reports it over ACP. */
export interface ConfigOption {
  id: string;
  category: ConfigCategory;
  name: string;
  currentValue: string | null;
  options: { value: string; name: string }[];
}

export interface SessionConfig {
  options: ConfigOption[];
  /** False while the session starts and its model is still being selected. */
  ready: boolean;
}

export interface SyncPreviewResponse {
  preview_id: string;
  can_apply: boolean;
  capabilities: string[];
  preview: {
    counts: { creates: number; updates: number; parents: number; relations_added: number; relations_removed: number; orphans: number };
    missing_capabilities: string[];
    skipped_drafts: string[];
    unplanned_changes?: string[];
  };
}

/** Subscribe to graph updates; the browser's EventSource reconnects by itself. */
export function subscribeGraph(onGraph: (g: MergedGraph) => void, onError?: () => void): () => void {
  const es = new EventSource("/api/events", { withCredentials: true });
  es.addEventListener("graph", (e) => onGraph(JSON.parse((e as MessageEvent).data)));
  if (onError) es.onerror = onError;
  return () => es.close();
}

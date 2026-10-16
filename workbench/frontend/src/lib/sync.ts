/** Sync and approval as the UI uses them; tests substitute a fake. */
import { projectApi, type SyncPreviewResponse } from "./api";

export interface SyncClient {
  preview(): Promise<SyncPreviewResponse>;
  apply(previewId: string): Promise<{ result: unknown }>;
  approve(change: string): Promise<unknown>;
}

/** Sync and approval of one project. */
export function httpSync(slug: string): SyncClient {
  const api = projectApi(slug);
  return { preview: () => api.preview(), apply: (id) => api.apply(id), approve: (change) => api.approve(change) };
}

/** The plan key an error points at, when the graph holds it. */
export function errorTarget(e: { change: string | null; deliverable: string | null; members: string[] }, has: (key: string) => boolean): string | null {
  const candidates = [
    e.change && e.deliverable ? `${e.change}/${e.deliverable}` : null,
    ...e.members,
    e.change,
  ].filter((k): k is string => !!k);
  return candidates.find(has) ?? null;
}

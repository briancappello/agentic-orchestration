<script lang="ts">
  import { ApiError, type SyncPreviewResponse } from "../lib/api";
  import type { SyncClient } from "../lib/sync";

  let { sync, onclose }: { sync: SyncClient; onclose: () => void } = $props();

  let phase = $state<"loading" | "preview" | "applying" | "done" | "error">("loading");
  let preview = $state<SyncPreviewResponse | null>(null);
  let message = $state("");
  let result = $state<Record<string, unknown> | null>(null);

  const counts = $derived(preview?.preview.counts);
  const writes = $derived(counts ? counts.creates + counts.updates + counts.parents + counts.relations_added + counts.relations_removed : 0);

  async function load() {
    phase = "loading";
    try {
      preview = await sync.preview();
      phase = "preview";
    } catch (err) {
      message = err instanceof ApiError ? err.message : "Sortie did not answer.";
      phase = "error";
    }
  }

  async function confirm() {
    if (!preview) return;
    phase = "applying";
    try {
      result = (await sync.apply(preview.preview_id)).result as Record<string, unknown>;
      phase = "done";
    } catch (err) {
      message = err instanceof ApiError ? err.message : "The sync failed.";
      const body = err instanceof ApiError ? (err.body as { error?: { result?: Record<string, unknown> } }) : null;
      result = body?.error?.result ?? null;
      phase = "error";
    }
  }

  const n = (v: unknown) => (Array.isArray(v) ? v.length : 0);
  load();
</script>

<div class="backdrop" role="presentation" onclick={(e) => e.target === e.currentTarget && phase !== "applying" && onclose()}>
  <div class="dialog" role="dialog" aria-modal="true" aria-labelledby="sync-title">
    <h2 id="sync-title">Sync the plan to the tracker</h2>

    {#if phase === "loading"}
      <p class="muted">Asking Sortie for a preview…</p>
    {:else if (phase === "preview" || phase === "applying") && preview && counts}
      <p class="muted">Nothing reaches the tracker until you apply. Only approved changes sync.</p>
      <dl class="counts">
        <div><dt>Issues to create</dt><dd data-count="creates">{counts.creates}</dd></div>
        <div><dt>Issues to update</dt><dd data-count="updates">{counts.updates}</dd></div>
        <div><dt>Parents to set</dt><dd data-count="parents">{counts.parents}</dd></div>
        <div><dt>Relations to add</dt><dd data-count="relations_added">{counts.relations_added}</dd></div>
        <div><dt>Relations to remove</dt><dd data-count="relations_removed">{counts.relations_removed}</dd></div>
        <div><dt>Orphaned issues</dt><dd data-count="orphans">{counts.orphans}</dd></div>
      </dl>
      {#if preview.preview.skipped_drafts.length}
        <p class="note">Skipped, breakdown still a draft: <span class="mono">{preview.preview.skipped_drafts.join(", ")}</span></p>
      {/if}
      {#if preview.preview.missing_capabilities.length}
        <p class="missing" role="alert">
          The tracker cannot do this sync. It lacks
          <b class="mono">{preview.preview.missing_capabilities.join(", ")}</b>.
        </p>
      {/if}
      <div class="actions">
        <button type="button" class="ghost" onclick={onclose} disabled={phase === "applying"}>Cancel</button>
        {#if preview.can_apply && writes > 0}
          <button type="button" class="primary" data-confirm onclick={confirm} disabled={phase === "applying"}>
            {phase === "applying" ? "Applying…" : `Apply ${writes} ${writes === 1 ? "write" : "writes"}`}
          </button>
        {:else if preview.can_apply}
          <span class="muted">The tracker already matches the plan.</span>
        {/if}
      </div>
    {:else if phase === "done"}
      <p>Synced: {n(result?.created)} created, {n(result?.updated)} updated, {n(result?.parents_set)} parents set, {n(result?.relations_added)} relations added, {n(result?.relations_removed)} removed.</p>
      <div class="actions"><button type="button" class="primary" onclick={onclose}>Done</button></div>
    {:else}
      <p class="missing" role="alert">{message}</p>
      {#if result}<p class="muted">Before it stopped: {n(result.created)} created, {n(result.relations_added)} relations added. Sync again to finish.</p>{/if}
      <div class="actions">
        <button type="button" class="ghost" onclick={onclose}>Close</button>
        <button type="button" class="primary" onclick={load}>New preview</button>
      </div>
    {/if}
  </div>
</div>

<style>
  .backdrop { position: fixed; inset: 0; z-index: 10; display: grid; place-items: center; padding: var(--s-gutter); background: rgba(20, 22, 26, 0.35); }
  .dialog { width: min(480px, 100%); display: flex; flex-direction: column; gap: var(--s-md); padding: var(--s-panel); border-radius: var(--r-well); background: #fff; box-shadow: 0 24px 60px -24px rgba(20, 22, 26, 0.5); }
  h2 { font-size: 20px; font-weight: 700; letter-spacing: -0.015em; }
  .muted { color: var(--mute); }
  .counts { display: grid; grid-template-columns: 1fr 1fr; gap: 8px 16px; }
  .counts div { display: flex; justify-content: space-between; align-items: baseline; padding: 6px 0; border-bottom: 1px solid var(--hair); }
  .counts dt { color: var(--mute); }
  .counts dd { font-size: 18px; font-weight: 700; font-variant-numeric: tabular-nums; }
  .note { font-size: 12px; color: var(--mute); }
  .mono { font: 500 12px var(--font-mono); }
  .missing { padding: 10px 12px; border: 1px solid var(--alert); border-radius: var(--r-button); color: var(--ink); }
  .actions { display: flex; justify-content: flex-end; align-items: center; gap: 8px; margin-top: 4px; }
  .primary, .ghost { height: 38px; padding: 0 16px; border-radius: var(--r-button); font-weight: 700; }
  .primary { background: var(--ink); color: #fff; }
  .primary:hover:not(:disabled) { background: #000; }
  .ghost { background: #fff; border: 1px solid var(--line); }
  button:disabled { opacity: 0.5; cursor: default; }
</style>

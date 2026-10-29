<script lang="ts">
  import type { SyncIssueRef, SyncStatus } from "../lib/types";

  let { status, onretry }: { status: SyncStatus | null | undefined; onretry: () => Promise<unknown> } = $props();

  let open = $state(false);
  let retrying = $state(false);

  const phase = $derived(status?.state ?? "idle");
  const clock = (t: number | null | undefined) =>
    t ? new Date(t * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "";
  const label = $derived(
    phase === "syncing" ? "Syncing…"
      : phase === "synced" ? `Synced ${clock(status?.synced_at)}`
      : phase === "failed" ? "Sync failed"
      : "Not synced yet",
  );

  const REASONS: Record<string, string> = {
    sortie_unreachable: "Sortie is unreachable.",
    plan_invalid: "The plan is invalid. It syncs once its problems are fixed.",
    tracker_unsupported_operation: "The tracker cannot do this sync.",
  };
  const reasonText = $derived(status?.reason ? (REASONS[status.reason.code] ?? "") : "");

  const LISTS: { key: "released" | "created" | "updated" | "orphans"; title: string }[] = [
    { key: "released", title: "Released to agents" },
    { key: "created", title: "Issues created" },
    { key: "updated", title: "Issues updated" },
    { key: "orphans", title: "Orphaned issues" },
  ];
  const name = (r: SyncIssueRef) => r.identifier || r.plan_key;

  async function retry() {
    retrying = true;
    try {
      await onretry();
    } finally {
      retrying = false;
    }
  }
</script>

<div class="sync-status">
  <button type="button" class="pill {phase}" data-sync={phase} aria-expanded={open} onclick={() => (open = !open)}
    title={phase === "failed" ? status?.reason?.message : "The approved plan syncs to the tracker on its own"}>
    <span class="dot" aria-hidden="true"></span>{label}
  </button>
  {#if open}
    <div class="panel" role="dialog" aria-label="Last sync" data-sync-result>
      {#if phase === "failed" && status?.reason}
        <p class="alert" role="alert">
          {#if reasonText}<b>{reasonText}</b>{/if}
          <span class="mono">{status.reason.message}</span>
        </p>
        {#if status.retry_at}<p class="muted">Retrying at {clock(status.retry_at)}, and at the next change.</p>{/if}
        <button type="button" class="retry" data-act="retry-sync" onclick={retry} disabled={retrying}>
          {retrying ? "Retrying…" : "Retry now"}
        </button>
      {:else if phase === "syncing"}
        <p class="muted">Syncing the approved plan to the tracker…</p>
      {/if}
      {#if status?.result}
        {#if status.result.failed}
          <p class="alert" data-sync-failed>Stopped at <span class="mono">{status.result.failed.op} {status.result.failed.plan_key}</span>: {status.result.failed.error}</p>
        {/if}
        {#each LISTS as l (l.key)}
          {@const items = status.result[l.key] ?? []}
          {#if items.length}
            <div class="list" data-sync-list={l.key}>
              <h3>{l.title} <span class="n">{items.length}</span></h3>
              <p class="mono">{items.map(name).join(", ")}</p>
            </div>
          {/if}
        {/each}
        {#if LISTS.every((l) => !(status?.result?.[l.key] ?? []).length) && !status.result.failed}
          <p class="muted">The tracker already matched the plan.</p>
        {/if}
      {:else if phase === "idle"}
        <p class="muted">The approved plan syncs to the tracker on its own, about a second after each change.</p>
      {/if}
    </div>
  {/if}
</div>

<style>
  .sync-status { position: relative; }
  .pill { display: inline-flex; align-items: center; gap: 8px; height: 32px; padding: 0 12px; border-radius: var(--r-pill);
    background: var(--ink-raised); border: 1px solid var(--ink-edge); color: #fff; font-size: 12.5px; font-weight: 600; white-space: nowrap; }
  .pill:hover { border-color: var(--ink-mute); }
  .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--slate); flex: none; }
  .synced .dot { background: #5fb48a; }
  .syncing .dot { background: var(--amber); animation: pulse 1s ease-in-out infinite; }
  .failed { border-color: var(--alert); }
  .failed .dot { background: var(--alert); }
  @keyframes pulse { 50% { opacity: 0.3; } }
  @media (prefers-reduced-motion: reduce) { .syncing .dot { animation: none; } }
  .panel { position: absolute; right: 0; top: calc(100% + 8px); z-index: 20; width: min(380px, 90vw); display: flex; flex-direction: column;
    gap: var(--s-sm); padding: var(--s-md) var(--s-card-x); border-radius: var(--r-well); background: #fff; color: var(--ink);
    box-shadow: 0 24px 60px -24px rgba(20, 22, 26, 0.5); border: 1px solid var(--line); }
  h3 { font-size: 12px; font-weight: 700; color: var(--mute); }
  .n { font-variant-numeric: tabular-nums; color: var(--ink); }
  .mono { font: 500 12px var(--font-mono); overflow-wrap: anywhere; }
  .muted { color: var(--mute); font-size: 12.5px; }
  .alert { display: flex; flex-direction: column; gap: 4px; padding: 8px 10px; border: 1px solid var(--alert); border-radius: var(--r-button); font-size: 12.5px; }
  .retry { align-self: flex-start; height: 32px; padding: 0 14px; border-radius: var(--r-button); background: var(--ink); color: #fff; font-weight: 700; }
  .retry:disabled { opacity: 0.5; cursor: default; }
</style>

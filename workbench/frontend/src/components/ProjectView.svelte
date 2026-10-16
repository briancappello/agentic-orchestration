<script lang="ts">
  import { onDestroy } from "svelte";
  import { api, projectApi, subscribeGraph } from "../lib/api";
  import { httpSession } from "../lib/session";
  import { httpSync } from "../lib/sync";
  import { emptyGraph, type MergedGraph, type TrackerProject, type ViewState } from "../lib/types";
  import ChatPane from "./ChatPane.svelte";
  import GraphPane from "./GraphPane.svelte";
  import Shell from "./Shell.svelte";
  import SyncDialog from "./SyncDialog.svelte";

  let { slug, view = $bindable(), onmissing }: { slug: string; view: ViewState; onmissing: () => void } = $props();

  let doc: MergedGraph = $state(emptyGraph());
  let name = $state("");
  let tracker: TrackerProject | null = $state(null);
  let syncing = $state(false);
  // svelte-ignore state_referenced_locally
  const session = httpSession(slug);
  // svelte-ignore state_referenced_locally
  const sync = httpSync(slug);
  let unsubscribe: (() => void) | null = null;

  /** Select a node from outside the graph, moving to the level that shows it. */
  function selectAnywhere(key: string | null) {
    const n = key ? doc.nodes.find((x) => x.plan_key === key) : undefined;
    if (n) view.epic = n.kind === "story" ? (doc.parents.find((p) => p.child === key)?.parent ?? n.change) : null;
    view.selected = key;
  }

  async function start() {
    try {
      const detail = await api.project(slug);
      name = detail.project.name;
      tracker = detail.tracker;
      doc = await projectApi(slug).graph();
      unsubscribe = subscribeGraph(slug, (g) => (doc = g));
    } catch {
      onmissing();
    }
  }
  start();
  onDestroy(() => unsubscribe?.());
</script>

<svelte:head><title>{name ? `${name} · Plan workbench` : "Plan workbench"}</title></svelte:head>

<Shell>
  {#snippet graph()}
    <GraphPane
      {doc}
      {view}
      projectName={name}
      onselect={(k) => (view.selected = k)}
      onopen={(k) => { view.epic = k; view.selected = null; }}
      onback={() => { view.selected = view.epic; view.epic = null; }}
      ontogglecross={(b) => (view.showCross = b)}
    >
      {#snippet notice()}
        {#if tracker && tracker.exists && !tracker.ready}
          <div class="tracker-warn" role="status">
            <p><b>Huly project {tracker.key} cannot take plan writes yet.</b> Fix this in Huly, then sync:</p>
            <ul>{#each tracker.problems as p (p)}<li>{p}</li>{/each}</ul>
          </div>
        {/if}
      {/snippet}
      {#snippet actions()}
        <button type="button" class="sync" onclick={() => (syncing = true)} disabled={!doc.validation.valid || !doc.sortie.reachable}
          title={!doc.validation.valid ? "Fix the plan's problems first" : !doc.sortie.reachable ? "Sortie is unreachable" : "Preview a sync to the tracker"}>
          Sync…
        </button>
      {/snippet}
    </GraphPane>
  {/snippet}
  {#snippet chat()}
    <ChatPane {doc} {view} {session} onselect={(k) => selectAnywhere(k)} onapprove={(c) => sync.approve(c)} />
  {/snippet}
</Shell>
{#if syncing}<SyncDialog {sync} onclose={() => (syncing = false)} />{/if}

<style>
  .sync { height: 32px; padding: 0 14px; border-radius: var(--r-button); background: #fff; color: var(--ink); font-weight: 700; }
  .sync:hover:not(:disabled) { background: var(--strip); }
  .sync:disabled { opacity: 0.4; cursor: default; }
  .tracker-warn { flex: none; padding: 10px var(--s-gutter); border-bottom: 1px solid #ecd9a8; background: var(--amber-tint); color: var(--amber-ink); font-size: 12.5px; }
  .tracker-warn b { color: var(--ink); font-weight: 600; }
  .tracker-warn ul { margin: 4px 0 0 18px; }
</style>

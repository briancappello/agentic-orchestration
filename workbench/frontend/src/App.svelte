<script lang="ts">
  import { onDestroy } from "svelte";
  import ChatPane from "./components/ChatPane.svelte";
  import GraphPane from "./components/GraphPane.svelte";
  import Login from "./components/Login.svelte";
  import Shell from "./components/Shell.svelte";
  import SyncDialog from "./components/SyncDialog.svelte";
  import { api, subscribeGraph } from "./lib/api";
  import { httpSession } from "./lib/session";
  import { httpSync } from "./lib/sync";
  import { emptyGraph, type MergedGraph, type ViewState } from "./lib/types";

  let signedIn: boolean | null = $state(null);
  let doc: MergedGraph = $state(emptyGraph());
  let view: ViewState = $state(readHash());
  let unsubscribe: (() => void) | null = null;
  let syncing = $state(false);

  function readHash(): ViewState {
    const p = new URLSearchParams(location.hash.slice(1));
    return { epic: p.get("epic"), selected: p.get("sel"), showCross: p.get("cross") !== "0" };
  }

  $effect(() => {
    const p = new URLSearchParams();
    if (view.epic) p.set("epic", view.epic);
    if (view.selected) p.set("sel", view.selected);
    if (!view.showCross) p.set("cross", "0");
    const next = p.toString();
    if (location.hash.slice(1) !== next) history.replaceState(null, "", next ? `#${next}` : location.pathname);
  });

  /** Select a node from outside the graph, moving to the level that shows it. */
  function selectAnywhere(key: string | null) {
    const n = key ? doc.nodes.find((x) => x.plan_key === key) : undefined;
    if (n) view.epic = n.kind === "story" ? (doc.parents.find((p) => p.child === key)?.parent ?? n.change) : null;
    view.selected = key;
  }

  async function start() {
    try {
      await api.me();
      signedIn = true;
      doc = await api.graph();
      unsubscribe = subscribeGraph((g) => (doc = g));
    } catch {
      signedIn = false;
    }
  }
  start();
  onDestroy(() => unsubscribe?.());
</script>

{#if signedIn === false}
  <Login onsignedin={start} />
{:else if signedIn}
  <Shell>
    {#snippet graph()}
      <GraphPane
        {doc}
        {view}
        onselect={(k) => (view.selected = k)}
        onopen={(k) => { view.epic = k; view.selected = null; }}
        onback={() => { view.selected = view.epic; view.epic = null; }}
        ontogglecross={(b) => (view.showCross = b)}
      >
        {#snippet actions()}
          <button type="button" class="sync" onclick={() => (syncing = true)} disabled={!doc.validation.valid || !doc.sortie.reachable}
            title={!doc.validation.valid ? "Fix the plan's problems first" : !doc.sortie.reachable ? "Sortie is unreachable" : "Preview a sync to the tracker"}>
            Sync…
          </button>
        {/snippet}
      </GraphPane>
    {/snippet}
    {#snippet chat()}
      <ChatPane {doc} {view} session={httpSession} onselect={(k) => selectAnywhere(k)} onapprove={(c) => httpSync.approve(c)} />
    {/snippet}
  </Shell>
  {#if syncing}<SyncDialog sync={httpSync} onclose={() => (syncing = false)} />{/if}
{/if}

<style>
  .sync { height: 32px; padding: 0 14px; border-radius: var(--r-button); background: #fff; color: var(--ink); font-weight: 700; }
  .sync:hover:not(:disabled) { background: var(--strip); }
  .sync:disabled { opacity: 0.4; cursor: default; }
</style>

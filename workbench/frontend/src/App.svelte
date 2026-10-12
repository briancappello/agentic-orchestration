<script lang="ts">
  import { onDestroy } from "svelte";
  import GraphPane from "./components/GraphPane.svelte";
  import Login from "./components/Login.svelte";
  import Shell from "./components/Shell.svelte";
  import { api, subscribeGraph } from "./lib/api";
  import { emptyGraph, type MergedGraph, type ViewState } from "./lib/types";

  let signedIn: boolean | null = $state(null);
  let doc: MergedGraph = $state(emptyGraph());
  let view: ViewState = $state(readHash());
  let unsubscribe: (() => void) | null = null;

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
      />
    {/snippet}
    {#snippet chat()}<p class="placeholder">Planning chat</p>{/snippet}
  </Shell>
{/if}

<style>
  .placeholder { padding: var(--s-panel); color: var(--mute); }
</style>

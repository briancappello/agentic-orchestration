<script lang="ts">
  import GraphPane from "../src/components/GraphPane.svelte";
  import type { MergedGraph, ViewState } from "../src/lib/types";

  let { initial, initialView = undefined }: { initial: MergedGraph; initialView?: ViewState } = $props();
  // svelte-ignore state_referenced_locally
  let doc = $state(initial);
  // svelte-ignore state_referenced_locally
  let view: ViewState = $state(initialView ?? { epic: null, selected: null, showCross: true });

  export function setDoc(next: MergedGraph) { doc = next; }
  export function getView() { return view; }
</script>

<div style="display:flex;flex-direction:column;height:600px">
  <GraphPane
    {doc}
    {view}
    onselect={(k) => (view.selected = k)}
    onopen={(k) => { view.epic = k; view.selected = null; }}
    onback={() => { view.selected = view.epic; view.epic = null; }}
    ontogglecross={(b) => (view.showCross = b)}
    onunmark={() => (view.mark = null)}
    tabs={[{ label: "Home", href: "#/p/x", current: false }, { label: "Graph", href: "#/p/x/graph", current: true }]}
  />
</div>

<script lang="ts">
  import ChatPane from "../src/components/ChatPane.svelte";
  import type { SessionClient } from "../src/lib/session";
  import type { MergedGraph, ViewState } from "../src/lib/types";

  let { initial, session }: { initial: MergedGraph; session: SessionClient } = $props();
  // svelte-ignore state_referenced_locally
  let doc = $state(initial);
  let view: ViewState = $state({ epic: null, selected: null, showCross: true });

  export function select(key: string | null) { view.selected = key; }
  export function setEpic(key: string | null) { view.epic = key; }
</script>

<div style="display:flex;flex-direction:column;height:800px">
  <ChatPane {doc} {view} {session} onselect={(k) => (view.selected = k)} />
</div>

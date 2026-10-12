<script lang="ts">
  import ChatPane from "../src/components/ChatPane.svelte";
  import type { SessionClient } from "../src/lib/session";
  import type { MergedGraph, ViewState } from "../src/lib/types";

  let { initial, session, onapprove = undefined }: { initial: MergedGraph; session: SessionClient; onapprove?: (c: string) => Promise<unknown> } = $props();
  // svelte-ignore state_referenced_locally
  let doc = $state(initial);
  let view: ViewState = $state({ epic: null, selected: null, showCross: true });

  export function select(key: string | null) { view.selected = key; }
  export function setEpic(key: string | null) { view.epic = key; }
</script>

<div style="display:flex;flex-direction:column;height:800px">
  <ChatPane {doc} {view} {session} {onapprove} onselect={(k) => (view.selected = k)} />
</div>

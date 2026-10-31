<script lang="ts">
  import ChatPane from "../src/components/ChatPane.svelte";
  import type { SessionClient } from "../src/lib/session";
  import type { StoryActions } from "../src/lib/sync";
  import type { GraphNode } from "../src/lib/types";
  import type { WorkerClient } from "../src/lib/worker";
  import type { SpecReader } from "../src/lib/spec";
  import type { MergedGraph, ViewState } from "../src/lib/types";

  let { initial, session, actions = undefined, workerClient = undefined, onwatch = undefined, specs = undefined, initialView = undefined }: {
    initial: MergedGraph; session: SessionClient; actions?: StoryActions; specs?: SpecReader;
    workerClient?: WorkerClient; onwatch?: (n: GraphNode) => void;
    /** Where the graph opened, as a deep link sets it. */
    initialView?: ViewState;
  } = $props();
  let watching: GraphNode | null = $state(null);
  export function watch(n: GraphNode | null) { watching = n; }
  // svelte-ignore state_referenced_locally
  let doc = $state(initial);
  // svelte-ignore state_referenced_locally
  let view: ViewState = $state(initialView ?? { epic: null, selected: null, showCross: true });

  export function select(key: string | null) { view.selected = key; }
  export function setEpic(key: string | null) { view.epic = key; }
</script>

<div style="display:flex;flex-direction:column;height:800px">
  <ChatPane {doc} {view} {session} {actions} {specs}
    worker={watching && workerClient ? { node: watching, client: workerClient } : null}
    onwatch={(n) => { onwatch?.(n); }} onunwatch={() => (watching = null)} onselect={(k) => (view.selected = k)} />
</div>

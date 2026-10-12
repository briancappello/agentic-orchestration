<script lang="ts">
  import type { Snippet } from "svelte";
  import { paneLayout } from "../lib/panes";

  let { graph, chat, width = undefined }: { graph: Snippet; chat: Snippet; width?: number } = $props();

  let innerWidth = $state(typeof window === "undefined" ? 1440 : window.innerWidth);
  const layout = $derived(paneLayout(width ?? innerWidth));
</script>

<svelte:window bind:innerWidth />

<div class="shell" class:stacked={layout.mode === "stacked"} data-mode={layout.mode}>
  <section
    class="pane graph-pane"
    aria-label="Plan graph"
    style:width={layout.mode === "split" ? `${layout.graph}px` : null}
  >
    {@render graph()}
  </section>
  <section
    class="pane chat-pane"
    aria-label="Planning chat"
    style:width={layout.mode === "split" ? `${layout.chat}px` : null}
  >
    {@render chat()}
  </section>
</div>

<style>
  .shell { display: flex; height: 100%; min-height: 0; }
  .pane { min-width: 0; min-height: 0; display: flex; flex-direction: column; }
  .graph-pane { flex: none; }
  .chat-pane { flex: none; border-left: 1px solid var(--line); background: var(--panel); }
  .shell.stacked { flex-direction: column; height: auto; }
  .shell.stacked .pane { width: 100%; }
  .shell.stacked .graph-pane { height: 62vh; }
  .shell.stacked .chat-pane { border-left: 0; border-top: 1px solid var(--line); min-height: 70vh; }
</style>

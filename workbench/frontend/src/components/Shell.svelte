<script lang="ts">
  import type { Snippet } from "svelte";
  import { clampGraph, DEFAULT_GRAPH_SHARE, loadGraphShare, paneLayout, saveGraphShare } from "../lib/panes";

  let { graph, chat, width = undefined }: { graph: Snippet; chat: Snippet; width?: number } = $props();

  let innerWidth = $state(typeof window === "undefined" ? 1440 : window.innerWidth);
  let share = $state(loadGraphShare());
  let dragging = $state(false);
  const viewport = $derived(width ?? innerWidth);
  const layout = $derived(paneLayout(viewport, share));
  const STEP = 24;

  function setGraph(px: number) {
    share = clampGraph(viewport, px) / viewport;
  }

  function onpointerdown(e: PointerEvent) {
    if (e.button !== 0) return;
    e.preventDefault();
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
    dragging = true;
  }

  function onpointermove(e: PointerEvent) {
    if (dragging) setGraph(e.clientX);
  }

  function onpointerup() {
    if (!dragging) return;
    dragging = false;
    saveGraphShare(share);
  }

  function onkeydown(e: KeyboardEvent) {
    if (layout.mode !== "split") return;
    const moves: Record<string, number> = { ArrowLeft: -STEP, ArrowRight: STEP, Home: -viewport, End: viewport };
    if (!(e.key in moves)) return;
    e.preventDefault();
    setGraph(layout.graph + moves[e.key]);
    saveGraphShare(share);
  }

  function reset() {
    share = DEFAULT_GRAPH_SHARE;
    saveGraphShare(share);
  }
</script>

<svelte:window bind:innerWidth />

<div class="shell" class:stacked={layout.mode === "stacked"} class:dragging data-mode={layout.mode}>
  <section
    class="pane graph-pane"
    aria-label="Plan graph"
    style:width={layout.mode === "split" ? `${layout.graph}px` : null}
  >
    {@render graph()}
  </section>
  {#if layout.mode === "split"}
    <!-- A focusable separator is the ARIA window-splitter widget. -->
    <!-- svelte-ignore a11y_no_noninteractive_tabindex, a11y_no_noninteractive_element_interactions -->
    <div
      class="divider"
      role="separator"
      tabindex="0"
      aria-orientation="vertical"
      aria-label="Resize the graph and the chat"
      aria-valuemin={Math.round((100 * clampGraph(viewport, 0)) / viewport)}
      aria-valuemax={Math.round((100 * clampGraph(viewport, viewport)) / viewport)}
      aria-valuenow={Math.round((100 * layout.graph) / viewport)}
      title="Drag to resize · double-click to reset"
      style:left={`${layout.graph}px`}
      {onpointerdown}
      {onpointermove}
      {onpointerup}
      onpointercancel={onpointerup}
      ondblclick={reset}
      {onkeydown}
    ></div>
  {/if}
  <section
    class="pane chat-pane"
    aria-label="Planning chat"
    style:width={layout.mode === "split" ? `${layout.chat}px` : null}
  >
    {@render chat()}
  </section>
</div>

<style>
  .shell { position: relative; display: flex; height: 100%; min-height: 0; }
  .shell.dragging { cursor: col-resize; user-select: none; }
  .shell.dragging .pane { pointer-events: none; }
  .pane { min-width: 0; min-height: 0; display: flex; flex-direction: column; }
  .graph-pane { flex: none; }
  .chat-pane { flex: none; border-left: 1px solid var(--line); background: var(--panel); }
  /* A 9px hit area centred on the chat pane's 1px border; the border itself stays the visible rule. */
  .divider { position: absolute; top: 0; bottom: 0; width: 9px; margin-left: -4px; z-index: 5; cursor: col-resize; touch-action: none; }
  .divider::after { content: ""; position: absolute; top: 0; bottom: 0; left: 4px; width: 1px; background: transparent; transition: background 0.15s ease-out, box-shadow 0.15s ease-out; }
  .divider:hover::after, .shell.dragging .divider::after { background: var(--ink); box-shadow: 0 0 0 1px var(--ink); }
  .divider:focus-visible { outline: none; }
  .divider:focus-visible::after { background: var(--amber); box-shadow: 0 0 0 1px var(--amber); }
  @media (prefers-reduced-motion: reduce) { .divider::after { transition: none; } }
  .shell.stacked { flex-direction: column; height: auto; }
  .shell.stacked .pane { width: 100%; }
  .shell.stacked .graph-pane { height: 62vh; }
  .shell.stacked .chat-pane { border-left: 0; border-top: 1px solid var(--line); min-height: 70vh; }
</style>

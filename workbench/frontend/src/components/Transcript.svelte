<script lang="ts">
  import { renderMarkdown } from "../lib/markdown";
  import { workSummary, type ChatBlock } from "../lib/chat";
  import Icon from "./Icon.svelte";

  /** A session's conversation: the agent's messages and work, people's
   * messages, and permission requests, which only ``onpermit`` answers. */
  let {
    items, empty = "", onpermit, el = $bindable(),
  }: {
    items: ChatBlock[];
    empty?: string;
    onpermit?: (id: string, option: string) => void;
    el?: HTMLElement;
  } = $props();
</script>

<div class="log" bind:this={el} aria-live="polite" aria-label="Conversation">
  {#if !items.length}<p class="empty">{empty}</p>{/if}
  {#each items as item (item.key)}
    {#if item.kind === "user"}
      <div class="msg user">{#if item.by}<span class="by">{item.by}</span>{/if}{item.text}</div>
    {:else if item.kind === "agent"}
      <div class="msg agent md">{@html renderMarkdown(item.text)}</div>
    {:else if item.kind === "work"}
      <details class="work" class:live={item.live}>
        <summary><Icon name="chevron" size={12} /><span>{workSummary(item.steps, item.live)}</span></summary>
        <div class="steps">
          {#each item.steps as step (step.key)}
            {#if step.kind === "tool"}
              <div class="tool" data-status={step.status}><span class="dot"></span><span class="title">{step.title}</span><em>{step.status}</em></div>
            {:else}
              <div class="msg step {step.kind} md">{@html renderMarkdown(step.text)}</div>
            {/if}
          {/each}
        </div>
      </details>
    {:else if item.kind === "permission"}
      <div class="permission" data-permission={item.id}>
        <b>Permission</b>
        <p>{item.title}</p>
        {#if item.resolved}
          <p class="resolved">{item.resolved}</p>
        {:else if onpermit}
          <div class="options">
            {#each item.options as o (o.optionId)}
              <button type="button" class={o.kind.startsWith("allow") ? "primary" : "ghost"} onclick={() => onpermit(item.id, o.optionId)}>{o.name}</button>
            {/each}
          </div>
        {/if}
      </div>
    {:else}
      <div class="notice">{item.text}</div>
    {/if}
  {/each}
</div>

<style>
  .primary, .ghost { height: 42px; padding: 0 16px; border-radius: var(--r-button); font-weight: 700; font-size: 13px; }
  .primary { background: var(--ink); color: #fff; }
  .primary:hover:not(:disabled) { background: #000; }
  .primary:disabled { opacity: 0.45; cursor: default; }
  .ghost { background: #fff; border: 1px solid var(--line); }
  .ghost:hover { border-color: var(--ink); }
  .log { flex: 1; min-height: 120px; overflow-y: auto; padding: var(--s-gutter) var(--s-panel); display: flex; flex-direction: column; gap: 10px; }
  .empty { color: var(--mute); max-width: 46ch; }
  .msg { white-space: pre-wrap; word-break: break-word; line-height: 1.5; max-width: 92%; }
  .msg.user { align-self: flex-end; padding: 8px 12px; border-radius: 12px 12px 4px 12px; background: var(--strip); }
  .msg.agent { align-self: flex-start; }
  .work { align-self: stretch; color: var(--mute); }
  .work summary { display: inline-flex; align-items: center; gap: 6px; min-height: 28px; font-size: 12px; font-weight: 600; cursor: pointer; list-style: none; border-radius: var(--r-button); }
  .work summary::-webkit-details-marker { display: none; }
  .work summary:hover { color: var(--ink); }
  .work summary span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 52ch; }
  .work summary :global(.ico) { transition: transform 160ms cubic-bezier(0.16, 1, 0.3, 1); }
  .work[open] summary :global(.ico) { transform: rotate(90deg); }
  .work.live summary span { color: var(--amber-ink); }
  .steps { display: flex; flex-direction: column; gap: 8px; margin: 6px 0 2px 5px; padding-left: 13px; border-left: 1px solid var(--hair); }
  .msg.step { max-width: none; font-size: 12px; }
  .msg.thought { font-style: italic; }
  .msg.md { white-space: normal; }
  .md :global(:is(p, ul, ol, pre, blockquote, table, h1, h2, h3, h4)) { margin: 0 0 8px; }
  .md :global(:is(p, ul, ol, pre, blockquote, table, h1, h2, h3, h4):last-child) { margin-bottom: 0; }
  .md :global(:is(h1, h2, h3, h4)) { font-size: 14px; font-weight: 700; line-height: 1.3; margin-top: 14px; }
  .md :global(:is(h1, h2, h3, h4):first-child) { margin-top: 0; }
  .md :global(:is(ul, ol)) { padding-left: 20px; }
  .md :global(li + li) { margin-top: 2px; }
  .md :global(code) { font: 500 12px var(--font-mono); padding: 1px 4px; border-radius: var(--r-tag); background: var(--strip); }
  .md :global(pre) { padding: 10px 12px; border-radius: var(--r-card); background: var(--strip); overflow-x: auto; white-space: pre; }
  .md :global(pre code) { padding: 0; background: none; }
  .md :global(blockquote) { padding-left: 10px; border-left: 1px solid var(--line); color: var(--mute); }
  .md :global(a) { color: var(--ink); text-decoration: underline; text-underline-offset: 2px; text-decoration-color: var(--line); }
  .md :global(.table-scroll) { max-width: 100%; overflow-x: auto; margin: 0 0 8px; scrollbar-color: #b9bab3 var(--hair); }
  .md :global(.table-scroll:last-child) { margin-bottom: 0; }
  .md :global(table) { border-collapse: collapse; font-size: 12.5px; margin: 0; }
  .md :global(:is(th, td)) { min-width: 7em; word-break: normal; overflow-wrap: normal; padding: 4px 8px; border: 1px solid var(--line); text-align: left; vertical-align: top; }
  .md :global(th) { background: var(--strip); font-weight: 600; }
  .md :global(hr) { border: 0; border-top: 1px solid var(--line); margin: 10px 0; }
  .tool { display: flex; align-items: center; gap: 8px; font: 500 11.5px var(--font-mono); color: var(--mute); }
  .tool .title { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .tool .dot { width: 6px; height: 6px; border-radius: 50%; background: var(--slate); }
  .tool[data-status="completed"] .dot { background: var(--done); }
  .tool[data-status="in_progress"] .dot, .tool[data-status="pending"] .dot { background: var(--amber); }
  .tool[data-status="failed"] .dot { background: var(--alert); }
  .tool em { margin-left: auto; font-style: normal; }
  .permission { padding: 12px 14px; border: 1px solid var(--amber); border-radius: var(--r-well); background: var(--amber-tint); display: flex; flex-direction: column; gap: 6px; }
  .permission b { font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase; color: var(--amber-ink); }
  .permission p { font: 500 12px/1.5 var(--font-mono); }
  .permission .resolved { color: var(--mute); font-family: var(--font-sans); }
  .options { display: flex; gap: 8px; flex-wrap: wrap; }
  .notice { font-size: 12px; color: var(--mute); }
  .by { display: block; font-size: 11px; font-weight: 700; color: var(--mute); margin-bottom: 2px; }
</style>

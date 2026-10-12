<script lang="ts">
  import { onDestroy, tick } from "svelte";
  import { applyEvent, composeMessage, emptyTranscript, withUserMessages, type ChatItem, type Transcript } from "../lib/chat";
  import { GraphModel } from "../lib/model";
  import type { SessionClient } from "../lib/session";
  import type { MergedGraph, ViewState } from "../lib/types";
  import ContextCard from "./ContextCard.svelte";
  import Icon from "./Icon.svelte";

  let {
    doc, view, session, onselect, onapprove,
  }: {
    doc: MergedGraph;
    view: ViewState;
    session: SessionClient;
    onselect: (key: string | null) => void;
    onapprove?: (change: string) => Promise<unknown>;
  } = $props();

  const model = $derived(new GraphModel(doc));
  let active = $state(false);
  let starting = $state(false);
  let error = $state("");
  let transcript: Transcript = $state(emptyTranscript());
  let messages: { time: number; text: string }[] = $state([]);
  let draft = $state("");
  let attached: string[] = $state([]);
  let log: HTMLElement | undefined = $state();
  let unsubscribe: (() => void) | null = null;

  const items: ChatItem[] = $derived(withUserMessages(transcript.items, messages));
  const attachedNodes = $derived(attached.map((k) => model.node(k)).filter((n) => n !== undefined));

  // A newly selected node is offered to the chat as context.
  let lastSelected: string | null = null;
  $effect(() => {
    const sel = view.selected;
    if (sel && sel !== lastSelected && !attached.includes(sel)) attached = [...attached, sel];
    lastSelected = sel;
  });

  async function refresh() {
    try {
      const status = await session.status();
      active = status.active;
      messages = status.messages ?? [];
      error = status.error ?? "";
      if (active && !unsubscribe) connect();
    } catch {
      error = "The planning session is unavailable.";
    }
  }

  function connect() {
    transcript = emptyTranscript();
    unsubscribe = session.subscribe(
      async (ev) => {
        transcript = applyEvent(transcript, ev);
        await tick();
        if (log) log.scrollTop = log.scrollHeight;
      },
      () => {
        unsubscribe = null;
        active = false;
      },
    );
  }

  async function start() {
    starting = true;
    error = "";
    try {
      await session.start();
      await refresh();
    } catch (err) {
      error = err instanceof Error ? err.message : "Could not start the session.";
    } finally {
      starting = false;
    }
  }

  async function stop() {
    unsubscribe?.();
    unsubscribe = null;
    await session.stop();
    active = false;
  }

  async function send(e?: Event) {
    e?.preventDefault();
    const text = draft.trim();
    if (!text || !active) return;
    const message = composeMessage(text, attachedNodes);
    draft = "";
    try {
      await session.command({ op: "steer", text: message });
      messages = [...messages, { time: Date.now() / 1000, text: message }];
      attached = [];
    } catch (err) {
      draft = text;
      error = err instanceof Error ? err.message : "The message was not sent.";
    }
  }

  async function permit(id: string, option: string) {
    try {
      await session.command({ op: "permit", id, option });
    } catch (err) {
      error = err instanceof Error ? err.message : "The answer was not sent.";
    }
  }

  function onkey(e: KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) send(e);
  }

  refresh();
  onDestroy(() => unsubscribe?.());
</script>

<ContextCard {model} {view} {attached} {onapprove} onattach={(k) => (attached = [...attached, k])} onselect={(k) => onselect(k)} />

<div class="session-bar">
  <span class="state" class:on={active}><i></i>{active ? (transcript.busy ? "Agent working" : "Planning session") : "No session"}</span>
  {#if active}
    <button type="button" class="ghost" onclick={stop}>End session</button>
  {:else}
    <button type="button" class="primary" onclick={start} disabled={starting}>{starting ? "Starting…" : "Start planning session"}</button>
  {/if}
</div>

<div class="log" bind:this={log} aria-live="polite" aria-label="Conversation">
  {#if !items.length}
    <p class="empty">{active ? "The agent is reading the store. Ask it to plan a change, or select a node and point at it." : "Start a session to plan with the agent. It works in the spec store and writes only under openspec/."}</p>
  {/if}
  {#each items as item (item.key)}
    {#if item.kind === "user"}
      <div class="msg user">{item.text}</div>
    {:else if item.kind === "agent"}
      <div class="msg agent">{item.text}</div>
    {:else if item.kind === "thought"}
      <div class="msg thought">{item.text}</div>
    {:else if item.kind === "tool"}
      <div class="tool" data-status={item.status}><span class="dot"></span>{item.title}<em>{item.status}</em></div>
    {:else if item.kind === "permission"}
      <div class="permission" data-permission={item.id}>
        <b>Permission</b>
        <p>{item.title}</p>
        {#if item.resolved}
          <p class="resolved">{item.resolved}</p>
        {:else}
          <div class="options">
            {#each item.options as o (o.optionId)}
              <button type="button" class={o.kind.startsWith("allow") ? "primary" : "ghost"} onclick={() => permit(item.id, o.optionId)}>{o.name}</button>
            {/each}
          </div>
        {/if}
      </div>
    {:else}
      <div class="notice">{item.text}</div>
    {/if}
  {/each}
</div>

{#if error}<p class="error" role="alert">{error}</p>{/if}

<form class="composer" onsubmit={send}>
  {#if attachedNodes.length}
    <div class="attached" aria-label="Attached to the next message">
      {#each attachedNodes as n (n.plan_key)}
        <span class="att" data-attached={n.plan_key}>{n.plan_key}<button type="button" aria-label="Remove {n.plan_key}" onclick={() => (attached = attached.filter((k) => k !== n.plan_key))}><Icon name="close" size={12} /></button></span>
      {/each}
    </div>
  {/if}
  <textarea bind:value={draft} onkeydown={onkey} rows="3" placeholder={active ? "Message the planning agent" : "Start a session first"} disabled={!active} aria-label="Message"></textarea>
  <button type="submit" class="primary" disabled={!active || !draft.trim()}>Send</button>
</form>

<style>
  .session-bar { flex: none; display: flex; align-items: center; justify-content: space-between; gap: var(--s-md); padding: 10px var(--s-panel); border-bottom: 1px solid var(--hair); }
  .state { display: flex; align-items: center; gap: 8px; font-size: 12px; font-weight: 600; color: var(--mute); }
  .state i { width: 8px; height: 8px; border-radius: 50%; background: var(--slate); }
  .state.on { color: var(--ink); }
  .state.on i { background: var(--amber); box-shadow: var(--shadow-pulse); }
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
  .msg.thought { color: var(--mute); font-size: 12px; font-style: italic; }
  .tool { display: flex; align-items: center; gap: 8px; font: 500 11.5px var(--font-mono); color: var(--mute); }
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
  .error { flex: none; padding: 6px var(--s-panel); color: var(--alert); font-size: 12px; }
  .composer button[type="submit"] { align-self: end; }
  .composer { flex: none; display: grid; grid-template-columns: 1fr auto; gap: 8px; align-items: stretch; padding: var(--s-md) var(--s-panel) var(--s-panel); border-top: 1px solid var(--line); }
  .attached { grid-column: 1 / -1; display: flex; flex-wrap: wrap; gap: 6px; }
  .att { display: inline-flex; align-items: center; gap: 2px; height: 28px; padding: 0 2px 0 10px; border: 1px solid var(--amber); border-radius: var(--r-pill); background: var(--amber-tint); font: 500 11.5px var(--font-mono); }
  .att button { width: 24px; height: 24px; display: grid; place-items: center; border-radius: 50%; color: var(--amber-ink); }
  .att button:hover { background: rgba(201, 138, 26, 0.2); }
  textarea { width: 100%; resize: none; min-height: 64px; padding: 10px 12px; border: 1px solid var(--line); border-radius: var(--r-button); background: #fff; line-height: 1.45; }
  textarea:disabled { background: var(--strip); }
</style>

<script lang="ts">
  import { renderMarkdown } from "../lib/markdown";
  import { onDestroy, tick } from "svelte";
  import { applyEvent, composeMessage, emptyTranscript, groupTurns, withUserMessages, workSummary, type ChatBlock, type Transcript } from "../lib/chat";
  import { GraphModel } from "../lib/model";
  import type { SessionClient } from "../lib/session";
  import type { MergedGraph, ViewState } from "../lib/types";
  import type { ConfigCategory, ConfigOption } from "../lib/api";
  import ContextCard from "./ContextCard.svelte";
  import Icon from "./Icon.svelte";
  import ModelPicker from "./ModelPicker.svelte";

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
  let config: ConfigOption[] = $state([]);
  let configReady = $state(false);
  let configBusy = $state(false);
  let configUnavailable = $state(false);
  let canConfigure = $state(true);
  let configTimer: ReturnType<typeof setTimeout> | undefined;

  const modelOption = $derived(config.find((o) => o.category === "model"));
  const levelOption = $derived(config.find((o) => o.category === "thought_level"));

  // The agent reports its options once the session is open and its model
  // selected; until then, ask again shortly.
  async function loadConfig(tries = 60) {
    clearTimeout(configTimer);
    try {
      const c = await session.config();
      config = c.options;
      configReady = c.ready;
      if (c.ready) return;
    } catch {
      // the session is still starting, or has ended
    }
    if (active && tries > 0) configTimer = setTimeout(() => loadConfig(tries - 1), 500);
    else configUnavailable = true;
  }

  async function choose(category: ConfigCategory, value: string) {
    configBusy = true;
    error = "";
    try {
      config = (await session.setConfig(category, value)).options;
    } catch (err) {
      error = err instanceof Error ? err.message : "The agent did not take the change.";
    } finally {
      configBusy = false;
    }
  }

  const items: ChatBlock[] = $derived(groupTurns(withUserMessages(transcript.items, messages), transcript.busy));
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
      canConfigure = status.can_configure !== false;
      if (active && canConfigure && !configReady) loadConfig();
      if (!active) {
        config = [];
        configReady = false;
        configUnavailable = false;
      }
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

  /** The first message starts the session; it is also the agent's first turn. */
  async function start(message: string, typed: string) {
    starting = true;
    error = "";
    messages = [{ time: Date.now() / 1000, text: message }];
    try {
      await session.start(message);
      attached = [];
      await refresh();
    } catch (err) {
      messages = [];
      draft = typed;
      error = err instanceof Error ? err.message : "Could not start the session.";
    } finally {
      starting = false;
    }
  }

  async function stop() {
    unsubscribe?.();
    unsubscribe = null;
    clearTimeout(configTimer);
    await session.stop();
    active = false;
    config = [];
    configReady = false;
    configUnavailable = false;
  }

  async function send(e?: Event) {
    e?.preventDefault();
    const text = draft.trim();
    if (!text || starting) return;
    const message = composeMessage(text, attachedNodes);
    draft = "";
    if (!active) return start(message, text);
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
  onDestroy(() => {
    unsubscribe?.();
    clearTimeout(configTimer);
  });
</script>

<ContextCard {model} {view} {attached} {onapprove} onattach={(k) => (attached = [...attached, k])} onselect={(k) => onselect(k)} />

<div class="session-bar">
  <span class="state" class:on={active || starting}><i></i>{starting ? "Starting session" : active ? (transcript.busy ? "Agent working" : "Planning session") : "No session"}</span>
  {#if active}
    <button type="button" class="ghost" onclick={stop}>End session</button>
  {/if}
</div>

<div class="log" bind:this={log} aria-live="polite" aria-label="Conversation">
  {#if !items.length}
    <p class="empty">Say what to plan, or select a node in the graph and point at it. Your first message starts a session with the planning agent. It works in the spec store and writes only under openspec/.</p>
  {/if}
  {#each items as item (item.key)}
    {#if item.kind === "user"}
      <div class="msg user">{item.text}</div>
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
  <textarea bind:value={draft} onkeydown={onkey} rows="3" placeholder={active ? "Message the planning agent" : "What should we plan?"} disabled={starting} aria-label="Message"></textarea>
  <div class="settings" aria-label="Agent settings">
    {#if active && !canConfigure}
      <p class="note" data-note="not-configurable">This session started before model choice existed, so its model can't change. End it; your next message starts a session where you can choose.</p>
    {:else if modelOption}
      <ModelPicker option={modelOption} disabled={!configReady || configBusy} onpick={(v) => choose("model", v)} />
    {:else if active}
      <p class="note">{configReady ? "The agent offers no model choice." : configUnavailable ? "The model choice did not load. End the session and start a new one to choose a model." : "Model: selecting…"}</p>
    {/if}
    {#if levelOption}
      <label class="level">
        <span>{levelOption.category === "thought_level" ? "Thinking" : levelOption.name}</span>
        <select
          value={levelOption.currentValue} disabled={!configReady || configBusy} data-config="thought_level"
          onchange={(e) => choose("thought_level", e.currentTarget.value)}
        >
          {#each levelOption.options as o (o.value)}<option value={o.value}>{o.name}</option>{/each}
        </select>
      </label>
    {/if}
  </div>
  <button type="submit" class="primary" disabled={starting || !draft.trim()}>{starting ? "Starting…" : "Send"}</button>
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
  .error { flex: none; padding: 6px var(--s-panel); color: var(--alert); font-size: 12px; }
  .composer button[type="submit"] { align-self: end; }
  .composer { flex: none; display: grid; grid-template-columns: 1fr auto; gap: 8px; align-items: stretch; padding: var(--s-md) var(--s-panel) var(--s-panel); border-top: 1px solid var(--line); }
  .attached { grid-column: 1 / -1; display: flex; flex-wrap: wrap; gap: 6px; }
  .att { display: inline-flex; align-items: center; gap: 2px; height: 28px; padding: 0 2px 0 10px; border: 1px solid var(--amber); border-radius: var(--r-pill); background: var(--amber-tint); font: 500 11.5px var(--font-mono); }
  .att button { width: 24px; height: 24px; display: grid; place-items: center; border-radius: 50%; color: var(--amber-ink); }
  .att button:hover { background: rgba(201, 138, 26, 0.2); }
  .settings { min-width: 0; display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }
  .note { margin: 0; font-size: 12px; line-height: 1.4; color: var(--mute); max-width: 52ch; }
  .level { display: inline-flex; align-items: center; gap: 6px; height: 32px; padding: 0 4px 0 10px; border: 1px solid var(--line); border-radius: var(--r-button); background: #fff; font-size: 12px; color: var(--mute); }
  .level:hover:has(select:not(:disabled)) { border-color: var(--ink); }
  .level select { height: 30px; border: 0; background: transparent; font: 600 12px var(--font-sans); color: var(--ink); cursor: pointer; }
  .level select:disabled { opacity: 0.55; cursor: default; }
  textarea { grid-column: 1 / -1; width: 100%; resize: none; min-height: 64px; padding: 10px 12px; border: 1px solid var(--line); border-radius: var(--r-button); background: #fff; line-height: 1.45; }
  textarea:disabled { background: var(--strip); }
</style>

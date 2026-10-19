<script lang="ts">
  import { tick } from "svelte";
  import type { ConfigOption } from "../lib/api";
  import Icon from "./Icon.svelte";

  let { option, disabled = false, onpick }: { option: ConfigOption; disabled?: boolean; onpick: (value: string) => void } = $props();

  let open = $state(false);
  let query = $state("");
  let active = $state(0);
  let root: HTMLElement | undefined = $state();
  let search: HTMLInputElement | undefined = $state();
  let list: HTMLElement | undefined = $state();

  const current = $derived(option.options.find((o) => o.value === option.currentValue));
  const matches = $derived.by(() => {
    const words = query.toLowerCase().split(/\s+/).filter(Boolean);
    return option.options.filter((o) => {
      const hay = `${o.name} ${o.value}`.toLowerCase();
      return words.every((w) => hay.includes(w));
    });
  });

  async function show() {
    open = true;
    query = "";
    active = Math.max(0, option.options.findIndex((o) => o.value === option.currentValue));
    await tick();
    search?.focus();
    scrollToActive();
  }

  function close(refocus = true) {
    open = false;
    if (refocus) root?.querySelector<HTMLButtonElement>(".trigger")?.focus();
  }

  function pick(value: string) {
    close();
    if (value !== option.currentValue) onpick(value);
  }

  function scrollToActive() {
    list?.querySelector(`[data-index="${active}"]`)?.scrollIntoView?.({ block: "nearest" });
  }

  async function onkey(e: KeyboardEvent) {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      const step = e.key === "ArrowDown" ? 1 : -1;
      active = Math.min(Math.max(active + step, 0), matches.length - 1);
      await tick();
      scrollToActive();
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (matches[active]) pick(matches[active].value);
    } else if (e.key === "Escape") {
      e.preventDefault();
      close();
    }
  }

  function outside(e: PointerEvent) {
    if (open && root && !root.contains(e.target as Node)) close(false);
  }
</script>

<svelte:window onpointerdown={outside} />

<div class="picker" bind:this={root}>
  <button
    type="button" class="trigger" {disabled} aria-haspopup="listbox" aria-expanded={open}
    title={option.currentValue ?? ""} onclick={() => (open ? close() : show())}
  >
    <span class="label">{option.name}</span>
    <span class="value">{current?.name ?? option.currentValue ?? "Agent default"}</span>
    <Icon name="chevron" size={12} />
  </button>
  {#if open}
    <div class="pop">
      <input
        bind:this={search} bind:value={query} oninput={() => (active = 0)} onkeydown={onkey}
        type="search" placeholder="Search {option.options.length} models" aria-label="Search models"
        role="combobox" aria-expanded="true" aria-controls="model-list" aria-activedescendant={matches[active] ? `model-${active}` : undefined}
      />
      <ul id="model-list" role="listbox" aria-label={option.name} bind:this={list}>
        {#each matches as o, i (o.value)}
          <!-- The search field owns the keyboard (combobox pattern); options take the pointer. -->
          <!-- svelte-ignore a11y_click_events_have_key_events -->
          <li
            id="model-{i}" role="option" data-index={i} data-value={o.value}
            aria-selected={o.value === option.currentValue} class:active={i === active}
            onpointerenter={() => (active = i)} onclick={() => pick(o.value)}
          >
            <span class="name">{o.name}</span>
            {#if o.value === option.currentValue}<span class="cur">Current</span>{/if}
          </li>
        {:else}
          <li class="none" role="presentation">No model matches “{query}”</li>
        {/each}
      </ul>
    </div>
  {/if}
</div>

<style>
  .picker { position: relative; min-width: 0; }
  .trigger { display: inline-flex; align-items: center; gap: 6px; max-width: 100%; height: 32px; padding: 0 10px; border: 1px solid var(--line); border-radius: var(--r-button); background: #fff; font-size: 12px; }
  .trigger:hover:not(:disabled) { border-color: var(--ink); }
  .trigger:disabled { opacity: 0.55; cursor: default; }
  .trigger :global(.ico) { transform: rotate(90deg); color: var(--mute); }
  .label { color: var(--mute); }
  .value { font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .pop { position: absolute; bottom: calc(100% + 6px); left: 0; z-index: 20; width: min(360px, 80vw); display: flex; flex-direction: column; border: 1px solid var(--line); border-radius: var(--r-well); background: #fff; box-shadow: var(--shadow-lift); overflow: hidden; }
  input { height: 38px; padding: 0 12px; border: 0; border-bottom: 1px solid var(--hair); font-size: 13px; background: #fff; }
  input:focus-visible { outline: none; }
  ul { list-style: none; margin: 0; padding: 4px; max-height: 280px; overflow-y: auto; }
  li { display: flex; align-items: center; gap: 8px; min-height: 32px; padding: 0 8px; border-radius: 6px; font-size: 12.5px; cursor: pointer; }
  li.active { background: var(--strip); }
  li[aria-selected="true"] .name { font-weight: 600; }
  .name { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .cur { font-size: 11px; color: var(--mute); }
  .none { color: var(--mute); cursor: default; }
</style>

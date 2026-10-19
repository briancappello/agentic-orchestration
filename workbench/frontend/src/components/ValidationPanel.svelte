<script lang="ts">
  import { errorTarget } from "../lib/sync";
  import type { PlanError } from "../lib/types";

  let { errors, has, onselect }: { errors: PlanError[]; has: (key: string) => boolean; onselect: (key: string) => void } = $props();
  let open = $state(true);
</script>

{#if errors.length}
  <section class="validation" aria-label="Validation errors">
    <header>
      <b>{errors.length} {errors.length === 1 ? "problem" : "problems"} in the plan</b>
      <span>The graph shows the last valid plan until they are fixed.</span>
      <button type="button" class="fold" aria-expanded={open} onclick={() => (open = !open)}>{open ? "Hide" : "Show"}</button>
    </header>
    {#if open}
      <ul>
        {#each errors as e, i (i)}
          {@const target = errorTarget(e, has)}
          <li>
            <button type="button" class="err" data-error={e.code} disabled={!target} onclick={() => target && onselect(target)}>
              <span class="code">{e.code}</span>
              <span class="where">{e.change ? (e.deliverable ? `${e.change}/${e.deliverable}` : e.change) : (e.file ?? "store")}</span>
              <span class="msg">{e.message}</span>
            </button>
          </li>
        {/each}
      </ul>
    {/if}
  </section>
{/if}

<style>
  .validation { flex: none; max-height: 30%; overflow-y: auto; border-bottom: 1px solid var(--alert); background: #fdf3f2; padding: 10px var(--s-gutter); }
  header { display: flex; align-items: baseline; gap: 10px; font-size: 12px; color: var(--mute); }
  header b { color: var(--alert); font-size: 13px; }
  .fold { margin-left: auto; font-size: 12px; font-weight: 600; color: var(--mute); }
  ul { list-style: none; margin-top: 6px; display: flex; flex-direction: column; gap: 2px; }
  .err { width: 100%; display: grid; grid-template-columns: auto auto 1fr; gap: 10px; align-items: baseline; padding: 4px 6px; margin: 0 -6px; border-radius: var(--r-tab); text-align: left; font-size: 12.5px; }
  .err:hover:not(:disabled) { background: rgba(196, 56, 47, 0.08); }
  .err:disabled { cursor: default; }
  .code { font: 500 11px var(--font-mono); color: var(--alert); }
  .where { font: 500 11.5px var(--font-mono); color: var(--ink); }
  .msg { color: var(--ink); }
</style>

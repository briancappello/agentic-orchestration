<script lang="ts" module>
  /** One level of the breadcrumb. The last is where the person is; the others go back up. */
  export interface Crumb {
    label: string;
    href?: string;
    onclick?: () => void;
  }
</script>

<script lang="ts">
  import type { Snippet } from "svelte";
  import Icon from "./Icon.svelte";

  let { crumbs, children }: { crumbs: Crumb[]; children?: Snippet } = $props();
</script>

<div class="bar">
<header class="top">
  <a class="logo" href="#/">Plan workbench</a>
  <nav class="crumbs" aria-label="Breadcrumb">
    <ol>
      {#each crumbs as c, i (i)}
        <li>
          {#if i > 0}<span class="sep"><Icon name="chevron" size={12} /></span>{/if}
          {#if i === crumbs.length - 1}
            <span class="here" aria-current="page" title={c.label}>{c.label}</span>
          {:else if c.href}
            <a class="up" href={c.href}>{c.label}</a>
          {:else}
            <button type="button" class="up" onclick={c.onclick}>{c.label}</button>
          {/if}
        </li>
      {/each}
    </ol>
  </nav>
  <span class="spacer"></span>
  {#if children}{@render children()}{/if}
</header>
</div>

<style>
  /* The bar sizes itself to its pane, which the person can make narrow. */
  .bar { flex: none; container-type: inline-size; }
  .top { height: 56px; display: flex; align-items: center; gap: 18px; padding: 0 var(--s-gutter); background: var(--ink); color: #fff; min-width: 0; }
  .logo { font-weight: 700; font-size: 16px; letter-spacing: -0.01em; white-space: nowrap; color: #fff; text-decoration: none; }
  .crumbs { flex: 0 1 auto; min-width: 0; overflow: hidden; }
  ol { display: flex; align-items: center; list-style: none; min-width: 0; }
  li { display: flex; align-items: center; min-width: 0; }
  li:last-child { flex: 0 1 auto; overflow: hidden; }
  .sep { display: inline-flex; padding: 0 6px; color: #6e6e73; }
  .up, .here { font-size: 13px; font-weight: 600; white-space: nowrap; }
  .up { color: #b8b8bd; text-decoration: none; padding: 4px 2px; border-radius: var(--r-tag); }
  .up:hover { color: #fff; text-decoration: underline; text-underline-offset: 3px; text-decoration-color: var(--ink-mute); }
  .here { color: #fff; overflow: hidden; text-overflow: ellipsis; display: block; }
  .spacer { flex: 1; }
  @container (max-width: 760px) {
    .top { gap: 12px; padding: 0 12px; }
    .logo { display: none; }
  }
</style>

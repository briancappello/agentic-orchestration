<script lang="ts">
  let { name, size = 14 }: { name: "arrow" | "external" | "close" | "chevron"; size?: number } = $props();
</script>

<svg class="ico" width={size} height={size} viewBox="0 0 14 14" aria-hidden="true">
  {#if name === "chevron"}
    <path d="M5.5 3.5L9 7l-3.5 3.5" />
  {:else if name === "arrow"}
    <path d="M2.5 7h8.5M7.5 3.5L11 7l-3.5 3.5" />
  {:else if name === "external"}
    <path d="M5 3H3v8h8V9M8 3h3v3M11 3L6.5 7.5" />
  {:else}
    <path d="M3.5 3.5l7 7M10.5 3.5l-7 7" />
  {/if}
</svg>

<style>
  .ico { display: inline-block; flex: none; vertical-align: -2px; fill: none; stroke: currentColor; stroke-width: 1.6; stroke-linecap: round; stroke-linejoin: round; }
</style>

<script lang="ts">
  import Shell from "./components/Shell.svelte";
</script>

<Shell>
  {#snippet graph()}<p class="placeholder">Plan graph</p>{/snippet}
  {#snippet chat()}<p class="placeholder">Planning chat</p>{/snippet}
</Shell>

<style>
  .placeholder { padding: var(--s-panel); color: var(--mute); }
</style>

<script lang="ts">
  import Shell from "../src/components/Shell.svelte";
  let { width }: { width?: number } = $props();
</script>

<Shell {width}>
  {#snippet graph()}<p>graph</p>{/snippet}
  {#snippet chat()}<p>chat</p>{/snippet}
</Shell>

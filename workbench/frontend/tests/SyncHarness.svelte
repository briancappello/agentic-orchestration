<script lang="ts">
  import SyncDialog from "../src/components/SyncDialog.svelte";
  import type { SyncClient } from "../src/lib/sync";
  let { sync }: { sync: SyncClient } = $props();
  let open = $state(true);
  export function isOpen() { return open; }
</script>

{#if open}<SyncDialog {sync} onclose={() => (open = false)} />{/if}

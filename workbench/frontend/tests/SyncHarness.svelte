<script lang="ts">
  import SyncStatus from "../src/components/SyncStatus.svelte";
  import type { SyncStatus as Status } from "../src/lib/types";
  let { status, onretry }: { status: Status | null; onretry: () => Promise<unknown> } = $props();
</script>

<SyncStatus {status} {onretry} />

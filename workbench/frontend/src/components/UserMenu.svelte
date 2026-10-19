<script lang="ts">
  import { api } from "../lib/api";
  import { session } from "../lib/identity.svelte";

  async function signOut() {
    const r = await api.logout().catch(() => null);
    if (r?.end_session_url) location.assign(r.end_session_url);
    else location.reload();
  }
</script>

{#if session.identity}
  <span class="user" title={session.identity.email || session.identity.id}>
    <span class="name">{session.identity.name}</span>
    {#if session.about}
      <a class="out" href={session.about.source_url} rel="noopener" title="Free software under the {session.about.license}">Source</a>
    {/if}
    <button type="button" class="out" onclick={signOut}>Sign out</button>
  </span>
{/if}

<style>
  .user { display: inline-flex; align-items: center; gap: 10px; white-space: nowrap; }
  .name { font-size: 13px; font-weight: 600; color: #fff; max-width: 18ch; overflow: hidden; text-overflow: ellipsis; }
  .out { font-size: 12px; font-weight: 600; color: #b8b8bd; padding: 4px 6px; border-radius: var(--r-tag); text-decoration: none; }
  .out:hover { color: #fff; text-decoration: underline; text-underline-offset: 3px; }
  @container (max-width: 760px) { .name { display: none; } }
</style>

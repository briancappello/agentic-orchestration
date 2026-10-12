<script lang="ts">
  import { api, ApiError } from "../lib/api";

  let { onsignedin }: { onsignedin: () => void } = $props();
  let password = $state("");
  let error = $state("");
  let busy = $state(false);

  async function submit(e: SubmitEvent) {
    e.preventDefault();
    busy = true;
    error = "";
    try {
      await api.login(password);
      onsignedin();
    } catch (err) {
      error = err instanceof ApiError && err.status === 401 ? "That password is not right." : "The workbench did not answer.";
    } finally {
      busy = false;
    }
  }
</script>

<main class="login">
  <form onsubmit={submit}>
    <h1>Plan workbench</h1>
    <p>Sign in to see the plan and talk to the planning agent.</p>
    <label for="pw">Operator password</label>
    <input id="pw" type="password" autocomplete="current-password" bind:value={password} required />
    {#if error}<p class="error" role="alert">{error}</p>{/if}
    <button type="submit" disabled={busy || !password}>{busy ? "Signing in…" : "Sign in"}</button>
  </form>
</main>

<style>
  .login { min-height: 100%; display: grid; place-items: center; padding: var(--s-panel); }
  form { width: min(360px, 100%); display: flex; flex-direction: column; gap: var(--s-md); }
  h1 { font-size: 26px; font-weight: 700; letter-spacing: -0.02em; }
  p { color: var(--mute); }
  label { font-size: 11px; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; color: var(--mute); margin-top: var(--s-sm); }
  input { height: 42px; padding: 0 var(--s-md); border: 1px solid var(--line); border-radius: var(--r-button); background: #fff; }
  button { height: 42px; border-radius: var(--r-button); background: var(--ink); color: #fff; font-weight: 700; font-size: 14px; }
  button:hover:not(:disabled) { background: #000; }
  button:disabled { opacity: 0.5; cursor: default; }
  .error { color: var(--alert); }
</style>

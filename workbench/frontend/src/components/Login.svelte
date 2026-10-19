<script lang="ts">
  import { api, ApiError } from "../lib/api";
  import { SIGN_IN_ERRORS, session } from "../lib/identity.svelte";

  let { mode, error: signInError = "", onsignedin }: { mode: "oidc" | "local"; error?: string; onsignedin: () => void } = $props();
  let password = $state("");
  let error = $state("");
  let busy = $state(false);

  // Back to the page the person opened once the provider signs them in.
  const next = $derived("/" + (location.hash || "#/"));
  const href = $derived(`/api/auth/login?next=${encodeURIComponent(next)}`);
  const shown = $derived(error || (signInError ? (SIGN_IN_ERRORS[signInError] ?? "The sign-in did not complete.") : ""));

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
  {#if mode === "oidc"}
    <div class="box">
      <h1>Plan workbench</h1>
      <p>Sign in with your team account to see the plan and talk to the planning agent.</p>
      {#if shown}<p class="error" role="alert">{shown}</p>{/if}
      <a class="button" {href}>Sign in</a>
    </div>
  {:else}
    <form class="box" onsubmit={submit}>
      <h1>Plan workbench</h1>
      <p>Sign in to see the plan and talk to the planning agent.</p>
      <label for="pw">Operator password</label>
      <input id="pw" type="password" autocomplete="current-password" bind:value={password} required />
      {#if shown}<p class="error" role="alert">{shown}</p>{/if}
      <button type="submit" disabled={busy || !password}>{busy ? "Signing in…" : "Sign in"}</button>
      <p class="note">Local mode: one shared password, for development.</p>
    </form>
  {/if}
  {#if session.about}
    <p class="source">
      Free software under the {session.about.license}.
      <a href={session.about.source_url} rel="noopener">Get the source code</a>
    </p>
  {/if}
</main>

<style>
  .login { min-height: 100%; display: grid; place-items: center; grid-template-rows: 1fr auto; padding: var(--s-panel); }
  .source { font-size: 12px; text-align: center; }
  .source a { color: var(--ink); text-decoration: underline; text-underline-offset: 3px; }
  .box { width: min(360px, 100%); display: flex; flex-direction: column; gap: var(--s-md); }
  h1 { font-size: 26px; font-weight: 700; letter-spacing: -0.02em; }
  p { color: var(--mute); }
  label { font-size: 11px; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; color: var(--mute); margin-top: var(--s-sm); }
  input { height: 42px; padding: 0 var(--s-md); border: 1px solid var(--line); border-radius: var(--r-button); background: #fff; }
  button, .button { height: 42px; border-radius: var(--r-button); background: var(--ink); color: #fff; font-weight: 700; font-size: 14px;
    display: grid; place-items: center; text-decoration: none; }
  button:hover:not(:disabled), .button:hover { background: #000; }
  button:disabled { opacity: 0.5; cursor: default; }
  .error { color: var(--alert); }
  .note { font-size: 12px; }
</style>

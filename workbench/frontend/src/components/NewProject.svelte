<script lang="ts">
  import { api, ApiError } from "../lib/api";
  import { suggestKey, suggestSlug } from "../lib/router";
  import type { ProjectSummary, TrackerProject } from "../lib/types";
  import TopBar from "./TopBar.svelte";

  let {
    client = api,
    oncreated,
  }: {
    client?: Pick<typeof api, "createProject">;
    oncreated: (project: ProjectSummary, tracker: TrackerProject) => void;
  } = $props();

  let name = $state("");
  let slug = $state("");
  let key = $state("");
  // A field the person typed in keeps their value; the others follow the name.
  let slugEdited = $state(false);
  let keyEdited = $state(false);
  let busy = $state(false);
  let errors: Record<string, string> = $state({});
  let formError = $state("");

  const shownSlug = $derived(slugEdited ? slug : suggestSlug(name));
  const shownKey = $derived(keyEdited ? key : suggestKey(name));

  async function submit(e: SubmitEvent) {
    e.preventDefault();
    busy = true;
    errors = {};
    formError = "";
    try {
      const { project, tracker } = await client.createProject({ name, slug: shownSlug, huly_project: shownKey });
      oncreated(project, tracker);
    } catch (err) {
      if (err instanceof ApiError) {
        const field = (err.body as { error?: { field?: string } } | null)?.error?.field;
        if (field) errors = { [field]: err.message };
        else formError = err.message;
      } else {
        formError = "The workbench did not answer. Try again.";
      }
    } finally {
      busy = false;
    }
  }
</script>

<svelte:head><title>New project · Plan workbench</title></svelte:head>

<div class="page">
  <TopBar crumbs={[{ label: "Projects", href: "#/" }, { label: "New project" }]} />

  <main class="body">
    <form onsubmit={submit} novalidate>
      <h1>New project</h1>
      <p class="lede">The workbench creates an empty spec store for the plan, and the Huly project it syncs into if it does not exist yet.</p>

      <div class="field">
        <label for="np-name">Name</label>
        <input id="np-name" bind:value={name} maxlength="80" autocomplete="off" required aria-invalid={!!errors.name}
          aria-describedby={errors.name ? "np-name-err" : undefined} />
        {#if errors.name}<p class="err" id="np-name-err">{errors.name}</p>{/if}
      </div>

      <div class="field">
        <label for="np-slug">Slug</label>
        <input id="np-slug" class="mono" value={shownSlug} maxlength="48" autocomplete="off" spellcheck="false"
          oninput={(e) => { slug = e.currentTarget.value; slugEdited = true; }}
          aria-invalid={!!errors.slug} aria-describedby="np-slug-hint{errors.slug ? ' np-slug-err' : ''}" />
        <p class="hint" id="np-slug-hint">Names the project in links and its folder on disk. Lower-case letters, digits and dashes. It cannot change later.</p>
        {#if errors.slug}<p class="err" id="np-slug-err">{errors.slug}</p>{/if}
      </div>

      <div class="field">
        <label for="np-key">Huly project</label>
        <input id="np-key" class="mono key" value={shownKey} maxlength="5" autocomplete="off" spellcheck="false"
          oninput={(e) => { key = e.currentTarget.value.toUpperCase(); e.currentTarget.value = key; keyEdited = true; }}
          aria-invalid={!!errors.huly_project} aria-describedby="np-key-hint{errors.huly_project ? ' np-key-err' : ''}" />
        <p class="hint" id="np-key-hint">The key of the Huly project the plan syncs into, such as <code>BILL</code>. An existing project is linked as it is; a missing one is created.</p>
        {#if errors.huly_project}<p class="err" id="np-key-err">{errors.huly_project}</p>{/if}
      </div>

      {#if formError}<p class="err form-err" role="alert">{formError}</p>{/if}

      <div class="buttons">
        <button type="submit" class="primary" disabled={busy || !name.trim() || !shownSlug || !shownKey}>
          {busy ? "Creating…" : "Create project"}
        </button>
        <a class="ghost" href="#/">Cancel</a>
      </div>
    </form>
  </main>
</div>

<style>
  .page { height: 100%; display: flex; flex-direction: column; background: var(--paper); }
  .body { flex: 1; min-height: 0; overflow: auto; padding: 40px var(--s-gutter) 64px; }
  form { width: min(520px, 100%); padding: var(--s-panel); border: 1px solid var(--line); border-radius: var(--r-well); background: var(--panel); }
  h1 { font-size: 26px; font-weight: 700; line-height: 1.12; letter-spacing: -0.02em; }
  .lede { margin: 8px 0 var(--s-section); color: var(--mute); max-width: 56ch; }
  .field { display: flex; flex-direction: column; gap: 6px; margin-bottom: 18px; }
  label { font-size: 11px; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; color: var(--mute); }
  input { height: 42px; padding: 0 var(--s-md); border: 1px solid var(--line); border-radius: var(--r-button); background: #fff; font: 400 14px var(--font-sans); color: var(--ink); }
  input:hover { border-color: #c8c8c2; }
  input:focus-visible { border-color: var(--ink); }
  input[aria-invalid="true"] { border-color: var(--alert); }
  input.mono { font: 500 13px var(--font-mono); }
  input.key { width: 120px; letter-spacing: 0.04em; }
  .hint { font-size: 12px; color: var(--mute); max-width: 60ch; }
  .hint code { font: 500 11.5px var(--font-mono); color: var(--ink); }
  .err { font-size: 12.5px; color: var(--alert); }
  .form-err { margin-bottom: 14px; }
  .buttons { display: flex; gap: 8px; margin-top: 6px; }
  .primary { height: 42px; padding: 0 20px; border-radius: var(--r-button); background: var(--ink); color: #fff; font-weight: 700; font-size: 14px; }
  .primary:hover:not(:disabled) { background: #000; }
  .primary:disabled { opacity: 0.45; cursor: default; }
  .ghost { height: 42px; display: inline-flex; align-items: center; padding: 0 18px; border: 1px solid var(--line); border-radius: var(--r-button); background: #fff; color: var(--ink); font-weight: 600; text-decoration: none; }
  .ghost:hover { background: var(--strip); }
</style>

<script lang="ts">
  import { tick } from "svelte";
  import { api, ApiError } from "../lib/api";
  import { projectHref } from "../lib/router";
  import type { ProjectSummary } from "../lib/types";
  import TopBar from "./TopBar.svelte";

  let { client = api }: { client?: Pick<typeof api, "projects" | "renameProject" | "deleteProject"> } = $props();

  let projects: ProjectSummary[] | null = $state(null);
  let loadError = $state("");
  let renaming: string | null = $state(null);
  let newName = $state("");
  let confirming: string | null = $state(null);
  let busy = $state(false);
  let rowError = $state("");
  let notice = $state("");

  const sessions = $derived((projects ?? ([] as ProjectSummary[])).filter((p) => p.session_active).length);

  async function load() {
    try {
      projects = (await client.projects()).projects;
      loadError = "";
    } catch {
      loadError = "The workbench did not answer. Reload to try again.";
    }
  }
  load();

  async function startRename(p: ProjectSummary) {
    confirming = null;
    rowError = "";
    renaming = p.slug;
    newName = p.name;
    await tick();
    document.querySelector<HTMLInputElement>(`#rename-${p.slug}`)?.select();
  }

  async function saveRename(e: SubmitEvent, p: ProjectSummary) {
    e.preventDefault();
    busy = true;
    try {
      const { project } = await client.renameProject(p.slug, newName);
      projects = projects!.map((x) => (x.slug === p.slug ? project : x));
      renaming = null;
      rowError = "";
    } catch (err) {
      rowError = err instanceof ApiError ? err.message : "The name was not saved.";
    } finally {
      busy = false;
    }
  }

  async function remove(p: ProjectSummary) {
    busy = true;
    try {
      const gone = await client.deleteProject(p.slug);
      projects = projects!.filter((x) => x.slug !== p.slug);
      confirming = null;
      notice = `Removed ${p.name}. Its spec store is still at ${gone.store_path}, and Huly project ${gone.huly_project} is unchanged.`;
    } catch (err) {
      rowError = err instanceof ApiError ? err.message : "The project was not removed.";
    } finally {
      busy = false;
    }
  }

  function onkeydown(e: KeyboardEvent) {
    if (e.key === "Escape") {
      renaming = null;
      confirming = null;
      rowError = "";
    }
  }
</script>

<svelte:head><title>Projects · Plan workbench</title></svelte:head>

<div class="page">
  <TopBar crumbs={[{ label: "Projects" }]}>
    <a class="new" href="#/new">New project</a>
  </TopBar>

  <div class="strip">
    {#if projects}
      <p><b>{projects.length} {projects.length === 1 ? "project" : "projects"}</b>
        · {sessions} planning {sessions === 1 ? "session" : "sessions"} open</p>
    {/if}
  </div>

  <main class="body">
    {#if notice}
      <p class="notice" role="status">{notice} <button type="button" class="link" onclick={() => (notice = "")}>Dismiss</button></p>
    {/if}

    {#if loadError}
      <p class="load-error" role="alert">{loadError}</p>
    {:else if projects === null}
      <p class="loading">Loading projects…</p>
    {:else if projects.length === 0}
      <div class="empty">
        <h1>No projects yet</h1>
        <p>A project is a spec store the planning agent writes in, paired with the Huly project its plan syncs into.</p>
        <a class="primary" href="#/new">New project</a>
      </div>
    {:else}
      <ul class="list" aria-label="Projects">
        {#each projects as p (p.slug)}
          <li class="row" class:open={confirming === p.slug}>
            <div class="who">
              {#if renaming === p.slug}
                <form class="rename" onsubmit={(e) => saveRename(e, p)}>
                  <label class="sr" for="rename-{p.slug}">Name of {p.name}</label>
                  <input id="rename-{p.slug}" bind:value={newName} maxlength="80" required {onkeydown} />
                  <button type="submit" class="small dark" disabled={busy || !newName.trim()}>Save</button>
                  <button type="button" class="small" onclick={() => { renaming = null; rowError = ""; }}>Cancel</button>
                </form>
              {:else}
                <a class="name" href={projectHref(p.slug)}>{p.name}</a>
              {/if}
              <p class="ids"><code>{p.slug}</code><span aria-hidden="true">·</span><code title="Huly project">{p.huly_project}</code></p>
              <p class="path" title={p.store_path}>{p.store_path}</p>
            </div>

            <dl class="facts">
              <div><dt>Epics</dt><dd>{p.epics}</dd></div>
              <div><dt>Stories</dt><dd>{p.stories}</dd></div>
              <div><dt>Plan</dt><dd class:bad={!p.valid}>{p.valid ? "Valid" : `${p.errors} ${p.errors === 1 ? "problem" : "problems"}`}</dd></div>
            </dl>

            <ul class="signals">
              {#if p.session_active}<li class="live"><i class="pulse" aria-hidden="true"></i>Planning session open</li>{/if}
              <li class:muted={!p.sortie.dispatched}>
                {#if !p.sortie.reachable}Sortie unreachable{:else if p.sortie.dispatched}Agents dispatched{:else}Agents not dispatched{/if}
              </li>
            </ul>

            <div class="actions">
              {#if renaming !== p.slug}
                <button type="button" class="small" onclick={() => startRename(p)}>Rename</button>
                <button type="button" class="small" aria-expanded={confirming === p.slug}
                  onclick={() => { renaming = null; rowError = ""; confirming = confirming === p.slug ? null : p.slug; }}>Remove</button>
              {/if}
            </div>

            {#if confirming === p.slug}
              <div class="confirm" role="group" aria-label="Remove {p.name}">
                <p>
                  Remove <b>{p.name}</b> from the workbench?
                  {#if p.session_active}Its planning session ends.{/if}
                  Nothing is deleted: the spec store stays at <code>{p.store_path}</code>, and Huly project <code>{p.huly_project}</code> keeps its issues.
                </p>
                <div>
                  <button type="button" class="small danger" disabled={busy} onclick={() => remove(p)}>{busy ? "Removing…" : "Remove project"}</button>
                  <button type="button" class="small" onclick={() => (confirming = null)}>Keep it</button>
                </div>
              </div>
            {/if}
            {#if rowError && (renaming === p.slug || confirming === p.slug)}
              <p class="row-error" role="alert">{rowError}</p>
            {/if}
          </li>
        {/each}
      </ul>
    {/if}
  </main>
</div>

<svelte:window {onkeydown} />

<style>
  .page { height: 100%; display: flex; flex-direction: column; background: var(--paper); }
  .new { height: 32px; display: inline-flex; align-items: center; padding: 0 14px; border-radius: var(--r-button); background: #fff; color: var(--ink); font-weight: 700; text-decoration: none; white-space: nowrap; }
  .new:hover { background: var(--strip); }

  .strip { flex: none; min-height: 48px; display: flex; align-items: center; padding: 8px var(--s-gutter); border-bottom: 1px solid var(--line); background: var(--strip); font-size: 12px; color: var(--mute); }
  .strip b { color: var(--ink); font-size: 13px; }

  .body { flex: 1; min-height: 0; overflow: auto; padding: var(--s-section) var(--s-gutter) 48px; }
  .loading, .load-error { color: var(--mute); }
  .load-error { color: var(--alert); }
  .notice { max-width: 980px; margin-bottom: var(--s-md); padding: 10px 14px; border: 1px solid var(--line); border-radius: var(--r-card); background: var(--panel); font-size: 13px; }
  .link { margin-left: 6px; color: var(--mute); text-decoration: underline; text-underline-offset: 3px; }

  .empty { max-width: 46ch; margin: 64px 0 0 20px; }
  .empty h1 { font: italic 400 26px/1.1 var(--font-serif); margin-bottom: 10px; }
  .empty p { color: var(--mute); margin-bottom: 20px; }
  .primary { display: inline-flex; align-items: center; height: 42px; padding: 0 20px; border-radius: var(--r-button); background: var(--ink); color: #fff; font-weight: 700; font-size: 14px; text-decoration: none; }
  .primary:hover { background: #000; }

  .list { list-style: none; max-width: 980px; border-top: 1px solid var(--line); }
  .row { display: grid; grid-template-columns: minmax(0, 1fr) auto 190px auto; align-items: center; column-gap: 32px; padding: 16px 4px; border-bottom: 1px solid var(--line); }
  .row:hover { background: rgba(244, 244, 242, 0.6); }

  .who { min-width: 0; }
  .name { font-size: 15px; font-weight: 600; letter-spacing: -0.005em; color: var(--ink); text-decoration: none; }
  .name:hover { text-decoration: underline; text-underline-offset: 3px; text-decoration-color: var(--line); }
  .ids { display: flex; gap: 6px; margin-top: 3px; color: var(--mute); font-size: 11px; }
  code { font: 500 11px var(--font-mono); color: var(--mute); }
  .path { margin-top: 2px; font: 500 10.5px var(--font-mono); color: var(--mute); opacity: 0.8; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

  .facts { display: flex; gap: 24px; }
  .facts dt { font-size: 10px; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; color: var(--mute); }
  .facts dd { margin-top: 2px; font-size: 15px; font-weight: 700; font-variant-numeric: tabular-nums; }
  .facts dd.bad { color: var(--alert); font-size: 13px; padding-top: 2px; }

  .signals { list-style: none; display: flex; flex-direction: column; gap: 4px; font-size: 12px; }
  .signals .muted { color: var(--mute); }
  .live { display: flex; align-items: center; gap: 7px; color: var(--amber-ink); font-weight: 600; }
  .pulse { width: 8px; height: 8px; border-radius: 50%; background: var(--amber); box-shadow: var(--shadow-pulse); }

  .actions { display: flex; gap: 6px; justify-content: flex-end; }
  .small { height: 30px; padding: 0 12px; border: 1px solid var(--line); border-radius: var(--r-button); background: var(--panel); color: var(--ink); font-size: 12.5px; font-weight: 600; white-space: nowrap; }
  .small:hover:not(:disabled) { background: var(--strip); }
  .small:disabled { opacity: 0.5; cursor: default; }
  .small.dark { background: var(--ink); border-color: var(--ink); color: #fff; }
  .small.dark:hover:not(:disabled) { background: #000; }
  .small.danger { border-color: var(--alert); color: var(--alert); }
  .small.danger:hover:not(:disabled) { background: #fbeeed; }

  .rename { display: flex; gap: 6px; align-items: center; }
  .rename input { height: 30px; width: min(320px, 100%); padding: 0 10px; border: 1px solid var(--ink); border-radius: var(--r-tag); font: 600 15px var(--font-sans); background: #fff; }

  .confirm { grid-column: 1 / -1; display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px 24px; margin-top: 14px; padding: 12px 14px; border: 1px solid var(--line); border-radius: var(--r-card); background: var(--panel); font-size: 13px; }
  .confirm p { max-width: 72ch; }
  .confirm code { color: var(--ink); }
  .confirm div { display: flex; gap: 6px; }
  .row-error { grid-column: 1 / -1; margin-top: 8px; color: var(--alert); font-size: 12.5px; }

  .sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); }

  @media (max-width: 900px) {
    .row { grid-template-columns: minmax(0, 1fr) auto; row-gap: 12px; }
    .signals { grid-column: 1; }
    .actions { grid-column: 2; grid-row: 1; }
    .facts { grid-column: 1 / -1; grid-row: 2; }
  }
</style>

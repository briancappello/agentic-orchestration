<script lang="ts">
  import Login from "./components/Login.svelte";
  import NewProject from "./components/NewProject.svelte";
  import ProjectsPage from "./components/ProjectsPage.svelte";
  import ProjectView from "./components/ProjectView.svelte";
  import { api } from "./lib/api";
  import { session } from "./lib/identity.svelte";
  import { formatRoute, parseRoute, projectHref, type Route } from "./lib/router";

  let signedIn: boolean | null = $state(null);
  // A sign-in the provider sent back with an error lands on #/signin?error=…
  let signInError = $state(new URLSearchParams(location.hash.split("?")[1] ?? "").get("error") ?? "");
  if (location.hash.startsWith("#/signin")) history.replaceState(null, "", "#/");
  let route: Route = $state(parseRoute(location.hash));

  function onhashchange() {
    route = parseRoute(location.hash);
  }

  // Keep the URL on the project's current level and selection, without
  // adding a history entry for every click in the graph.
  $effect(() => {
    if (route.name !== "project") return;
    const next = formatRoute(route);
    if (location.hash !== next) history.replaceState(null, "", next);
  });

  async function start() {
    try {
      const me = await api.me();
      session.identity = me.identity;
      session.mode = me.mode;
      signedIn = true;
    } catch {
      session.identity = null;
      try {
        session.mode = (await api.authMode()).mode;
      } catch {
        session.mode = "local";
      }
      signedIn = false;
    }
  }
  start();
  api.about().then((a) => (session.about = a)).catch(() => {});
</script>

<svelte:window {onhashchange} />

{#if signedIn === false}
  <Login mode={session.mode} error={signInError} onsignedin={start} />
{:else if signedIn}
  {#if route.name === "projects"}
    <ProjectsPage />
  {:else if route.name === "new"}
    <NewProject oncreated={(p) => (location.hash = projectHref(p.slug))} />
  {:else}
    {#key route.slug}
      <ProjectView slug={route.slug} bind:view={route.view} onmissing={() => (location.hash = "#/")} />
    {/key}
  {/if}
{/if}

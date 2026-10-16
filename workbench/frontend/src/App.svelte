<script lang="ts">
  import Login from "./components/Login.svelte";
  import NewProject from "./components/NewProject.svelte";
  import ProjectsPage from "./components/ProjectsPage.svelte";
  import ProjectView from "./components/ProjectView.svelte";
  import { api } from "./lib/api";
  import { formatRoute, parseRoute, projectHref, type Route } from "./lib/router";

  let signedIn: boolean | null = $state(null);
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
      await api.me();
      signedIn = true;
    } catch {
      signedIn = false;
    }
  }
  start();
</script>

<svelte:window {onhashchange} />

{#if signedIn === false}
  <Login onsignedin={start} />
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

<script lang="ts">
  import type { GraphModel } from "../lib/model";
  import type { GraphNode, ViewState } from "../lib/types";

  let {
    model, view, attached, onattach, onselect,
  }: {
    model: GraphModel;
    view: ViewState;
    attached: string[];
    onattach: (key: string) => void;
    onselect: (key: string) => void;
  } = $props();

  let open = $state(true);
  const node = $derived(model.node(view.selected));
  const scope = $derived(view.epic ? model.storiesOf(view.epic) : model.epics);
  const ready = $derived(scope.filter((n) => model.isReady(n)));
  const active = $derived(scope.filter((n) => (n.kind === "epic" ? model.badge(n) !== null : n.runtime !== null)));
  const unplanned = $derived(scope.filter((n) => n.has_spec === false));
  const noun = $derived(view.epic ? "stories" : "epics");

  function why(n: GraphNode): string {
    return model.badge(n)?.label ?? model.statusLabel(n);
  }
</script>

<section class="context" aria-label="Context">
  <header>
    <span class="label">{node ? (node.kind === "epic" ? "Selected change" : "Selected deliverable") : "Plan at a glance"}</span>
    <button type="button" class="fold" aria-expanded={open} onclick={() => (open = !open)}>{open ? "Hide" : "Show"}</button>
  </header>

  {#if open}
    {#if node}
      <div class="sel">
        <h2>{node.title}</h2>
        <div class="chips">
          <span class="chip id">{node.plan_key}</span>
          <span class="chip {model.statusClass(node)}"><i></i>{model.statusLabel(node)}</span>
          {#if node.status === "orphaned"}<span class="chip">orphaned: no longer in the plan</span>{/if}
          {#if node.approval}<span class="chip">breakdown {node.approval}</span>{/if}
        </div>

        {#if node.runtime}
          <div class="agent" class:warn={node.runtime.status !== "running"}>
            <b>{model.badge(node)?.label}</b>
            {#if node.runtime.last_message}<p>{node.runtime.last_message}</p>{/if}
          </div>
        {/if}

        <dl>
          <dt>Spec</dt>
          <dd>
            {#if node.covers.length}
              <ul class="refs">{#each node.covers as c (c)}<li>{c}</li>{/each}</ul>
            {:else if node.kind === "story"}<span class="none">No spec yet</span>
            {:else}<span class="mono">openspec/changes/{node.change}</span>{/if}
          </dd>
          {#if node.acceptance_criteria.length}
            <dt>Acceptance</dt>
            <dd><ul class="ac">{#each node.acceptance_criteria as a, i (i)}<li>{a}</li>{/each}</ul></dd>
          {/if}
          <dt>Depends on</dt>
          <dd>
            {#each model.blockers(node.plan_key) as k (k)}
              <button type="button" class="link" onclick={() => onselect(k)}>{k}</button>
            {:else}<span class="none">Nothing</span>{/each}
          </dd>
          <dt>Unblocks</dt>
          <dd>
            {#each model.unblocks(node.plan_key) as k (k)}
              <button type="button" class="link" onclick={() => onselect(k)}>{k}</button>
            {:else}<span class="none">Nothing</span>{/each}
          </dd>
          {#if node.tracker}
            <dt>Tracker</dt>
            <dd>{#if node.tracker.url}<a href={node.tracker.url} target="_blank" rel="noopener">{node.tracker.identifier} ↗</a>{:else}{node.tracker.identifier}{/if}</dd>
          {/if}
        </dl>
        {#if !attached.includes(node.plan_key)}
          <button type="button" class="attach" onclick={() => onattach(node.plan_key)}>Attach to message</button>
        {/if}
      </div>
    {:else}
      <div class="lists">
        {#each [["Ready to start", ready], ["Agent activity", active], ["Without a spec", unplanned]] as [title, list] (title)}
          <div>
            <span class="label">{title}</span>
            <ul class="list" data-list={title}>
              {#each list as GraphNode[] as n (n.plan_key)}
                <li><button type="button" onclick={() => onselect(n.plan_key)}><span class="dot {model.statusClass(n)}"></span>{n.title}<em>{why(n)}</em></button></li>
              {:else}<li class="none">No {noun}</li>{/each}
            </ul>
          </div>
        {/each}
      </div>
    {/if}
  {/if}
</section>

<style>
  .context { flex: none; max-height: 45%; overflow-y: auto; padding: var(--s-gutter) var(--s-panel); border-bottom: 1px solid var(--line); display: flex; flex-direction: column; gap: var(--s-md); }
  header { display: flex; justify-content: space-between; align-items: center; }
  .label { font-size: 11px; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; color: var(--mute); }
  .fold { font-size: 12px; font-weight: 600; color: var(--mute); }
  .fold:hover { color: var(--ink); }
  h2 { font-size: 20px; font-weight: 700; line-height: 1.15; letter-spacing: -0.015em; text-wrap: balance; }
  .chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
  .chip { display: inline-flex; align-items: center; gap: 6px; height: 24px; padding: 0 9px; border: 1px solid var(--line); border-radius: var(--r-pill); font-size: 12px; font-weight: 600; }
  .chip i { width: 8px; height: 8px; border-radius: 50%; background: var(--c); }
  .chip.done { --c: var(--done); border-color: #b9d3c3; background: var(--done-tint); color: var(--done); }
  .chip.prog { --c: var(--amber); border-color: #ecc77f; background: var(--amber-tint); color: var(--amber-ink); }
  .chip.todo { --c: var(--slate); background: var(--slate-tint); color: var(--slate-ink); }
  .chip.id { font: 500 11.5px var(--font-mono); color: var(--mute); }
  .agent { margin-top: var(--s-md); padding: 12px 14px; border-radius: var(--r-well); background: var(--ink); color: #fff; }
  .agent.warn { background: #fff; color: var(--ink); border: 1px solid var(--alert); }
  .agent p { margin-top: 6px; font: 500 12px/1.5 var(--font-mono); color: #c7c7cc; }
  .agent.warn p { color: var(--mute); }
  dl { display: grid; grid-template-columns: 92px 1fr; gap: 8px 12px; margin-top: var(--s-md); font-size: 13px; }
  dt { font-size: 11px; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; color: var(--mute); padding-top: 2px; }
  dd { display: flex; flex-wrap: wrap; gap: 4px 10px; min-width: 0; }
  .refs, .ac { list-style: none; display: flex; flex-direction: column; gap: 3px; }
  .refs li, .mono { font: 500 11.5px var(--font-mono); word-break: break-word; }
  .ac li { padding-left: 12px; position: relative; }
  .ac li::before { content: "–"; position: absolute; left: 0; color: var(--mute); }
  .link { font: 500 11.5px var(--font-mono); text-decoration: underline; text-underline-offset: 3px; text-decoration-color: var(--line); }
  .link:hover { text-decoration-color: var(--ink); }
  .none { color: var(--mute); font-size: 12px; }
  .attach { margin-top: var(--s-md); height: 34px; padding: 0 12px; border: 1px solid var(--line); border-radius: var(--r-button); background: #fff; font-weight: 600; }
  .attach:hover { border-color: var(--ink); }
  .lists { display: flex; flex-direction: column; gap: var(--s-md); }
  .list { list-style: none; display: flex; flex-direction: column; gap: 2px; margin-top: 6px; }
  .list button { width: 100%; display: flex; align-items: center; gap: 10px; padding: 4px 6px; margin: 0 -6px; border-radius: var(--r-tab); font-size: 13px; font-weight: 600; text-align: left; }
  .list button:hover { background: var(--strip); }
  .list em { margin-left: auto; font-size: 12px; font-style: normal; font-weight: 500; color: var(--mute); white-space: nowrap; }
  .dot { width: 10px; height: 10px; flex: none; border-radius: 50%; border: 2.5px solid var(--c); background: #fff; }
  .dot.done { --c: var(--done); } .dot.prog { --c: var(--amber); } .dot.todo { --c: var(--slate); }
</style>

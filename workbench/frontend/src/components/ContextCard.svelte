<script lang="ts">
  import type { GraphModel } from "../lib/model";
  import type { GraphNode, ViewState } from "../lib/types";
  import Icon from "./Icon.svelte";

  let {
    model, view, attached, onattach, onselect, onapprove,
  }: {
    model: GraphModel;
    view: ViewState;
    attached: string[];
    onattach: (key: string) => void;
    onselect: (key: string) => void;
    onapprove?: (change: string) => Promise<unknown>;
  } = $props();

  let approving = $state(false);
  let approveError = $state("");
  async function approve(change: string) {
    if (!onapprove) return;
    approving = true;
    approveError = "";
    try {
      await onapprove(change);
    } catch (err) {
      approveError = err instanceof Error ? err.message : "Approval failed.";
    } finally {
      approving = false;
    }
  }

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
    {#if node}
      <p class="meta">{node.kind === "epic" ? "Change" : node.deliverable_kind === "enabler" ? "Enabler" : "Story"} · <span class="mono">{model.identifier(node)}</span>{#if node.tracker}<span class="mono"> · {node.plan_key}</span>{/if}</p>
    {:else}
      <h2 class="glance">{view.epic ? (model.node(view.epic)?.title ?? "This change") : "The plan at a glance"}</h2>
    {/if}
    <button type="button" class="fold" aria-expanded={open} onclick={() => (open = !open)}>{open ? "Hide" : "Show"}</button>
  </header>

  {#if open}
    {#if node}
      <div class="sel">
        <h2>{node.title}</h2>
        <div class="chips">
          <span class="chip {model.statusClass(node)}"><i></i>{model.statusLabel(node)}</span>
          {#if node.status === "orphaned"}<span class="chip">orphaned: no longer in the plan</span>{/if}
          {#if node.approval}<span class="chip">breakdown {node.approval}</span>{/if}
        </div>

        {#if node.runtime}
          <div class="agent" class:warn={node.runtime.status !== "running"}>
            <b><span class="pulse" aria-hidden="true"></span>{model.badge(node)?.label}</b>
            {#if node.runtime.last_message}<p>{node.runtime.last_message}</p>{/if}
          </div>
        {/if}

        <dl>
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
            <dd>{#if node.tracker.url}<a class="ext-link" href={node.tracker.url} target="_blank" rel="noopener">{node.tracker.identifier} <Icon name="external" size={13} /></a>{:else}{node.tracker.identifier}{/if}</dd>
          {/if}
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
        </dl>
        <div class="acts">
          {#if !attached.includes(node.plan_key)}
            <button type="button" class="attach" onclick={() => onattach(node.plan_key)}>Attach to message</button>
          {/if}
          {#if node.kind === "epic" && node.approval === "draft" && onapprove}
            <button type="button" class="attach approve" data-approve={node.change} disabled={approving} onclick={() => approve(node.change)}>
              {approving ? "Approving…" : "Approve breakdown"}
            </button>
          {/if}
        </div>
        {#if approveError}<p class="err" role="alert">{approveError}</p>{/if}
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
  /* A shadow at the bottom edge shows only while more content sits below it:
     the white cover scrolls with the content and hides it at the end. */
  .context {
    background:
      linear-gradient(rgba(255, 255, 255, 0), #fff 70%) 0 100% / 100% 40px no-repeat local,
      radial-gradient(farthest-side at 50% 100%, rgba(20, 22, 26, 0.14), rgba(20, 22, 26, 0)) 0 100% / 100% 12px no-repeat scroll,
      #fff;
  }
  .context { flex: none; max-height: 60%; overflow-y: auto; padding: var(--s-gutter) var(--s-panel); border-bottom: 1px solid var(--line); display: flex; flex-direction: column; gap: var(--s-md); }
  header { display: flex; justify-content: space-between; align-items: center; gap: var(--s-md); }
  .meta { font-size: 12px; color: var(--mute); min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .meta .mono { font: 500 12px var(--font-mono); }
  .glance { font-size: 15px; font-weight: 600; letter-spacing: -0.005em; }
  .ext-link { display: inline-flex; align-items: center; gap: 4px; }
  .pulse { display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: var(--amber); box-shadow: var(--shadow-pulse); }
  .agent.warn .pulse { background: var(--alert); box-shadow: none; }
  .label { font-size: 11px; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; color: var(--mute); }
  .fold { flex: none; min-height: 32px; padding: 0 8px; margin-right: -8px; font-size: 12px; font-weight: 600; color: var(--mute); }
  @media (max-width: 900px) { .fold { min-height: 44px; min-width: 44px; } }
  .fold:hover { color: var(--ink); }
  h2:not(.glance) { font-size: 26px; font-weight: 700; line-height: 1.12; letter-spacing: -0.02em; text-wrap: balance; }
  .chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
  .chip { display: inline-flex; align-items: center; gap: 6px; height: 24px; padding: 0 9px; border: 1px solid var(--line); border-radius: var(--r-pill); font-size: 12px; font-weight: 600; }
  .chip i { width: 8px; height: 8px; border-radius: 50%; background: var(--c); }
  .chip.done { --c: var(--done); border-color: #b9d3c3; background: var(--done-tint); color: var(--done); }
  .chip.prog { --c: var(--amber); border-color: #ecc77f; background: var(--amber-tint); color: var(--amber-ink); }
  .chip.todo { --c: var(--slate); background: var(--slate-tint); color: var(--slate-ink); }
  .chip.id { font: 500 11.5px var(--font-mono); color: var(--mute); }
  .agent { margin-top: var(--s-md); padding: 12px 14px; border-radius: var(--r-well); background: var(--ink); color: #fff; }
  .agent b { display: flex; align-items: center; gap: 8px; font-size: 14px; }
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
  .acts { display: flex; gap: 8px; flex-wrap: wrap; margin-top: var(--s-md); }
  .approve { background: var(--ink); color: #fff; border-color: var(--ink); }
  .approve:hover:not(:disabled) { background: #000; }
  .err { color: var(--alert); font-size: 12px; margin-top: 6px; }
  .attach { height: 42px; padding: 0 14px; border: 1px solid var(--line); border-radius: var(--r-button); background: #fff; font-weight: 600; }
  .attach:hover { border-color: var(--ink); }
  .lists { display: flex; flex-direction: column; gap: var(--s-md); }
  .list { list-style: none; display: flex; flex-direction: column; gap: 2px; margin-top: 6px; }
  .list button { width: 100%; display: flex; align-items: center; gap: 10px; padding: 4px 6px; margin: 0 -6px; border-radius: var(--r-tab); font-size: 13px; font-weight: 600; text-align: left; }
  .list button:hover { background: var(--strip); }
  .list em { margin-left: auto; font-size: 12px; font-style: normal; font-weight: 500; color: var(--mute); white-space: nowrap; }
  .dot { width: 10px; height: 10px; flex: none; border-radius: 50%; border: 2.5px solid var(--c); background: #fff; }
  .dot.done { --c: var(--done); } .dot.prog { --c: var(--amber); } .dot.todo { --c: var(--slate); }
</style>

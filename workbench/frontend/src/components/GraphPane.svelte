<script lang="ts">
  import type { Snippet } from "svelte";
  import { GEOMETRY, layoutScore } from "../lib/layout";
  import { GraphModel } from "../lib/model";
  import type { MergedGraph, ViewState } from "../lib/types";
  import Card from "./Card.svelte";
  import Icon from "./Icon.svelte";
  import TopBar, { type Crumb } from "./TopBar.svelte";
  import ValidationPanel from "./ValidationPanel.svelte";

  let {
    doc, view, onselect, onopen, onback, ontogglecross, actions, notice, projectName = "",
  }: {
    doc: MergedGraph;
    /** The project's name, shown in the breadcrumb under "Projects". */
    projectName?: string;
    view: ViewState;
    onselect: (key: string | null) => void;
    onopen: (epicKey: string) => void;
    onback: () => void;
    ontogglecross: (show: boolean) => void;
    actions?: Snippet;
    /** A band under the strip for facts about the project as a whole. */
    notice?: Snippet;
  } = $props();

  const g = GEOMETRY;
  const model = $derived(new GraphModel(doc));
  const epic = $derived(view.epic ? model.node(view.epic) : undefined);
  const nodes = $derived(epic ? model.storiesOf(epic.plan_key) : model.epics);
  const unit = $derived(epic ? "stories" : "epics");
  const layout = $derived(
    layoutScore({
      nodes: nodes.map((n) => ({ key: n.plan_key, depth: n.depth })),
      blockers: (k) => model.blockers(k),
      isDone: (k) => model.isDone(model.node(k)) || model.isCancelled(model.node(k)),
      showExternal: !!epic && view.showCross,
    }),
  );
  const selected = $derived(view.selected && layout.pos.has(view.selected) ? view.selected : null);
  const near = $derived(
    new Set(selected ? layout.edges.filter((e) => e.from === selected || e.to === selected).flatMap((e) => [e.from, e.to]) : []),
  );
  const agents = $derived(doc.nodes.filter((n) => n.runtime && n.runtime.status !== "budget_held").length);
  const counts = $derived({
    done: nodes.filter((n) => model.statusClass(n) === "done").length,
    prog: nodes.filter((n) => model.statusClass(n) === "prog").length,
    todo: nodes.filter((n) => model.statusClass(n) === "todo").length,
    cancelled: nodes.filter((n) => model.isCancelled(n)).length,
    nospec: nodes.filter((n) => n.has_spec === false).length,
    drafts: nodes.filter((n) => n.status === "draft").length,
  });
  const dispatched = $derived(doc.sortie.dispatched !== false);
  const liveText = $derived(!doc.sortie.reachable ? "Sortie unreachable" : dispatched ? `Sortie · ${agents} running` : "Sortie · agents not dispatched");
  const crumbs: Crumb[] = $derived([
    { label: "Projects", href: "#/" },
    ...(epic ? [{ label: projectName || "Epics", onclick: onback }, { label: epic.title }] : [{ label: projectName || "Epics" }]),
  ]);
  const letter = (d: number) => String.fromCharCode(65 + d);
  const singular = (u: string) => u.replace(/ies$/, "y").replace(/s$/, "");

  function caption(col: string[]): string {
    const ns = col.map((k) => model.node(k)!);
    if (ns.every((n) => model.isDone(n) || model.isCancelled(n))) return "complete";
    if (ns.some((n) => model.statusClass(n) === "prog" || n.runtime)) return "in flight";
    return "queued";
  }

  function footTop(col: string[]): number {
    return Math.max(...col.map((k) => layout.pos.get(k)!.y)) + g.cardH + 28;
  }

  function selectStub(key: string) {
    const target = model.node(key);
    if (!target) return;
    const parent = model.epicOf(target);
    if (parent && parent.plan_key !== view.epic) onopen(parent.plan_key);
    onselect(key);
  }

  function onkeydown(e: KeyboardEvent) {
    if (e.key !== "Escape") return;
    if (view.selected) onselect(null);
    else if (view.epic) onback();
  }
</script>

<svelte:window {onkeydown} />

<TopBar {crumbs}>
  <span class="live" class:down={!doc.sortie.reachable} class:idle={doc.sortie.reachable && !dispatched}
    title={doc.sortie.reachable && !dispatched ? `${liveText}: Sortie plans and syncs this project but runs agents only for its configured project` : liveText}>
    <span class="pulse" aria-hidden="true"></span>
    <span class="live-text">{liveText}</span>
  </span>
  {#if actions}{@render actions()}{/if}
</TopBar>

<div class="strip">
  <p class="summary">
    <b>{nodes.length} {nodes.length === 1 ? singular(unit) : unit}</b> · {counts.done} done · {counts.prog} in progress ·
    {counts.todo} to do{#if counts.cancelled} · {counts.cancelled} cancelled{/if} · {counts.nospec} without a spec · {counts.drafts} draft
  </p>
  <span class="spacer"></span>
  {#if epic}
    <label class="toggle">
      <input type="checkbox" checked={view.showCross} onchange={(e) => ontogglecross(e.currentTarget.checked)} />
      <span>Show links to other epics</span>
    </label>
  {/if}
  <ul class="legend" aria-label="Legend">
    <li><i class="sw done"></i>Done</li>
    <li><i class="sw prog"></i>In progress</li>
    <li><i class="sw todo"></i>To do</li>
    <li class="rule" aria-hidden="true"></li>
    <li><i class="sw planned"></i>Spec</li>
    <li><i class="sw unplanned"></i>No spec</li>
    <li><i class="sw draft"></i>Draft</li>
    <li><i class="sw orphan"></i>Orphaned</li>
    <li class="rule" aria-hidden="true"></li>
    <li><i class="agent-mark"></i>Agent</li>
  </ul>
</div>

{#if notice}{@render notice()}{/if}
<ValidationPanel errors={doc.validation.errors} has={(k) => model.byKey.has(k)} onselect={selectStub} />

<section class="canvas" aria-label="Dependency graph" data-level={view.epic ?? "project"}>
  {#if nodes.length === 0}
    <div class="empty">
      <b>{epic ? "No stories yet" : "No plan yet"}</b>
      {epic ? "This change has no deliverables. Ask the planning agent to break it down." : "Start a planning session and ask the agent to write the plan."}
    </div>
  {:else}
    <div class="score" class:focused={!!selected} style:width="{layout.width}px" style:height="{layout.height}px">
      {#if layout.frontier > 0}<div class="wash" style:width="{layout.playX}px"></div>{/if}
      <svg width={layout.width} height={layout.height} aria-hidden="true">
        <defs>
          <marker id="arrow" viewBox="0 0 8 8" refX="7.5" refY="4" markerWidth="7" markerHeight="7" orient="auto">
            <path d="M0 1L8 4L0 7z" fill="#14161a" />
          </marker>
        </defs>
        {#each layout.columns as _, d (d)}
          {#if d > 0 && d !== layout.frontier}
            <path d="M{layout.colX(d) - 34} 16V{layout.height}" class="bar" />
          {/if}
        {/each}
        {#if layout.stubs.length}<path d="M{layout.colX(0) - 34} 16V{layout.height}" class="bar ext-bar" />{/if}
        <path d="M{layout.finX} 60V{layout.height - 60}" class="fin" />
        <path d="M{layout.finX + 7} 60V{layout.height - 60}" class="fin thick" />
        {#each layout.edges as e (e.from + ">" + e.to)}
          {@const hot = selected !== null && (e.from === selected || e.to === selected)}
          <path
            d={e.path}
            class="edge"
            class:ext={e.external}
            class:hot
            class:faded={selected !== null && !hot}
            marker-end="url(#arrow)"
            data-edge="{e.from}>{e.to}"
          />
        {/each}
      </svg>

      {#each layout.columns as col, d (d)}
        <div class="measure-head" style:left="{layout.colX(d) - 16}px">
          <div class="reh">{letter(d)}</div>
          <p>{d === 0 ? "Ready" : `Depth ${d}`}<small>{col.length} {col.length === 1 ? singular(unit) : unit}</small></p>
        </div>
        {#if col.length}
          <div class="measure-foot" style:left="{layout.colX(d)}px" style:top="{footTop(col)}px">
            <em>{caption(col)}</em>{col.filter((k) => model.isDone(model.node(k))).length} of {col.length} done
          </div>
        {/if}
      {/each}
      <div class="measure-head" style:left="{layout.finX + 24}px">
        <div class="reh">{letter(layout.columns.length)}</div>
        <p>Fine<small>{epic ? "Change complete" : "Plan complete"}</small></p>
      </div>
      {#if layout.stubs.length}
        <div class="measure-head" style:left="{g.left - 16}px">
          <p>From other epics<small>{layout.stubs.length} linked {layout.stubs.length === 1 ? "story" : "stories"}</small></p>
        </div>
      {/if}

      <div class="playhead" style:left="{layout.playX}px"></div>
      <div class="playhead-label" class:edge-left={layout.playX < 70} style:left="{layout.playX}px">now · {agents} {agents === 1 ? "agent" : "agents"}</div>

      {#each layout.stubs as stub (stub.key)}
        {@const target = model.node(stub.key)}
        <button
          type="button"
          class="ext {target ? model.statusClass(target) : 'todo'}"
          data-stub={stub.key}
          style:left="{stub.x}px"
          style:top="{stub.y}px"
          title="{stub.key}{target ? ` · ${target.title}` : ''}"
          onclick={() => selectStub(stub.key)}
        ><b>{stub.key}</b>{target?.title ?? ""}</button>
      {/each}

      {#each nodes as n (n.plan_key)}
        {@const p = layout.pos.get(n.plan_key)!}
        <Card
          node={n}
          {model}
          x={p.x}
          y={p.y}
          selected={selected === n.plan_key}
          near={near.has(n.plan_key)}
          onselect={(k) => onselect(selected === k ? null : k)}
          {onopen}
        />
        {#if selected === n.plan_key && n.kind === "epic"}
          <button
            type="button"
            class="open-tab"
            style:left="{p.x + g.cardW - 132}px"
            style:top="{p.y + g.cardH - 1}px"
            onclick={() => onopen(n.plan_key)}
          >Open change <Icon name="arrow" /></button>
        {/if}
      {/each}
    </div>
  {/if}
</section>

<style>
  .live { display: flex; align-items: center; gap: 8px; font-size: 12px; color: #d1d1d6; white-space: nowrap; }
  .live.down { color: var(--ink-mute); }
  .live.down .pulse, .live.idle .pulse { background: var(--ink-mute); box-shadow: none; }
  .live.idle { color: var(--ink-mute); }
  /* Under a narrow graph pane the status keeps its dot; the words move to the tooltip. */
  @container (max-width: 600px) { .live-text { display: none; } }
  .pulse { width: 8px; height: 8px; border-radius: 50%; background: var(--amber); box-shadow: var(--shadow-pulse); }

  .strip { flex: none; min-height: 48px; display: flex; align-items: center; flex-wrap: wrap; gap: 8px 20px; padding: 8px var(--s-gutter); border-bottom: 1px solid var(--line); background: var(--strip); font-size: 12px; color: var(--mute); }
  .summary b { color: var(--ink); font-weight: 700; font-size: 13px; }
  .legend { display: flex; align-items: center; flex-wrap: wrap; gap: 6px 14px; list-style: none; }
  .legend li { display: flex; align-items: center; gap: 7px; }
  .legend .rule { width: 1px; height: 18px; background: var(--line); }
  .sw { display: inline-block; width: 16px; height: 11px; border: 1.5px solid; border-radius: var(--r-swatch); }
  .sw.done { border-color: var(--done); background: var(--done-tint); }
  .sw.prog { border-color: var(--amber); background: var(--amber-tint); }
  .sw.todo { border-color: var(--slate); background: var(--slate-tint); }
  .sw.planned { border-color: var(--ink); background: #ecece6; }
  .sw.unplanned { border-color: var(--ink); background: repeating-linear-gradient(135deg, #8a8f98 0 1px, #fff 1px 4px); }
  .sw.draft { border-color: var(--ink); border-style: dashed; background: #fff; }
  .sw.orphan { border-color: var(--slate); background: var(--slate-tint); opacity: 0.8; outline: 1px dashed var(--mute); outline-offset: 1px; }
  .agent-mark { width: 14px; height: 14px; border-radius: 3px; background: radial-gradient(circle, var(--amber) 0 2.5px, var(--ink) 3px); }
  .toggle { display: flex; align-items: center; gap: 7px; color: var(--ink); font-weight: 500; cursor: pointer; }
  .toggle input { accent-color: var(--ink); }

  .canvas { position: relative; flex: 1; min-height: 0; overflow: auto; scrollbar-color: #b9bab3 var(--hair); }
  .score { position: relative; min-width: 100%; min-height: 100%; }
  .score svg { position: absolute; left: 0; top: 0; pointer-events: none; overflow: hidden; }
  .bar { stroke: var(--ink-rule); stroke-width: 1; opacity: 0.5; shape-rendering: crispEdges; fill: none; }
  .ext-bar { stroke-dasharray: 3 4; }
  .fin { stroke: var(--ink-rule); stroke-width: 1; shape-rendering: crispEdges; }
  .fin.thick { stroke-width: 5; }
  .edge { fill: none; stroke: var(--ink-rule); stroke-width: 1; }
  .edge.ext { stroke-dasharray: 4 3; opacity: 0.7; }
  .edge.hot { stroke-width: 1.5; }
  .edge.faded { opacity: 0.25; }
  .measure-head { position: absolute; top: 22px; display: flex; gap: 12px; align-items: flex-start; }
  .reh { width: 30px; height: 30px; flex: none; display: grid; place-items: center; border: 1.5px solid var(--ink-rule); background: var(--paper); font: 700 17px/1 var(--font-serif); }
  .measure-head p { font: italic 400 16px/1.1 var(--font-serif); }
  .measure-head small { display: block; margin-top: 4px; font: 600 11px var(--font-sans); letter-spacing: 0.05em; text-transform: uppercase; color: var(--mute); font-style: normal; }
  .measure-foot { position: absolute; font-size: 11.5px; color: var(--mute); }
  .measure-foot em { display: block; margin-bottom: 2px; font: italic 400 15px var(--font-serif); color: var(--ink); }
  .playhead { position: absolute; top: 76px; bottom: 0; width: 1px; background: var(--ink-rule); }
  .playhead-label { position: absolute; top: 64px; transform: translateX(-50%); padding: 3px 9px; border-radius: var(--r-tag); background: var(--ink-rule); color: #fff; font-size: 11px; font-weight: 600; white-space: nowrap; }
  .playhead-label.edge-left { transform: translateX(-4px); }
  .wash { position: absolute; top: 0; bottom: 0; left: 0; background: rgba(47, 111, 78, 0.04); }
  .ext { position: absolute; display: flex; align-items: center; gap: 6px; height: 24px; max-width: 212px; padding: 0 9px; border: 1px dashed var(--slate); border-radius: 12px; background: var(--paper); font-size: 11px; color: var(--mute); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .ext b { font: 500 10.5px var(--font-mono); color: var(--ink); }
  .ext.done { border-color: var(--done); }
  .open-tab { position: absolute; display: flex; align-items: center; gap: 6px; height: 28px; padding: 0 12px; border-radius: 0 0 var(--r-card) var(--r-card); background: var(--ink); color: #fff; font-size: 12px; font-weight: 600; white-space: nowrap; }
  .open-tab:hover { background: #000; }
  .empty { position: absolute; left: 40px; top: 120px; max-width: 40ch; color: var(--mute); }
  .empty b { display: block; margin-bottom: 4px; font: italic 400 20px var(--font-serif); color: var(--ink); }
</style>

<script lang="ts">
  import { graphHref } from "../lib/router";
  import { mapShare, progressLines, REASON_TEXT, visualSpans, type HomeDoc } from "../lib/home";

  let { home, slug, marks }: { home: HomeDoc; slug: string; marks: Set<string> } = $props();

  // The staff's width in pixels: how many crosses fit in a stretch without overlapping.
  let width = $state(1360);
  const CROSS_PX = 17;

  const spans = $derived(home.timeline?.spans ?? []);
  // Every span is at least wide enough for its tick's label.
  const LABEL_PX = 124;
  const visual = $derived(visualSpans(spans, Math.max(0.1, LABEL_PX / Math.max(width, 1))));
  const here = $derived(home.timeline ? mapShare(home.timeline.here, spans, visual) : 0);
  const byId = $derived(new Map(home.milestones.map((m) => [m.id, m])));
  const storiesKnown = $derived(home.story_progress !== "unknown");
  const pct = (x: number) => `${(x * 100).toFixed(3)}%`;

  // A screen too narrow for the whole timeline opens it at "we are here".
  let wrap: HTMLDivElement | undefined = $state();
  let centred = false;
  $effect(() => {
    if (!wrap || centred || !home.timeline) return;
    if (wrap.scrollWidth > wrap.clientWidth) wrap.scrollLeft = Math.max(0, here * wrap.scrollWidth - wrap.clientWidth / 2);
    centred = true;
  });

  /** The rest of a title after its short name: "VM-COMPLETE" from "M1: vm-complete". */
  function subtitle(title: string, short: string): string {
    return title.startsWith(short) ? title.slice(short.length).replace(/^[:\s·-]+/, "") : "";
  }

  /**
   * Each blocker's x: spread over the part of its milestone still ahead of
   * "we are here", most urgent first. A stretch shows as many crosses as fit;
   * the rest are counted beside the last one.
   */
  const marksOnStaff = $derived.by(() => {
    const crosses: { key: string; label: string; reason: string; x: number; milestone: string; rank: number | null }[] = [];
    const more: { x: number; count: number; milestone: string }[] = [];
    spans.forEach((s, i) => {
      const v = visual[i];
      if (!v || !s.blockers.length) return;
      const pad = 12 / width;
      const from = Math.max(v.x0, here) + pad;
      const to = Math.max(from, v.x1 - pad);
      const room = Math.max(1, Math.floor(((to - from) * width) / CROSS_PX) + 1);
      const ordered = [...s.blockers].sort((a, b) => (a.rank ?? 1e9) - (b.rank ?? 1e9));
      const shown = ordered.length > room ? ordered.slice(0, Math.max(1, room - 2)) : ordered;
      const slots = ordered.length > room ? shown.length + 2 : shown.length;
      const step = slots > 1 ? Math.min((to - from) / (slots - 1), (2.2 * CROSS_PX) / width) : 0;
      shown.forEach((b, j) => crosses.push({ ...b, x: from + j * step, milestone: s.id }));
      if (shown.length < ordered.length) more.push({ x: from + shown.length * step, count: ordered.length - shown.length, milestone: s.id });
    });
    return { crosses, more };
  });
</script>

<div class="staff-wrap" bind:this={wrap}>
  <div class="staff" bind:clientWidth={width} role="group" aria-label="Timeline: the milestones, where the work is, and the blockers that need a person">
    <div class="lane" aria-hidden="true"></div>
    <div class="bar played" style:left="0" style:width={pct(here)} aria-hidden="true"></div>
    <div class="bar ahead" style:left={pct(here)} style:width={pct(1 - here)} aria-hidden="true"></div>

    {#each visual as v, i (v.id)}
      {@const m = byId.get(v.id)!}
      <div class="m" class:goal={m.goal} class:next={m.next} style:left={pct(v.x0)} style:width={pct(v.x1 - v.x0)} data-milestone={m.id}>
        <a class="lab" href={graphHref(slug, { mark: m.id })} title="{m.title}: open the graph with its changes marked">
          <b>{m.short}</b>
          <span>{subtitle(m.title, m.short)}{m.goal ? " · goal" : ""}</span>
        </a>
        <span class="cnt">
          {#if m.done}<span>done</span>{:else}
            {#each progressLines(m, storiesKnown) as line (line)}<span>{line}</span>{/each}
            {#if m.progress.stories.total && home.story_progress === "last_known"}<span class="stale">stories last known</span>{/if}
          {/if}
        </span>
      </div>
    {/each}

    <div class="here" style:left={pct(here)} class:edge-left={here < 0.06} class:edge-right={here > 0.94}>
      <span class="flag">we are here</span><span class="stem" aria-hidden="true"></span>
    </div>

    {#each marksOnStaff.crosses as c (c.key)}
      <a class="x" class:moved={marks.has(c.key)} style:left={pct(c.x)} href={graphHref(slug, c.key.includes("/") && !c.key.includes("#") ? { epic: c.key.split("/")[0], selected: c.key } : { epic: c.key.split("#")[0] })}
        title="{c.key}: {REASON_TEXT[c.reason as keyof typeof REASON_TEXT]}" aria-label="Blocker in {byId.get(c.milestone)?.short}: {c.key}, {REASON_TEXT[c.reason as keyof typeof REASON_TEXT]}"
        data-blocker={c.key}><span class="tip" role="tooltip">{c.key} · {REASON_TEXT[c.reason as keyof typeof REASON_TEXT]}</span></a>
    {/each}
    {#each marksOnStaff.more as m (m.milestone)}
      <span class="more" style:left={pct(m.x)} data-more={m.milestone}>+{m.count}</span>
    {/each}
  </div>
</div>

<style>
  /* Wide enough for every label; a narrow screen scrolls the timeline, not the page. */
  .staff-wrap { overflow-x: auto; overflow-y: visible; margin: 0 calc(-1 * var(--home-x)); padding: 0 var(--home-x); scrollbar-color: #b9bab3 var(--hair); }
  .staff { position: relative; min-width: 640px; height: 166px; }
  .lane { position: absolute; left: 0; right: 0; top: 63px; height: 1px; background: var(--hair); }
  .bar { position: absolute; top: 58px; height: 10px; border-radius: 2px; }
  .bar.played { background: var(--ink-rule); }
  .bar.ahead { background: repeating-linear-gradient(90deg, var(--line) 0 10px, transparent 10px 16px); }

  .m { position: absolute; top: 0; bottom: 0; border-left: 1px solid var(--ink-rule); pointer-events: none; }
  .m a { pointer-events: auto; color: inherit; text-decoration: none; }
  .m.goal { border-left: 5px double var(--ink-rule); }
  /* A label stays inside its own span: the subtitle wraps rather than running into the next tick. */
  .lab { position: absolute; top: -6px; left: 10px; right: 8px; }
  .lab b { display: block; font: italic 400 26px/1 var(--font-serif); }
  .lab span { display: block; overflow: hidden; text-overflow: ellipsis; margin-top: 2px; font-size: 11px; font-weight: 700; line-height: 1.25; letter-spacing: 0.05em; text-transform: uppercase; color: var(--mute); }
  .m.next .lab span { color: var(--ink); }
  .cnt { position: absolute; top: 98px; left: 10px; right: 6px; display: flex; flex-direction: column; font-size: 11.5px; line-height: 1.5; color: var(--mute); font-variant-numeric: tabular-nums; }
  .cnt span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .cnt .stale { font-style: italic; }
  .lab:hover b, .lab:focus-visible b { text-decoration: underline; text-underline-offset: 4px; text-decoration-thickness: 1px; }

  .here { position: absolute; top: 34px; transform: translateX(-50%); display: flex; flex-direction: column; align-items: center; pointer-events: none; }
  .here.edge-left { transform: translateX(-4px); align-items: flex-start; }
  .here.edge-right { transform: translateX(calc(-100% + 4px)); align-items: flex-end; }
  .flag { padding: 3px 8px; border-radius: var(--r-tag); background: var(--ink-rule); color: #fff; font-size: 11px; font-weight: 700; white-space: nowrap; }
  .stem { width: 2px; height: 20px; background: var(--ink-rule); }
  .here.edge-left .stem { margin-left: 3px; }
  .here.edge-right .stem { margin-right: 3px; }

  /* A blocker that needs a person: a cross drawn from two bars, not a glyph. */
  .x { position: absolute; top: 76px; width: 18px; height: 18px; margin-left: -9px; border-radius: 3px; }
  .x::before, .x::after { content: ""; position: absolute; left: 7.75px; top: 2px; width: 2.5px; height: 14px; border-radius: 1px; background: var(--alert); transform: rotate(45deg); }
  .x::after { transform: rotate(-45deg); }
  .x .tip { position: absolute; z-index: 3; top: 22px; left: 50%; transform: translateX(-50%); display: none; padding: 4px 8px; border-radius: var(--r-tag); background: var(--ink); color: #fff; font: 500 11px var(--font-mono); white-space: nowrap; }
  .x:hover .tip, .x:focus-visible .tip { display: block; }
  .more { position: absolute; top: 77px; margin-left: -4px; font-size: 11px; font-weight: 700; color: #8f241d; white-space: nowrap; }
  .x.moved { animation: moved 1.4s ease-out 3; }
  @keyframes moved { from { box-shadow: 0 0 0 0 rgba(201, 138, 26, 0.55); } to { box-shadow: 0 0 0 10px rgba(201, 138, 26, 0); } }
</style>

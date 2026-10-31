---
name: Huly DAG
description: A dependency graph of Huly tickets, read left to right like a score, with Sortie's live agents marked on it.
colors:
  ink: "#1d1d1f"
  ink-rule: "#14161a"
  ink-raised: "#2a2a2d"
  ink-edge: "#3a3a3d"
  ink-mute: "#a1a1a6"
  paper: "#fbfbf8"
  strip: "#f4f4f2"
  panel: "#ffffff"
  line: "#dcdcd7"
  hair: "#e6e6e0"
  mute: "#5d626b"
  done: "#2f6f4e"
  done-tint: "#eef4f0"
  amber: "#c98a1a"
  amber-ink: "#8a5a06"
  amber-tint: "#fbf4e5"
  slate: "#8a8f98"
  slate-ink: "#6b7079"
  slate-tint: "#f1f2f3"
  alert: "#c4382f"
typography:
  display:
    fontFamily: "Instrument Sans, Helvetica Neue, Helvetica, Arial, sans-serif"
    fontSize: "26px"
    fontWeight: 700
    lineHeight: 1.12
    letterSpacing: "-0.02em"
  rehearsal:
    fontFamily: "Bodoni Moda, Georgia, serif"
    fontSize: "17px"
    fontWeight: 700
    lineHeight: 1
  measure:
    fontFamily: "Bodoni Moda, Georgia, serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.1
  title:
    fontFamily: "Instrument Sans, Helvetica Neue, Helvetica, Arial, sans-serif"
    fontSize: "15px"
    fontWeight: 600
    lineHeight: 1.25
    letterSpacing: "-0.005em"
  numeral:
    fontFamily: "Instrument Sans, Helvetica Neue, Helvetica, Arial, sans-serif"
    fontSize: "22px"
    fontWeight: 700
    letterSpacing: "-0.02em"
    fontFeature: "'tnum' 1"
  body:
    fontFamily: "Instrument Sans, Helvetica Neue, Helvetica, Arial, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.45
  label:
    fontFamily: "Instrument Sans, Helvetica Neue, Helvetica, Arial, sans-serif"
    fontSize: "11px"
    fontWeight: 700
    letterSpacing: "0.06em"
  status:
    fontFamily: "Instrument Sans, Helvetica Neue, Helvetica, Arial, sans-serif"
    fontSize: "10px"
    fontWeight: 700
    letterSpacing: "0.05em"
  mono:
    fontFamily: "JetBrains Mono, ui-monospace, Menlo, monospace"
    fontSize: "10.5px"
    fontWeight: 500
rounded:
  swatch: "2px"
  tag: "3px"
  tab: "5px"
  card: "6px"
  button: "8px"
  well: "10px"
  pill: "999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  card-x: "14px"
  gutter: "20px"
  section: "22px"
  panel: "24px"
  row-gap: "44px"
  measure: "300px"
components:
  top-bar:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.panel}"
    height: "56px"
    padding: "0 20px"
  project-selector:
    backgroundColor: "{colors.ink-raised}"
    textColor: "{colors.panel}"
    rounded: "{rounded.card}"
    height: "32px"
    padding: "0 12px"
  level-tab:
    textColor: "#b8b8bd"
    typography: "{typography.body}"
    rounded: "{rounded.tab}"
    padding: "5px 14px"
  level-tab-active:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    rounded: "{rounded.tab}"
    padding: "5px 14px"
  summary-strip:
    backgroundColor: "{colors.strip}"
    textColor: "{colors.mute}"
    height: "48px"
    padding: "0 20px"
  rehearsal-letter:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink-rule}"
    typography: "{typography.rehearsal}"
    size: "30px"
  card-done:
    backgroundColor: "{colors.done-tint}"
    textColor: "{colors.ink}"
    rounded: "{rounded.card}"
    padding: "11px 14px 10px"
    width: "232px"
    height: "112px"
  card-in-progress:
    backgroundColor: "{colors.amber-tint}"
    textColor: "{colors.ink}"
    rounded: "{rounded.card}"
    padding: "11px 14px 10px"
    width: "232px"
    height: "112px"
  card-todo:
    backgroundColor: "{colors.slate-tint}"
    textColor: "{colors.ink}"
    rounded: "{rounded.card}"
    padding: "11px 14px 10px"
    width: "232px"
    height: "112px"
  spec-tag:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    rounded: "{rounded.tag}"
    padding: "1px 6px"
  agent-badge:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.panel}"
    rounded: "{rounded.pill}"
    padding: "3px 9px 3px 7px"
  agent-badge-retry:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    rounded: "{rounded.pill}"
  agent-badge-budget:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.alert}"
    rounded: "{rounded.pill}"
  playhead-label:
    backgroundColor: "{colors.ink-rule}"
    textColor: "{colors.panel}"
    rounded: "{rounded.tag}"
    padding: "3px 9px"
  status-chip-done:
    backgroundColor: "{colors.done-tint}"
    textColor: "{colors.done}"
    rounded: "{rounded.pill}"
    height: "26px"
    padding: "0 10px"
  status-chip-in-progress:
    backgroundColor: "{colors.amber-tint}"
    textColor: "{colors.amber-ink}"
    rounded: "{rounded.pill}"
    height: "26px"
    padding: "0 10px"
  status-chip-todo:
    backgroundColor: "{colors.slate-tint}"
    textColor: "{colors.slate-ink}"
    rounded: "{rounded.pill}"
    height: "26px"
    padding: "0 10px"
  agent-well:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.panel}"
    rounded: "{rounded.well}"
    padding: "14px 16px"
  agent-well-warn:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    rounded: "{rounded.well}"
    padding: "14px 16px"
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.panel}"
    rounded: "{rounded.button}"
    height: "42px"
  button-primary-hover:
    backgroundColor: "#000000"
  button-ghost:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    rounded: "{rounded.button}"
    height: "42px"
  side-panel:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    width: "360px"
    padding: "24px"
---

# Design System: Huly DAG

## Overview

**Creative North Star: "The Conductor's Score"**

The project is a piece of music that is being played. The canvas is a printed score on paper: each dependency depth is one measure, bar lines are ink hairlines, and a boxed Bodoni rehearsal letter (A, B, C…) heads each measure. The last measure ends in a double final bar named "Fine". A single ink playhead marks "now", and the measures behind it are washed a faint green because they are already played. A reader finds what is ready by reading left to right, the same way an orchestra reads a part.

Around the score sits the station shell of a transit diagram: a dark ink top bar for identity, level and live system status; a light strip for the summary and the legend; and a white side panel that reads out the selected ticket. The shell is quiet, sans-serif and functional. The score carries the character. The density is that of a working tool, not a poster: 13px body text, 232×112px cards, and every pixel of colour encodes a state.

Status is carried by the border, not the fill. Planning is carried by the fill: a solid tint is a planned ticket, a diagonal hatch is a ticket with no spec yet. Lines are always ink. The view rejects the pannable node canvas with coloured bezier spaghetti and a minimap.

**Key Characteristics:**
- Paper score canvas inside an ink-and-white transit shell.
- Columns are dependency depth; x position is the only spatial encoding.
- Boxy status-bordered ticket cards; tint means planned, hatch means unplanned.
- One ink line weight for every edge, bar line and the playhead.
- Bodoni Moda only for the notation layer; Instrument Sans for everything a user operates; JetBrains Mono for identifiers.
- Amber is the colour of motion: work in progress, agents running, keyboard focus.

## Colors

A near-monochrome ink-and-paper system with three muted status voices and one alarm red.

### Primary
- **Shell Ink** (`ink`): the top bar, primary buttons, the running-agent badge and well, and all body text. It is the frame of the whole tool.
- **Rule Ink** (`ink-rule`): a slightly cooler, darker ink reserved for the drawn layer of the score — edges, arrowheads, bar lines, the final bar, the playhead and its label, and the rehearsal-letter box.

### Secondary
- **Signal Amber** (`amber`): the in-progress card border, the progress fill on in-progress cards, the live pulse dot, the focus outline, and the selection halo. It means "something is moving".
- **Amber Ink** (`amber-ink`): in-progress text on amber tint (status chips). Use this, not a lighter amber, wherever amber has to be read as text.
- **Amber Tint** (`amber-tint`): the solid fill of a planned in-progress card and chip.

### Tertiary
- **Ledger Green** (`done`): the done border, done status text, the progress segments of finished stories, and (at 4% alpha) the "played" wash behind the playhead.
- **Green Tint** (`done-tint`): the fill of a planned done card and chip.
- **Slate** (`slate`): the todo border and the dashed border of external-story stubs.
- **Slate Ink** (`slate-ink`) and **Slate Tint** (`slate-tint`): todo text and the planned todo fill.
- **Alarm Red** (`alert`): only for a ticket held by budget — its badge text, badge border, and the border of its agent well. It never marks an ordinary status.

### Neutral
- **Score Paper** (`paper`): the canvas ground, the rehearsal-box fill, the stub fill.
- **Strip Grey** (`strip`): the summary-and-legend strip and the hover fill of panel list rows.
- **Panel White** (`panel`): the side panel, tags, and the active level tab.
- **Rule Line** (`line`): structural 1px borders — strip bottom, panel left edge, chips, ghost buttons.
- **Hairline** (`hair`): the scrollbar track and the faintest dividers.
- **Muted Text** (`mute`): secondary text — counts, captions, labels, identifiers.
- **Raised Ink** (`ink-raised`), **Ink Edge** (`ink-edge`), **Ink Mute** (`ink-mute`): surfaces, borders and secondary text that sit on the ink top bar.

### Named Rules
**The Border Speaks Status Rule.** A ticket's status lives in its 1.5px border and the matching pale tint. Never fill a card with a saturated status colour; never encode status with anything but border, tint, and the status label.

**The One Ink Rule.** Every line drawn on the score is Rule Ink. Edges are never coloured by status; emphasis comes from weight (1px → 1.5px) and from fading the rest to 25% opacity.

**The Amber Means Motion Rule.** Amber marks work in flight, live agents and focus. It is never decoration and never a brand accent.

## Typography

**Display Font:** Bodoni Moda (with Georgia, serif) — notation layer only
**Body Font:** Instrument Sans (with Helvetica Neue, Helvetica, Arial, sans-serif)
**Label/Mono Font:** JetBrains Mono (with ui-monospace, Menlo, monospace)

**Character:** A high-contrast didone engraves the score's markings, as on printed sheet music; a plain, slightly warm grotesque runs the tool; a mono sets the machine names.

### Hierarchy
- **Display** (Instrument Sans 700, 26px, 1.12, −0.02em, balanced wrap): the selected item's title at the top of the side panel. One per screen.
- **Rehearsal** (Bodoni Moda 700, 17px, 1): the letter inside the 30px rehearsal box.
- **Measure** (Bodoni Moda italic 400, 16px, 1.1): the measure name beside the rehearsal box ("Ready", "Depth 2", "Fine"). The same italic at 15px sets the measure caption under each column ("complete", "in flight", "queued"), and at 20px the empty-state heading.
- **Title** (Instrument Sans 600, 15px, 1.25, −0.005em): the ticket title on a card.
- **Numeral** (Instrument Sans 700, 22px, tabular figures): counts that a user compares, such as "5 / 8 done" in the panel.
- **Body** (Instrument Sans 400, 13px, 1.45): base text, the summary, panel list rows (at 600).
- **Label** (Instrument Sans 600–700, 11px, 0.05–0.06em, uppercase): panel section headings ("Ready to start", "Depends on") and the unit count under each measure name.
- **Status** (Instrument Sans 700, 10px, 0.05em, uppercase): the status word on a card, after a 6px dot in the status colour.
- **Mono** (JetBrains Mono 500, 10.5–12px): ticket identifiers, the project key, OpenSpec references, and agent log lines.

### Named Rules
**The Notation Layer Rule.** Bodoni Moda appears only on the score as notation: rehearsal letters, measure names, measure captions, and the empty state. It never appears in the shell, on cards, or in the side panel.

**The Mono Is Identity Rule.** JetBrains Mono is for identifiers and machine output only (LED-12, openspec:…, an agent's last message). Never use it for prose or for numbers a user compares.

## Layout

The score is a fixed-geometry grid, not a free canvas. Each dependency depth is one 300px measure; a card is 232×112px and sits 34px right of the bar line that opens its measure; cards in a column stack on a 156px pitch (card height + 44px). A card's column is the length of the longest chain of open dependencies before it, so x position means readiness. Vertical position carries no meaning: a card is placed at the average height of its parents to keep edges short. The score scrolls horizontally inside the canvas; it is never zoomed or panned freely.

Measure heads sit 22px from the top of the score; cards start at 96px. A caption under each column reports "N of M done". When a drill-down has stories from other epics, a 220px lane of dashed stubs opens on the left, set off by a dashed bar line.

In the workbench the page is two panes: the graph pane takes 60% of the width and holds the top bar, the strip, and the canvas; the chat pane takes 40% and replaces the prototype's 360px side panel. Below 1200px the panes stack, graph first. In the prototype the page was a column: a 56px top bar, a 48px strip, then a row of the flexible canvas and a 360px side panel. Shell gutters are 20px; the side panel has 24px padding and 22px between groups. Below 900px the row stacks: the canvas takes 62vh, the panel follows below it at full width, the strip scrolls horizontally, and the top bar drops the logo word, the project key and the sync note.

### Named Rules
**The Depth Is Distance Rule.** Horizontal position encodes dependency depth and nothing else. Never place a card by priority, date or owner.

## Elevation & Depth

The system is flat. Surfaces are separated by tone (ink bar, grey strip, paper canvas, white panel) and by 1px rules, never by resting shadows. Shadows appear only as a response to state on a card: a soft drop on hover, and a 4px amber halo plus drop when selected. When an item is selected, every card not connected to it fades to 45% opacity and unrelated edges to 25%; that dimming, not a shadow, creates the focus depth.

### Shadow Vocabulary
- **Card lift** (`box-shadow: 0 8px 20px -12px rgba(20,22,26,.4)`): card hover only.
- **Selection halo** (`box-shadow: 0 0 0 4px rgba(201,138,26,.18), 0 10px 24px -12px rgba(20,22,26,.4)`): the selected card.
- **Pulse ring** (`box-shadow: 0 0 0 3px rgba(201,138,26,.25)`): the 8px live-agent dot.

### Named Rules
**The Flat Score Rule.** Nothing on the score casts a shadow at rest. Depth is tone, rules and dimming.

## Shapes

Boxy and engraved. Ticket cards are near-rectangles with a gently softened corner (6px) and a 1.5px border; the rehearsal box is a true square with no radius and a 1.5px ink border, like a printed rehearsal mark. Small inline marks stay nearly square (tags 3px, legend swatches 2px). Pills (fully rounded) are reserved for live and status signals that float over or beside a ticket: agent badges, status chips, and the dashed stubs of stories from other epics. Buttons and the agent well are slightly rounder (8px and 10px) because they belong to the shell, not the score.

Line language: solid 1.5px for a card border, solid 1px for structure, dashed for anything provisional or external (a "No spec" tag, an external-story stub, its edges, the bar line of the external lane). The final bar is a 1px line plus a 5px line, 7px apart.

### Named Rules
**The Hatch Means Unplanned Rule.** A 135° hatch (1px line, 7px pitch, in the status hue at about 25% alpha over white) marks a ticket with no OpenSpec change; a solid tint marks a planned one. The hatch is never decorative. Text on a hatched card sits on a narrow white backing so it stays legible.

## Components

### Buttons
Shell-weight and decisive; one primary action per panel.
- **Shape:** gently rounded (8px), 42px tall, full panel width, pinned to the bottom of the side panel.
- **Primary:** Shell Ink fill, white 700 14px text ("Open 8 stories"). Hover deepens to pure black.
- **Ghost:** white fill, Shell Ink text, 1px Rule Line border; for secondary exits ("Open in Huly", "All epics").
- **Focus:** the global 2px Signal Amber outline at 2px offset.

### Level Tabs (top bar)
- **Style:** a Raised Ink track (7px radius, 3px inset) holding 600 13px tabs (5px radius, 5px 14px padding) in a light grey.
- **Active:** white fill, Shell Ink text, `aria-current="page"`. The drill-down reads "Epics › Epic name"; "Epics" becomes a button back to the project.

### Ticket Card (signature)
The single unit of the score: a 232×112px button.
- **Border and fill:** 1.5px status border with the matching pale tint (planned) or the status-hued hatch (unplanned). Gently rounded (6px). Internal padding 11px 14px 10px.
- **Row 1:** mono identifier (muted) left; uppercase status word with a 6px status dot right.
- **Title:** 600 15px, up to two lines.
- **Progress:** a 3px rule in 8% ink, filled in the status colour (epics: share of done stories).
- **Row 3:** muted meta ("5/8 stories", "waiting on 2", "ready") left; a spec tag right — a white 3px-radius tag reading "OpenSpec", or a dashed muted "No spec" tag.
- **States:** hover adds the card lift; selection adds the amber halo and sets `aria-pressed`; unrelated cards fade to 45% while one is selected. Transitions are 0.2s ease-out on shadow and opacity, and switch off under reduced motion. Double-clicking an epic opens its stories.

### Agent Badge
- **Style:** a pill that straddles the card's top edge, 11px above it, 10px from the right; 600 10.5px text after a 6px dot.
- **Running:** Shell Ink fill, white text, amber dot ("1 agent running").
- **Retrying:** white fill, ink text, amber border.
- **Budget held:** white fill, Alarm Red text, border and dot.

### Rehearsal Mark and Measure Head (signature)
A 30px square, 1.5px Rule Ink border, paper fill, Bodoni 700 letter; beside it the italic measure name and an uppercase unit count ("3 epics"). The last head is "Fine" with "Project complete" or "Epic complete".

### Playhead
A 1px Rule Ink vertical line that replaces the bar line at the first column that is not fully done, topped by a small ink label ("now · 3 agents", 600 11px white, 3px radius). Everything left of it carries the 4% green "played" wash.

### Edges
1px Rule Ink, from the right edge of a dependency to the left edge of its dependent, with a small filled arrowhead. A straight line when the two cards share a row, otherwise a horizontal S-curve whose control points sit at the midpoint. Edges to the selected card thicken to 1.5px; others fall to 25%. Edges from other epics are dashed (4 3) at 70%.

### Chips
- **Status chip:** 26px pill, 1px border, 600 12px text after an 8px dot; done uses Ledger Green on Green Tint, in progress Amber Ink on Amber Tint, todo Slate Ink on Slate Tint.
- **Neutral chip:** the same pill with a Rule Line border and ink text, for facts such as "2 dependencies" or the parent epic.

### Side Panel
White, 360px, 24px padding, 22px between groups, separated from the canvas by a 1px Rule Line. Order: a muted metadata line (item type and mono identifier), the Display title, chips, the spec row, a 1px divider, then labelled lists ("Ready to start", "Depends on", "Unblocks", "Needs a spec"). List rows are full-width buttons: a 10px ring dot in the status colour (dashed when unplanned), a 600 13px title, and a muted right-aligned fact; hover fills Strip Grey.

### Agent Well
A 10px-radius block in the panel that reports Sortie's live state for a story. Running: Shell Ink fill, white text, pulse dot, mono log line. Retry or budget: white fill, ink text, 1px Alarm Red border, muted log line.

### Legend
In the strip: 16×11px swatches (1.5px border, 2px radius) for each status and for planned (tint) versus unplanned (hatch), separated by 1px × 18px rules, followed by the agent mark. Every visual encoding on the score must have a legend entry.

## Do's and Don'ts

### Do:
- **Do** encode ticket status with the 1.5px border, its pale tint and the status word — Ledger Green done, Signal Amber in progress, Slate todo.
- **Do** mark an unplanned ticket with the 135° status-hued hatch and a dashed "No spec" tag, and a planned one with a solid tint.
- **Do** draw every edge, bar line and the playhead in Rule Ink at 1px; emphasise by weight and by fading the rest.
- **Do** keep Bodoni Moda on the notation layer only: rehearsal letters, measure names, measure captions, empty states.
- **Do** set identifiers and agent output in JetBrains Mono, and counts a user compares in tabular Instrument Sans.
- **Do** keep text at 4.5:1 or better on its fill; on amber tint use Amber Ink, not Signal Amber.
- **Do** give every new visual encoding a legend entry in the strip.

### Don't:
- **Don't** fill cards with saturated status colour or colour edges by status.
- **Don't** use the hatch, dashes or amber as decoration; each one is a state.
- **Don't** use Alarm Red for anything but a budget hold or a failure that needs a person.
- **Don't** add resting shadows; the only shadows are card hover, the selection halo and the pulse ring.
- **Don't** place a card by anything but dependency depth, and don't turn the score into a freely panned, zoomed node canvas with a minimap.
- **Don't** use Bodoni Moda in the shell, on cards or in the side panel, and don't use mono for prose.

## Workbench additions

The workbench keeps the score and the shell and adds the planning conversation.

- **Context card.** The side panel moves to the top of the chat pane as a collapsible card: the selected node's spec references, acceptance criteria, dependencies, tracker link, and agent state, or, with nothing selected, the "Ready to start", "Agent activity", and "Without a spec" lists. It uses the side panel's typography, chips, and list rows.
- **Draft and orphan.** A node only in the spec store is a draft: a dashed border, the same dashed line language as other provisional marks, and a dashed "Draft" tag. A tracker issue whose deliverable left the plan is orphaned: an "Orphaned" tag and 80% opacity. Both have legend entries; the draft swatch is a dashed ink box.
- **Conversation.** Agent text is plain body type; the person's messages sit right-aligned on Strip Grey; tool calls are one mono line with a status dot; a permission request is an Amber Tint block with an amber border, because it is work waiting on a person. Attached nodes are amber pills in the composer.
- **Validation panel.** When the plan fails validation, a pale Alarm Red band under the strip lists every problem with its mono code and location. The score keeps the last valid plan.
- **Sync dialog.** A white 10px-radius dialog with the six preview counts in tabular figures; the apply button names the number of writes and appears only when the tracker can do them.
- **Project home.** A project opens on its home; the graph is the other page tab in the top bar (level-tab style). The home is a column on paper: a strip-grey band holding the goal's title and the timeline, then the execution-health tiles, the critical path, the three "Needs a person" columns, and a table of milestone progress. The composition is `specs/openspec/changes/workbench-project-home/prototype.html`.
- **Timeline (notation).** Milestone ticks are rule-ink hairlines labelled in the Measure italic; the goal's tick is a double line, like the final bar. The played stretch is a solid ink bar, the rest dashed. "We are here" is a playhead-style flag. A blocker that needs a person is an Alarm Red cross drawn from two bars (never a glyph), named on hover and focus; a stretch that cannot fit its crosses counts the rest ("+28"). Spans follow the work each milestone counts, with a floor so every label fits.
- **Urgency.** Alarm Red also marks work that needs a person now: the blocker crosses, a "stuck" or "idle now" verdict tile, and a slack bar that is blocking now. Amber is within four stories and Ledger Green is room to spare; every bar carries its slack in words, and every verdict is a word.
- **Changed stories.** A story whose state just changed pulses an amber ring for a few seconds and carries an "updated" tag; the pulse stops under reduced motion and the tag stays.

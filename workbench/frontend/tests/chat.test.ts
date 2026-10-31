import { flushSync, mount, tick, unmount } from "svelte";
import { afterEach, describe, expect, it } from "vitest";
import Harness from "./ChatHarness.svelte";
import { planDoc } from "./fixtures";
import type { BrokerEvent, ChatBlock, ChatItem } from "../src/lib/chat";
import { applyEvent, displayText, emptyTranscript, groupTurns, workSummary } from "../src/lib/chat";
import type { SessionClient } from "../src/lib/session";
import type { ConfigCategory, ConfigOption } from "../src/lib/api";
import type { ChangeRequirements, SpecReader } from "../src/lib/spec";

class FakeSession implements SessionClient {
  commands: Record<string, unknown>[] = [];
  listener: ((e: BrokerEvent) => void) | null = null;
  messages: { time: number; text: string }[] = [];
  constructor(public active = true) {}
  async status() { return { active: this.active, messages: this.messages }; }
  started: string[] = [];
  async start(message: string) {
    this.started.push(message);
    this.messages = [{ time: Date.now() / 1000, text: message }];
    this.active = true;
    return { active: true };
  }
  async stop() { this.active = false; return { active: false }; }
  async command(cmd: Record<string, unknown>) { this.commands.push(cmd); return {}; }
  subscribe(onEvent: (e: BrokerEvent) => void) { this.listener = onEvent; return () => (this.listener = null); }
  // Like the agent: opus has thinking levels and starts at "low"; the local model has none.
  levels: Record<string, string[]> = { "anthropic/opus": ["low", "high"], "llama/local": [] };
  current: { model: string; thought_level: string | null } = { model: "anthropic/opus", thought_level: "low" };
  configChanges: [string, string][] = [];
  options(): ConfigOption[] {
    const out: ConfigOption[] = [{
      id: "model", category: "model", name: "Model", currentValue: this.current.model,
      options: [{ value: "anthropic/opus", name: "Anthropic/Claude Opus" }, { value: "llama/local", name: "Local Coder" }],
    }];
    const levels = this.levels[this.current.model];
    if (levels.length) out.push({ id: "effort", category: "thought_level", name: "Effort", currentValue: this.current.thought_level, options: levels.map((v) => ({ value: v, name: v })) });
    return out;
  }
  async config() { return { options: this.options(), ready: true }; }
  async setConfig(category: ConfigCategory, value: string) {
    this.configChanges.push([category, value]);
    if (category === "model") this.current = { model: value, thought_level: this.levels[value][0] ?? null };
    else this.current.thought_level = value;
    return { options: this.options(), ready: true };
  }
  emit(e: Partial<BrokerEvent>) { this.listener!({ seq: 0, time: new Date().toISOString(), type: "state", ...e } as BrokerEvent); }
}

type H = { select: (k: string | null) => void; setEpic: (k: string | null) => void };
let app: (ReturnType<typeof mount> & H) | undefined;
afterEach(() => {
  if (app) unmount(app);
  app = undefined;
  document.body.innerHTML = "";
});

async function render(session = new FakeSession(), specs?: SpecReader) {
  app = mount(Harness, { target: document.body, props: { initial: planDoc(), session, specs } }) as typeof app;
  await settle();
  return { h: app!, session };
}
async function settle() {
  for (let i = 0; i < 5; i++) { await tick(); await Promise.resolve(); }
  flushSync();
}
const $ = <T extends Element = HTMLElement>(sel: string) => document.querySelector<T>(sel);

async function type(text: string) {
  const ta = $<HTMLTextAreaElement>("textarea")!;
  ta.value = text;
  ta.dispatchEvent(new Event("input", { bubbles: true }));
  flushSync();
}
async function submit() {
  $<HTMLFormElement>("form.composer")!.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
  await settle();
}

describe("chat pane: context card", () => {
  it("lists ready, active, and unplanned work when nothing is selected", async () => {
    await render();
    expect($("[data-list='Agent activity']")!.textContent).toContain("Title accounts-api");
    expect($("[data-list='Ready to start']")!.textContent).toContain("No epics");
  });

  it("shows the selected node's details", async () => {
    const { h } = await render();
    h.setEpic("billing");
    h.select("billing/invoice");
    await settle();
    const card = $(".context")!;
    expect(card.textContent).toContain("Title billing/invoice");
    expect(card.querySelector("[data-capability='cap']")!.textContent).toContain("Req billing/invoice");
    expect(card.textContent).toContain("billing/invoice works");
    expect(card.textContent).toContain("accounts-api/close");
    expect(card.querySelector("a")!.getAttribute("href")).toBe("https://huly/billing/invoice");
  });
});

describe("chat pane: a story's spec", () => {
  const billing: ChangeRequirements = {
    cap: [{
      name: "Req billing/invoice", operation: "ADDED", text: "An invoice SHALL carry the `customer_id`.",
      scenarios: [{ name: "A new invoice", steps: [
        { keyword: "WHEN", text: "an invoice is created" },
        { keyword: "THEN", text: "it names `customer_id`" },
        { keyword: "AND", text: "<img src=x onerror=alert(1)>it is saved" },
      ] }],
    }],
  };
  class FakeSpecs implements SpecReader {
    reads: string[] = [];
    constructor(private result: ChangeRequirements | Error) {}
    async requirements(change: string) {
      this.reads.push(change);
      if (this.result instanceof Error) throw this.result;
      return this.result;
    }
  }
  async function selectInvoice(specs: SpecReader) {
    const { h } = await render(new FakeSession(), specs);
    h.setEpic("billing");
    h.select("billing/invoice");
    await settle();
    return $(".context")!;
  }

  it("names each covered requirement in words under its capability, folded", async () => {
    const specs = new FakeSpecs(billing);
    const card = await selectInvoice(specs);
    expect(specs.reads).toEqual(["billing"]);
    expect(card.querySelector(".cap-name")!.textContent).toBe("cap");
    const req = card.querySelector<HTMLDetailsElement>("details[data-requirement='Req billing/invoice']")!;
    expect(req.querySelector("summary")!.textContent).toBe("Req billing/invoice");
    expect(req.open).toBe(false);
  });

  it("shows the requirement's text and scenarios when expanded, with code but nothing that runs", async () => {
    const card = await selectInvoice(new FakeSpecs(billing));
    (card.querySelector(".cap-toggle") as HTMLButtonElement).click();
    await settle();
    const req = card.querySelector<HTMLDetailsElement>("details[data-requirement='Req billing/invoice']")!;
    expect(req.open).toBe(true);
    expect(req.querySelector(".req-text code")!.textContent).toBe("customer_id");
    expect(req.querySelector(".scn-name")!.textContent).toBe("A new invoice");
    const steps = [...req.querySelectorAll(".steps li")].map((li) => li.textContent);
    expect(steps).toEqual(["whenan invoice is created", "thenit names customer_id", "andit is saved"]);
    expect(req.querySelector("img")).toBeNull();
    expect(card.querySelector(".cap-toggle")!.textContent).toBe("Collapse all");
  });

  it("says so when the change has no such requirement, or its specs cannot be read", async () => {
    let card = await selectInvoice(new FakeSpecs({ cap: [] }));
    expect(card.querySelector(".req-body")!.textContent).toContain("Not found in billing's specs.");
    unmount(app!);
    app = undefined;
    card = await selectInvoice(new FakeSpecs(new Error("The specs of billing could not be read (500).")));
    expect(card.querySelector("details[data-requirement='Req billing/invoice'] summary")!.textContent).toBe("Req billing/invoice");
    expect(card.querySelector(".err")!.textContent).toContain("could not be read (500)");
  });
});

describe("chat pane: selection as context", () => {
  it("attaches the story a deep link selects", async () => {
    app = mount(Harness, { target: document.body, props: {
      initial: planDoc(), session: new FakeSession(),
      initialView: { epic: "billing", selected: "billing/invoice", showCross: true, mark: null },
    } }) as typeof app;
    await settle();
    expect($("[data-attached='billing/invoice']")).not.toBeNull();
  });

  it("attaches the selected node to the next message, and can detach it", async () => {
    const { h, session } = await render();
    h.select("billing/invoice");
    await settle();
    expect($("[data-attached='billing/invoice']")).not.toBeNull();

    await type("split this into two");
    await submit();
    const sent = session.commands[0];
    expect(sent.op).toBe("steer");
    expect(sent.text).toContain("billing/invoice");
    expect(sent.text).toContain('"Title billing/invoice"');
    expect(String(sent.text).endsWith("split this into two")).toBe(true);
    expect($("[data-attached]")).toBeNull();

    h.select(null);
    await settle();
    h.select("billing");
    await settle();
    $<HTMLButtonElement>("[data-attached='billing'] button")!.click();
    await settle();
    expect($("[data-attached]")).toBeNull();
    await type("no context here");
    await submit();
    expect(session.commands[1].text).toBe("no context here");
  });
});

describe("chat pane: conversation", () => {
  it("renders the agent's Markdown, without anything that could run", async () => {
    const { session } = await render();
    const text = "## Status\n\n- **Done:** `ufw` rules\n- Left: [audit](https://example.com)\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n<script>window.pwned = 1</script><img src=x onerror=\"window.pwned=1\"><a href=\"javascript:alert(1)\">x</a>";
    session.emit({ seq: 1, type: "update", update: { update: { sessionUpdate: "agent_message_chunk", content: { type: "text", text } } } });
    await settle();
    const msg = $(".msg.agent")!;
    expect(msg.querySelector("h2")?.textContent).toBe("Status");
    expect(msg.querySelector("li strong")?.textContent).toBe("Done:");
    expect(msg.querySelector("li code")?.textContent).toBe("ufw");
    expect(msg.querySelector("td")?.textContent).toBe("1");
    const link = msg.querySelector<HTMLAnchorElement>("a[href='https://example.com']")!;
    expect(link.target).toBe("_blank");
    expect(link.rel).toBe("noopener noreferrer");
    expect(msg.querySelector("script, img, [onerror]")).toBeNull();
    expect(msg.querySelector("a[href^='javascript']")).toBeNull();
    expect((window as unknown as { pwned?: number }).pwned).toBeUndefined();
    expect(msg.textContent).not.toContain("##");
  });

  it("streams agent replies and shows the person's messages", async () => {
    const { session } = await render();
    session.emit({ seq: 1, type: "update", update: { update: { sessionUpdate: "agent_message_chunk", content: { type: "text", text: "Hello" } } } });
    session.emit({ seq: 2, type: "update", update: { update: { sessionUpdate: "agent_message_chunk", content: { type: "text", text: ", planner" } } } });
    session.emit({ seq: 3, type: "update", update: { update: { sessionUpdate: "tool_call", toolCallId: "t1", title: "planlib validate", status: "in_progress" } } });
    session.emit({ seq: 4, type: "update", update: { update: { sessionUpdate: "tool_call_update", toolCallId: "t1", status: "completed" } } });
    await settle();
    expect($(".msg.agent")!.textContent).toBe("Hello, planner");
    expect($(".tool")!.dataset.status).toBe("completed");
  });

  it("folds a turn's reasoning and tool calls, and shows only its reply", async () => {
    const { session } = await render();
    const upd = (seq: number, update: Record<string, unknown>) => session.emit({ seq, type: "update", update: { update } });
    upd(1, { sessionUpdate: "agent_thought_chunk", content: { type: "text", text: "Let me read the plan." } });
    upd(2, { sessionUpdate: "tool_call", toolCallId: "t1", title: "openspec/plan.yaml", status: "completed" });
    upd(3, { sessionUpdate: "tool_call", toolCallId: "t2", title: "planlib validate", status: "completed" });
    upd(4, { sessionUpdate: "agent_message_chunk", content: { type: "text", text: "</thi" } });
    upd(5, { sessionUpdate: "agent_message_chunk", content: { type: "text", text: "nk>The plan is empty." } });
    session.emit({ seq: 6, type: "result" });
    await settle();
    const work = $<HTMLDetailsElement>("details.work")!;
    expect(work.open).toBe(false);
    expect(work.querySelector("summary")!.textContent).toBe("Worked through 2 tool calls");
    expect(work.querySelectorAll(".tool")).toHaveLength(2);
    expect(work.querySelector(".thought")!.textContent).toBe("Let me read the plan.");
    const replies = [...document.querySelectorAll(".log > .msg.agent")];
    expect(replies.map((r) => r.textContent)).toEqual(["The plan is empty."]);
  });

  it("sends a permission answer to the relay", async () => {
    const { session } = await render();
    session.emit({
      seq: 5, type: "permission", id: '"perm-1"',
      request: { toolCall: { title: "run planlib validate" }, options: [
        { optionId: "allow", name: "Allow", kind: "allow_once" },
        { optionId: "deny", name: "Deny", kind: "reject_once" },
      ] },
    });
    await settle();
    const allow = [...document.querySelectorAll<HTMLButtonElement>(".permission button")].find((b) => b.textContent === "Allow")!;
    allow.click();
    await settle();
    expect(session.commands).toEqual([{ op: "permit", id: '"perm-1"', option: "allow" }]);

    session.emit({ seq: 6, type: "permission_resolved", id: '"perm-1"', message: "answered by a viewer: allow" });
    await settle();
    expect($(".permission .resolved")!.textContent).toContain("allow");
    expect($(".permission button")).toBeNull();
  });

  it("starts the session with the first message, selection included", async () => {
    const session = new FakeSession(false);
    const { h } = await render(session);
    expect($("textarea")!.hasAttribute("disabled")).toBe(false);
    expect([...document.querySelectorAll("button")].some((b) => b.textContent?.includes("Start"))).toBe(false);

    h.select("billing/invoice");
    await settle();
    await type("plan this epic");
    await submit();
    expect(session.started).toHaveLength(1);
    expect(session.started[0]).toContain("billing/invoice");
    expect(session.started[0].endsWith("plan this epic")).toBe(true);
    expect(session.commands).toEqual([]); // not sent a second time as a steer
    expect(session.active).toBe(true);
    expect($(".msg.user")!.textContent).toBe("(about billing/invoice) plan this epic");
    expect($("[data-attached]")).toBeNull();
    expect($(".session-bar")!.textContent).toContain("End session");
  });
});

describe("chat pane: model and thinking level", () => {
  it("shows the current model and thinking level, and changes them through the session", async () => {
    const { session } = await render();
    expect($(".trigger .value")!.textContent).toBe("Anthropic/Claude Opus");
    expect($<HTMLSelectElement>("[data-config='thought_level']")!.value).toBe("low");

    const level = $<HTMLSelectElement>("[data-config='thought_level']")!;
    level.value = "high";
    level.dispatchEvent(new Event("change", { bubbles: true }));
    await settle();
    expect(session.configChanges).toEqual([["thought_level", "high"]]);
    expect($<HTMLSelectElement>("[data-config='thought_level']")!.value).toBe("high");

    // Search the models, pick with the keyboard; the new model has no thinking levels.
    $<HTMLButtonElement>(".trigger")!.click();
    await settle();
    const search = $<HTMLInputElement>(".pop input")!;
    expect(document.activeElement).toBe(search);
    search.value = "local";
    search.dispatchEvent(new Event("input", { bubbles: true }));
    await settle();
    expect([...document.querySelectorAll("[role='option']")].map((o) => o.textContent?.trim())).toEqual(["Local Coder"]);
    search.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
    await settle();
    expect(session.configChanges[1]).toEqual(["model", "llama/local"]);
    expect($(".pop")).toBeNull();
    expect($(".trigger .value")!.textContent).toBe("Local Coder");
    expect($("[data-config='thought_level']")).toBeNull();
  });

  it("says at once that a session from an older driver cannot change model, and does not wait for it", async () => {
    const session = new FakeSession();
    let asked = 0;
    session.status = async () => ({ active: true, can_configure: false, messages: [] });
    session.config = async () => { asked++; return { options: [], ready: false }; };
    await render(session);
    expect($("[data-note='not-configurable']")!.textContent).toContain("End it");
    expect($(".trigger")).toBeNull();
    expect(asked).toBe(0);
  });

  it("shows no agent settings without a session", async () => {
    await render(new FakeSession(false));
    expect($(".trigger")).toBeNull();
    expect($("[data-config='thought_level']")).toBeNull();
  });
});

describe("transcript", () => {
  it("ignores replayed events and joins chunks", () => {
    let tr = emptyTranscript();
    const ev = { seq: 1, time: "2026-01-01T00:00:00Z", type: "update", update: { update: { sessionUpdate: "agent_message_chunk", content: { type: "text", text: "a" } } } } as BrokerEvent;
    tr = applyEvent(tr, ev);
    tr = applyEvent(tr, ev);
    expect(tr.items).toHaveLength(1);
    expect(displayText('[Selected in the plan graph]\n- billing/tax — "Tax" (story)\n\nsplit it')).toBe("(about billing/tax) split it");
  });

  it("ends the driver's turn on the broker's state event, which brings no result", () => {
    const ev = (seq: number, e: Partial<BrokerEvent>) => ({ seq, time: "2026-01-01T00:00:00Z", type: "state", ...e }) as BrokerEvent;
    const chunk = { update: { update: { sessionUpdate: "agent_message_chunk", content: { type: "text", text: "a" } } } };
    let tr = applyEvent(emptyTranscript(), ev(1, { driverTurn: "active" }));
    tr = applyEvent(tr, ev(2, { type: "update", ...chunk }));
    expect(tr.busy).toBe(true);
    tr = applyEvent(tr, ev(3, { driverTurn: "none" }));
    expect(tr.busy).toBe(false);
    // A person's own turn: chunks start it, its result ends it.
    tr = applyEvent(tr, ev(4, { type: "update", ...chunk }));
    expect(tr.busy).toBe(true);
    tr = applyEvent(tr, ev(5, { driverTurn: "none" }));
    expect(tr.busy).toBe(true);
    tr = applyEvent(tr, ev(6, { type: "result", op: "steer-turn" }));
    expect(tr.busy).toBe(false);
  });

  it("groups each turn separately and keeps interim messages in the fold", () => {
    const at = (n: number) => n;
    const items: ChatItem[] = [
      { kind: "agent", key: "a1", text: "Let me check.", time: at(1) },
      { kind: "tool", key: "t1", title: "ls", status: "completed", time: at(2) },
      { kind: "agent", key: "a2", text: "Done.", time: at(3) },
      { kind: "user", key: "u1", text: "now plan billing", time: at(4) },
      { kind: "agent", key: "a3", text: "<think>which change?</think>Planning billing.", time: at(5) },
    ];
    const blocks = groupTurns(items, true);
    expect(blocks.map((b) => b.kind)).toEqual(["work", "agent", "user", "work", "agent"]);
    const [first, , , second, last] = blocks as [Extract<ChatBlock, { kind: "work" }>, ChatBlock, ChatBlock, Extract<ChatBlock, { kind: "work" }>, ChatBlock];
    expect(first.steps.map((s) => s.key)).toEqual(["a1", "t1"]);
    expect(first.live).toBe(false);
    expect(second.steps).toMatchObject([{ kind: "thought", text: "which change?" }]);
    expect(second.live).toBe(true);
    expect(last).toMatchObject({ kind: "agent", text: "Planning billing." });
    expect(workSummary(second.steps, true)).toBe("Thinking");
  });
});

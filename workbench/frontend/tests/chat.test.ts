import { flushSync, mount, tick, unmount } from "svelte";
import { afterEach, describe, expect, it } from "vitest";
import Harness from "./ChatHarness.svelte";
import { planDoc } from "./fixtures";
import type { BrokerEvent, ChatBlock, ChatItem } from "../src/lib/chat";
import { applyEvent, displayText, emptyTranscript, groupTurns, workSummary } from "../src/lib/chat";
import type { SessionClient } from "../src/lib/session";

class FakeSession implements SessionClient {
  commands: Record<string, unknown>[] = [];
  listener: ((e: BrokerEvent) => void) | null = null;
  messages: { time: number; text: string }[] = [];
  constructor(public active = true) {}
  async status() { return { active: this.active, messages: this.messages }; }
  async start() { this.active = true; return { active: true }; }
  async stop() { this.active = false; return { active: false }; }
  async command(cmd: Record<string, unknown>) { this.commands.push(cmd); return {}; }
  subscribe(onEvent: (e: BrokerEvent) => void) { this.listener = onEvent; return () => (this.listener = null); }
  emit(e: Partial<BrokerEvent>) { this.listener!({ seq: 0, time: new Date().toISOString(), type: "state", ...e } as BrokerEvent); }
}

type H = { select: (k: string | null) => void; setEpic: (k: string | null) => void };
let app: (ReturnType<typeof mount> & H) | undefined;
afterEach(() => {
  if (app) unmount(app);
  app = undefined;
  document.body.innerHTML = "";
});

async function render(session = new FakeSession()) {
  app = mount(Harness, { target: document.body, props: { initial: planDoc(), session } }) as typeof app;
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
    expect(card.textContent).toContain("cap#Req billing/invoice");
    expect(card.textContent).toContain("billing/invoice works");
    expect(card.textContent).toContain("accounts-api/close");
    expect(card.querySelector("a")!.getAttribute("href")).toBe("https://huly/billing/invoice");
  });
});

describe("chat pane: selection as context", () => {
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

  it("offers to start a session when none runs", async () => {
    const session = new FakeSession(false);
    await render(session);
    const start = [...document.querySelectorAll<HTMLButtonElement>("button")].find((b) => b.textContent?.includes("Start planning session"))!;
    start.click();
    await settle();
    expect(session.active).toBe(true);
    expect($("textarea")!.hasAttribute("disabled")).toBe(false);
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

import { flushSync, mount, tick, unmount } from "svelte";
import { afterEach, describe, expect, it } from "vitest";
import SyncHarness from "./SyncHarness.svelte";
import GraphHarness from "./GraphHarness.svelte";
import ChatHarness from "./ChatHarness.svelte";
import { planDoc } from "./fixtures";
import type { SyncPreviewResponse } from "../src/lib/api";
import type { SyncClient } from "../src/lib/sync";
import { errorTarget } from "../src/lib/sync";
import type { SessionClient } from "../src/lib/session";
import { session as identity } from "../src/lib/identity.svelte";
import type { GraphNode } from "../src/lib/types";

class FakeSync implements SyncClient {
  applied: string[] = [];
  approved: { keys?: string[]; epic?: string }[] = [];
  calls: string[] = [];
  constructor(public missing: string[] = []) {}
  async preview(): Promise<SyncPreviewResponse> {
    return {
      preview_id: "p1", can_apply: this.missing.length === 0, capabilities: [],
      preview: { counts: { creates: 7, updates: 1, parents: 0, relations_added: 3, relations_removed: 1, orphans: 1, releases: 2 }, missing_capabilities: this.missing, skipped_drafts: ["billing"],
        releases: [{ plan_key: "billing/a1", identifier: "PLAT-1", to: "Todo" }, { plan_key: "billing/a2", to: "Todo" }] },
    };
  }
  async apply(id: string) { this.applied.push(id); return { result: { created: [1, 2, 3, 4, 5, 6, 7], updated: [1], parents_set: [], relations_added: [1, 2, 3], relations_removed: [1] } }; }
  async approve(t: { keys?: string[]; epic?: string }) { this.approved.push(t); return {}; }
  async pullBack(k: string) { this.calls.push(`pull-back ${k}`); return {}; }
  async cancel(k: string) { this.calls.push(`cancel ${k}`); return {}; }
  async supersede(k: string) { this.calls.push(`supersede ${k}`); return {}; }
}

let app: ReturnType<typeof mount> | undefined;
afterEach(() => {
  if (app) unmount(app);
  app = undefined;
  document.body.innerHTML = "";
});
async function settle() { for (let i = 0; i < 6; i++) { await tick(); await Promise.resolve(); } flushSync(); }
const $ = <T extends Element = HTMLElement>(s: string) => document.querySelector<T>(s);

describe("sync dialog", () => {
  it("shows the preview counts and applies only after the confirm", async () => {
    const sync = new FakeSync();
    app = mount(SyncHarness, { target: document.body, props: { sync } });
    await settle();
    expect($("[data-count='creates']")!.textContent).toBe("7");
    expect($("[data-count='updates']")!.textContent).toBe("1");
    expect($("[data-count='relations_added']")!.textContent).toBe("3");
    expect($("[data-count='relations_removed']")!.textContent).toBe("1");
    expect($("[data-count='releases']")!.textContent).toBe("2");
    expect($("[data-releases]")!.textContent).toContain("PLAT-1, billing/a2");
    expect(document.body.textContent).toContain("billing");
    expect(sync.applied).toEqual([]);

    $<HTMLButtonElement>("[data-confirm]")!.click();
    await settle();
    expect(sync.applied).toEqual(["p1"]);
    expect(document.body.textContent).toContain("7 created");
  });

  it("names a missing capability and offers no apply", async () => {
    const sync = new FakeSync(["link_dependency"]);
    app = mount(SyncHarness, { target: document.body, props: { sync } });
    await settle();
    expect($("[role='alert']")!.textContent).toContain("link_dependency");
    expect($("[data-confirm]")).toBeNull();
    expect(sync.applied).toEqual([]);
  });
});

describe("validation panel", () => {
  it("lists every error and selecting one selects its node", async () => {
    const doc = planDoc();
    doc.validation = {
      valid: false, version: 2,
      errors: [
        { code: "cycle", message: "deliverables depend on each other in a cycle", file: "x", change: "billing", deliverable: "tax", members: ["billing/tax", "billing/invoice"] },
        { code: "unknown_change", message: "ghost is not active", file: "openspec/plan.yaml", change: "ghost", deliverable: null, members: [] },
      ],
    };
    const h = mount(GraphHarness, { target: document.body, props: { initial: doc } }) as ReturnType<typeof mount> & { getView: () => { epic: string | null; selected: string | null } };
    app = h;
    await settle();
    const errs = document.querySelectorAll<HTMLButtonElement>(".validation .err");
    expect(errs).toHaveLength(2);
    expect(errs[1].disabled).toBe(true);
    errs[0].click();
    await settle();
    expect(h.getView()).toMatchObject({ epic: "billing", selected: "billing/tax" });
    expect($(".card[data-key='billing/tax']")!.getAttribute("aria-pressed")).toBe("true");
  });

  it("finds an error's node", () => {
    const has = (k: string) => ["a", "a/b"].includes(k);
    expect(errorTarget({ change: "a", deliverable: "b", members: [] }, has)).toBe("a/b");
    expect(errorTarget({ change: "a", deliverable: "zz", members: [] }, has)).toBe("a");
    expect(errorTarget({ change: null, deliverable: null, members: [] }, has)).toBeNull();
  });
});

const noSession: SessionClient = {
  status: async () => ({ active: false }), start: async (_message: string) => ({ active: true }), stop: async () => ({ active: false }),
  command: async () => ({}), subscribe: () => () => {},
  config: async () => ({ options: [], ready: true }), setConfig: async () => ({ options: [], ready: true }),
};

function chat(doc: ReturnType<typeof planDoc>, sync: FakeSync) {
  const h = mount(ChatHarness, { target: document.body, props: { initial: doc, session: noSession, actions: sync } }) as ReturnType<typeof mount> & { select: (k: string | null) => void; setEpic: (k: string | null) => void };
  app = h;
  return h;
}

function story(doc: ReturnType<typeof planDoc>, extra: Partial<GraphNode>): GraphNode {
  const n = doc.nodes.find((x) => x.kind === "story")!;
  Object.assign(n, extra);
  return n;
}

describe("approver actions", () => {
  afterEach(() => { identity.identity = null; });
  const approver = () => { identity.identity = { name: "Ann", email: "", roles: ["planner", "approver"], id: "a" }; };

  it("approves a never-approved epic in one action", async () => {
    approver();
    const doc = planDoc();
    doc.nodes.find((n) => n.plan_key === "billing")!.approval = "draft";
    for (const n of doc.nodes.filter((x) => x.change === "billing" && x.kind === "story")) { n.approval = "draft"; n.plan_status = "draft"; }
    const sync = new FakeSync();
    const h = chat(doc, sync);
    await settle();
    h.select("billing");
    await settle();
    $<HTMLButtonElement>("[data-act='approve-epic']")!.click();
    await settle();
    expect(sync.approved).toEqual([{ epic: "billing" }]);
  });

  it("approves one draft story and explains a held one", async () => {
    approver();
    const doc = planDoc();
    const s = story(doc, { plan_status: "draft", approval: "draft" });
    const sync = new FakeSync();
    const h = chat(doc, sync);
    await settle();
    h.select(s.plan_key);
    await settle();
    $<HTMLButtonElement>("[data-act='approve']")!.click();
    await settle();
    expect(sync.approved).toEqual([{ keys: [s.plan_key] }]);
    unmount(h); document.body.innerHTML = "";
    const doc2 = planDoc();
    const held = story(doc2, { plan_status: "held", held_by: ["billing/zz"], approval: "approved" });
    const h2 = chat(doc2, sync);
    await settle();
    h2.select(held.plan_key);
    await settle();
    expect($("[data-why='held']")!.textContent).toContain("billing/zz");
    expect($("[data-act='approve']")).toBeNull();
  });

  it("pulls back a released story and shows a re-review reason", async () => {
    approver();
    const doc = planDoc();
    const s = story(doc, { plan_status: "released", approval: "approved" });
    const sync = new FakeSync();
    const h = chat(doc, sync);
    await settle();
    h.select(s.plan_key);
    await settle();
    $<HTMLButtonElement>("[data-act='pull-back']")!.click();
    await settle();
    expect(sync.calls).toEqual([`pull-back ${s.plan_key}`]);
  });

  it("explains a re-review", async () => {
    approver();
    const doc = planDoc();
    const s = story(doc, { plan_status: "needs_rereview", rereview: { reason: "blocker_canceled", ref: "billing/a3" } });
    const h = chat(doc, new FakeSync());
    await settle();
    h.select(s.plan_key);
    await settle();
    expect($("[data-why='rereview']")!.textContent).toContain("billing/a3 was cancelled");
    expect($("[data-act='approve']")).not.toBeNull();
  });

  it("shows held and re-review on the story cards", async () => {
    const doc = planDoc();
    const [a, b] = doc.nodes.filter((x) => x.kind === "story" && x.change === doc.nodes.find((n) => n.kind === "story")!.change);
    Object.assign(a, { plan_status: "held", held_by: ["x/y"], tracker: null, runtime: null, status: "draft" });
    Object.assign(b, { plan_status: "needs_rereview", rereview: { reason: "blocker_canceled", ref: "x/y" }, tracker: null, runtime: null, status: "draft" });
    app = mount(GraphHarness, { target: document.body, props: { initial: doc } });
    await settle();
    (app as unknown as { getView: () => { epic: string | null } }).getView().epic = a.change;
    await settle();
    expect($(`[data-key='${a.plan_key}'] .meta`)!.textContent).toBe("held for approval");
    expect($(`[data-key='${b.plan_key}'] .meta`)!.textContent).toBe("needs re-review");
  });

  it("hides every action from a planner", async () => {
    identity.identity = { name: "Pat", email: "", roles: ["planner"], id: "p" };
    const doc = planDoc();
    const s = story(doc, { plan_status: "draft", approval: "draft" });
    const h = chat(doc, new FakeSync());
    await settle();
    h.select(s.plan_key);
    await settle();
    expect($("[data-plan-status='draft']")).not.toBeNull();
    expect(document.querySelectorAll("[data-act]").length).toBe(0);
  });
});

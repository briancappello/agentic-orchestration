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

class FakeSync implements SyncClient {
  applied: string[] = [];
  approved: string[] = [];
  constructor(public missing: string[] = []) {}
  async preview(): Promise<SyncPreviewResponse> {
    return {
      preview_id: "p1", can_apply: this.missing.length === 0, capabilities: [],
      preview: { counts: { creates: 7, updates: 1, parents: 0, relations_added: 3, relations_removed: 1, orphans: 1 }, missing_capabilities: this.missing, skipped_drafts: ["billing"] },
    };
  }
  async apply(id: string) { this.applied.push(id); return { result: { created: [1, 2, 3, 4, 5, 6, 7], updated: [1], parents_set: [], relations_added: [1, 2, 3], relations_removed: [1] } }; }
  async approve(change: string) { this.approved.push(change); return {}; }
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

describe("approve action", () => {
  it("approves the selected change's draft breakdown", async () => {
    const doc = planDoc();
    doc.nodes.find((n) => n.plan_key === "billing")!.approval = "draft";
    const session: SessionClient = {
      status: async () => ({ active: false }), start: async (_message: string) => ({ active: true }), stop: async () => ({ active: false }),
      command: async () => ({}), subscribe: () => () => {},
      config: async () => ({ options: [], ready: true }), setConfig: async () => ({ options: [], ready: true }),
    };
    const sync = new FakeSync();
    const h = mount(ChatHarness, { target: document.body, props: { initial: doc, session, onapprove: (c: string) => sync.approve(c) } }) as ReturnType<typeof mount> & { select: (k: string) => void };
    app = h;
    await settle();
    h.select("billing");
    await settle();
    $<HTMLButtonElement>("[data-approve='billing']")!.click();
    await settle();
    expect(sync.approved).toEqual(["billing"]);
  });
});

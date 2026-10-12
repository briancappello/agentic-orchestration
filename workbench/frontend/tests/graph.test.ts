import { flushSync, mount, unmount } from "svelte";
import { afterEach, describe, expect, it } from "vitest";
import Harness from "./GraphHarness.svelte";
import { node, planDoc } from "./fixtures";

type H = { setDoc: (d: ReturnType<typeof planDoc>) => void; getView: () => { epic: string | null; selected: string | null } };
let app: (ReturnType<typeof mount> & H) | undefined;
afterEach(() => {
  if (app) unmount(app);
  app = undefined;
  document.body.innerHTML = "";
});

function render(doc = planDoc()) {
  app = mount(Harness, { target: document.body, props: { initial: doc } }) as typeof app;
  flushSync();
  return app!;
}
const card = (key: string) => document.querySelector<HTMLButtonElement>(`.card[data-key="${key}"]`);
const click = (el: Element | null) => { (el as HTMLElement).click(); flushSync(); };
const dbl = (el: Element | null) => { el!.dispatchEvent(new MouseEvent("dblclick", { bubbles: true })); flushSync(); };

describe("graph pane: levels", () => {
  it("shows only epics at the project level, ordered by dependency", () => {
    render();
    const keys = [...document.querySelectorAll<HTMLElement>(".card")].map((c) => c.dataset.key);
    expect(keys).toEqual(["accounts-api", "billing"]);
    expect(parseFloat(card("billing")!.style.left)).toBeGreaterThan(parseFloat(card("accounts-api")!.style.left));
    expect(document.querySelector("[data-edge='accounts-api>billing']")).not.toBeNull();
  });

  it("drills into an epic, shows cross-epic references, hides them, and goes back in one action", () => {
    const h = render();
    dbl(card("billing"));
    const keys = [...document.querySelectorAll<HTMLElement>(".card")].map((c) => c.dataset.key).sort();
    expect(keys).toEqual(["billing/invoice", "billing/old", "billing/tax"]);
    expect(document.querySelector("[data-stub='accounts-api/close']")).not.toBeNull();
    expect(document.querySelector("[data-edge='accounts-api/close>billing/invoice']")?.classList.contains("ext")).toBe(true);

    const toggle = document.querySelector<HTMLInputElement>(".toggle input")!;
    toggle.checked = false;
    toggle.dispatchEvent(new Event("change", { bubbles: true }));
    flushSync();
    expect(document.querySelector("[data-stub]")).toBeNull();

    click(document.querySelector(".crumbs .home"));
    expect(h.getView().epic).toBeNull();
    expect([...document.querySelectorAll<HTMLElement>(".card")].map((c) => c.dataset.key)).toEqual(["accounts-api", "billing"]);
  });
});

describe("graph pane: node encoding", () => {
  it("borders by status and shows the identifier, title, and state", () => {
    render();
    expect(card("accounts-api")!.classList.contains("prog")).toBe(true);
    expect(card("billing")!.classList.contains("todo")).toBe(true);
    expect(card("billing")!.querySelector(".t")!.textContent).toBe("Title billing");
    expect(card("billing")!.querySelector(".st")!.textContent).toBe("Todo");
    expect(card("billing")!.querySelector(".id")!.textContent).toBe("HULY-7");
  });

  it("an unplanned story has the unplanned fill and a no-spec marker", () => {
    render();
    dbl(card("billing"));
    const tax = card("billing/tax")!;
    expect(tax.classList.contains("unplanned")).toBe(true);
    expect(tax.querySelector(".tag.nospec")?.textContent).toBe("No spec");
    expect(card("billing/invoice")!.classList.contains("unplanned")).toBe(false);
  });

  it("marks drafts and orphans", () => {
    render();
    dbl(card("billing"));
    expect(card("billing/tax")!.classList.contains("draft")).toBe(true);
    expect(card("billing/tax")!.querySelector(".draft-tag")?.textContent).toBe("Draft");
    expect(card("billing/old")!.classList.contains("orphaned")).toBe(true);
    expect(card("billing/old")!.querySelector(".orphan-tag")?.textContent).toBe("Orphaned");
  });

  it("a running agent badges the story and its epic; the epic shows done of total", () => {
    render();
    expect(card("accounts-api")!.querySelector(".badge.run")?.textContent).toBe("1 agent running");
    expect(card("accounts-api")!.querySelector(".r3 .meta")?.textContent).toBe("1/2 done");
    dbl(card("accounts-api"));
    expect(card("accounts-api/open")!.querySelector(".badge.run")?.textContent).toContain("running · turn 3");
    expect(card("accounts-api/close")!.querySelector(".badge")).toBeNull();
  });
});

describe("graph pane: live redraw", () => {
  it("adds a new deliverable and keeps the level, selection, and scroll", () => {
    const h = render();
    dbl(card("billing"));
    click(card("billing/invoice"));
    const canvas = document.querySelector<HTMLElement>(".canvas")!;
    canvas.scrollLeft = 120;

    const next = planDoc();
    next.nodes.push(node("billing/vat", { depth: 0 }));
    next.parents.push({ child: "billing/vat", parent: "billing" });
    next.version = 2;
    h.setDoc(next);
    flushSync();

    expect(card("billing/vat")).not.toBeNull();
    expect(h.getView()).toMatchObject({ epic: "billing", selected: "billing/invoice" });
    expect(card("billing/invoice")!.getAttribute("aria-pressed")).toBe("true");
    expect(document.querySelector(".canvas")).toBe(canvas);
    expect(canvas.scrollLeft).toBe(120);
  });

  it("keeps the selection when the selected node's tracker state changes", () => {
    const h = render();
    click(card("billing"));
    const next = planDoc();
    next.nodes.find((n) => n.plan_key === "billing")!.tracker!.state = "In Progress";
    h.setDoc(next);
    flushSync();
    expect(card("billing")!.classList.contains("prog")).toBe(true);
    expect(card("billing")!.getAttribute("aria-pressed")).toBe("true");
  });
});

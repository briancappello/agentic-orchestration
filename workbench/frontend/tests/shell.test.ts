import { flushSync, mount, unmount } from "svelte";
import { afterEach, describe, expect, it } from "vitest";
import Harness from "./ShellHarness.svelte";
import { MIN_CHAT, MIN_GRAPH, paneLayout } from "../src/lib/panes";

let app: ReturnType<typeof mount> | undefined;
afterEach(() => {
  localStorage.clear();
  if (app) unmount(app);
  app = undefined;
  document.body.innerHTML = "";
});

function render(width: number) {
  window.innerWidth = width;
  app = mount(Harness, { target: document.body, props: {} });
  flushSync();
  const panes = [...document.querySelectorAll<HTMLElement>(".pane")];
  return { shell: document.querySelector<HTMLElement>(".shell")!, panes };
}

describe("two-pane shell", () => {
  it("splits 60/40 at 1440px: 864px graph, 576px chat", () => {
    const { shell, panes } = render(1440);
    expect(shell.dataset.mode).toBe("split");
    expect(panes[0].getAttribute("aria-label")).toBe("Plan graph");
    expect(panes[0].style.width).toBe("864px");
    expect(panes[1].style.width).toBe("576px");
  });

  it("stacks at 900px with the graph first", () => {
    const { shell, panes } = render(900);
    expect(shell.dataset.mode).toBe("stacked");
    expect(panes.map((p) => p.getAttribute("aria-label"))).toEqual(["Plan graph", "Planning chat"]);
    expect(panes[0].style.width).toBe("");
  });

  it("switches at 1200px", () => {
    expect(paneLayout(1199).mode).toBe("stacked");
    expect(paneLayout(1200)).toEqual({ mode: "split", graph: 720, chat: 480 });
  });

  it("keeps both panes usable whatever the share", () => {
    expect(paneLayout(1440, 0.05)).toEqual({ mode: "split", graph: MIN_GRAPH, chat: 1440 - MIN_GRAPH });
    expect(paneLayout(1440, 0.99)).toEqual({ mode: "split", graph: 1440 - MIN_CHAT, chat: MIN_CHAT });
  });
});

describe("resizing the split", () => {
  const divider = () => document.querySelector<HTMLElement>("[role=separator]")!;
  const widths = () => [...document.querySelectorAll<HTMLElement>(".pane")].map((p) => p.style.width);
  const pointer = (type: string, clientX: number) => {
    const e = new MouseEvent(type, { bubbles: true, clientX, button: 0 });
    divider().dispatchEvent(Object.assign(e, { pointerId: 1 }));
    flushSync();
  };
  const key = (k: string) => { divider().dispatchEvent(new KeyboardEvent("keydown", { key: k, bubbles: true })); flushSync(); };

  it("drags the divider, clamps it, and remembers the share", () => {
    render(1440);
    divider().setPointerCapture = () => {};
    pointer("pointerdown", 864);
    pointer("pointermove", 1000);
    expect(widths()).toEqual(["1000px", "440px"]);
    pointer("pointermove", 1400);
    expect(widths()).toEqual([`${1440 - MIN_CHAT}px`, `${MIN_CHAT}px`]);
    pointer("pointermove", 700);
    pointer("pointerup", 700);
    expect(divider().getAttribute("aria-valuenow")).toBe("49");

    unmount(app!);
    render(1440);
    expect(widths()).toEqual(["700px", "740px"]);
  });

  it("moves with the arrow keys and resets on double-click", () => {
    render(1440);
    key("ArrowLeft");
    expect(widths()[0]).toBe("840px");
    key("End");
    expect(widths()[0]).toBe(`${1440 - MIN_CHAT}px`);
    divider().dispatchEvent(new MouseEvent("dblclick", { bubbles: true }));
    flushSync();
    expect(widths()).toEqual(["864px", "576px"]);
    expect(localStorage.length).toBe(0);
  });

  it("has no divider when the panes are stacked", () => {
    render(900);
    expect(document.querySelector("[role=separator]")).toBeNull();
  });
});

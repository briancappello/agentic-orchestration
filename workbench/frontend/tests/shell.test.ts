import { flushSync, mount, unmount } from "svelte";
import { afterEach, describe, expect, it } from "vitest";
import Harness from "./ShellHarness.svelte";
import { paneLayout } from "../src/lib/panes";

let app: ReturnType<typeof mount> | undefined;
afterEach(() => {
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
});

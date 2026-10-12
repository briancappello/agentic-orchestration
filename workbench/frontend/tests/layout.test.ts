import { describe, expect, it } from "vitest";
import { GEOMETRY, layoutScore } from "../src/lib/layout";

const g = GEOMETRY;

function deps(map: Record<string, string[]>) {
  return (k: string) => map[k] ?? [];
}

describe("score layout", () => {
  it("puts a chain of three in three columns, left to right", () => {
    const l = layoutScore({
      nodes: [{ key: "a", depth: 0 }, { key: "b", depth: 1 }, { key: "c", depth: 2 }],
      blockers: deps({ b: ["a"], c: ["b"] }),
      isDone: () => false,
    });
    expect(l.columns).toEqual([["a"], ["b"], ["c"]]);
    const xa = l.pos.get("a")!.x, xb = l.pos.get("b")!.x, xc = l.pos.get("c")!.x;
    expect(xa).toBeLessThan(xb);
    expect(xb).toBeLessThan(xc);
    expect(xb - xa).toBe(g.col);
    // A chain on one row draws straight edges from blocker to blocked.
    expect(l.edges.map((e) => [e.from, e.to])).toEqual([["a", "b"], ["b", "c"]]);
    expect(l.edges[0].path).toBe(`M${xa + g.cardW} ${g.top + g.cardH / 2}H${xb - 2}`);
    expect(l.frontier).toBe(0);
    expect(l.finX).toBe(l.colX(3) - 20);
  });

  it("moves the frontier past finished columns", () => {
    const l = layoutScore({
      nodes: [{ key: "a", depth: 0 }, { key: "b", depth: 1 }, { key: "c", depth: 2 }],
      blockers: deps({ b: ["a"], c: ["b"] }),
      isDone: (k) => k === "a",
    });
    expect(l.frontier).toBe(1);
    expect(l.playX).toBe(l.colX(1) - 34);
  });

  it("places a node at the average height of its blockers", () => {
    const l = layoutScore({
      nodes: [{ key: "a", depth: 0 }, { key: "b", depth: 0 }, { key: "c", depth: 1 }],
      blockers: deps({ c: ["a", "b"] }),
      isDone: () => false,
    });
    expect(l.pos.get("b")!.y).toBe(g.top + g.row);
    expect(l.pos.get("c")!.y).toBe(g.top + g.row / 2);
  });

  it("drill-down: blockers in other epics become stubs in a left lane", () => {
    const nodes = [{ key: "billing/invoice", depth: 0 }, { key: "billing/tax", depth: 1 }, { key: "billing/report", depth: 0 }];
    const blockers = deps({
      "billing/invoice": ["accounts/close"],
      "billing/tax": ["billing/invoice"],
      "billing/report": ["accounts/close", "search/index"],
    });
    const l = layoutScore({ nodes, blockers, isDone: () => false, showExternal: true });

    expect(l.stubs.map((s) => s.key)).toEqual(["accounts/close", "search/index"]);
    const close = l.stubs[0];
    expect(close.x).toBe(g.left);
    expect(close.targets).toEqual(["billing/invoice", "billing/report"]);
    // At the average of its targets' rows, and stubs never overlap.
    const avg = (l.pos.get("billing/invoice")!.y + l.pos.get("billing/report")!.y) / 2;
    expect(close.y).toBe(avg + g.cardH / 2 - 12);
    expect(l.stubs[1].y).toBeGreaterThanOrEqual(close.y + g.stubPitch);
    // The lane pushes the columns right of it.
    expect(l.colX(0)).toBe(g.left + g.extW + 40);
    expect(l.pos.get("billing/invoice")!.x).toBe(l.colX(0));
    expect(l.edges.filter((e) => e.external).map((e) => e.to)).toEqual(["billing/invoice", "billing/report", "billing/report"]);

    const hidden = layoutScore({ nodes, blockers, isDone: () => false, showExternal: false });
    expect(hidden.stubs).toEqual([]);
    expect(hidden.colX(0)).toBe(g.left);
  });
});

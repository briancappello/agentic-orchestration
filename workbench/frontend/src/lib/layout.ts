/**
 * Score layout, ported from the prototype as plain TypeScript so it can be
 * tested on its own. A node's column is the dependency depth the backend
 * computed for its view; rows are placed near the average of the node's
 * blockers so edges stay short. Blockers outside the view become stubs in
 * a lane on the left.
 */

export const GEOMETRY = {
  col: 300,
  cardW: 232,
  cardH: 112,
  row: 112 + 44,
  left: 40,
  top: 96,
  extW: 220,
  stubPitch: 36,
} as const;

export interface LayoutNode {
  key: string;
  depth: number;
}

export interface LayoutInput {
  nodes: LayoutNode[];
  /** Blockers of a node, by key, anywhere in the graph. */
  blockers: (key: string) => string[];
  isDone: (key: string) => boolean;
  /** Draw stubs for blockers outside the view. */
  showExternal?: boolean;
}

export interface Point { x: number; y: number }

export interface Edge {
  from: string;
  to: string;
  path: string;
  external: boolean;
}

export interface Stub {
  key: string;
  x: number;
  y: number;
  targets: string[];
}

export interface Layout {
  columns: string[][];
  pos: Map<string, Point>;
  edges: Edge[];
  stubs: Stub[];
  /** Index of the first column not entirely done; columns.length when all are. */
  frontier: number;
  playX: number;
  finX: number;
  width: number;
  height: number;
  colX: (depth: number) => number;
}

export function edgePath(x1: number, y1: number, x2: number, y2: number): string {
  if (y1 === y2) return `M${x1} ${y1}H${x2}`;
  const mid = (x1 + x2) / 2;
  return `M${x1} ${y1}C${mid} ${y1} ${mid} ${y2} ${x2} ${y2}`;
}

export function layoutScore(input: LayoutInput): Layout {
  const g = GEOMETRY;
  const inView = new Set(input.nodes.map((n) => n.key));
  const depthOf = new Map(input.nodes.map((n) => [n.key, Math.max(0, n.depth)]));

  const columns: string[][] = [];
  for (const n of input.nodes) (columns[depthOf.get(n.key)!] ??= []).push(n.key);
  for (let d = 0; d < columns.length; d++) columns[d] ??= [];

  const inViewBlockers = (key: string) => input.blockers(key).filter((b) => inView.has(b));

  // Blockers outside the view, each with the nodes it blocks.
  const external = new Map<string, string[]>();
  if (input.showExternal) {
    for (const n of input.nodes) {
      for (const b of input.blockers(n.key)) {
        if (inView.has(b)) continue;
        (external.get(b) ?? external.set(b, []).get(b)!).push(n.key);
      }
    }
  }
  const offset = external.size ? g.extW + 40 : 0;
  const colX = (d: number) => g.left + offset + d * g.col;

  const y = new Map<string, number>();
  columns.forEach((col, d) => {
    const target = (key: string) => {
      const ys = inViewBlockers(key).filter((b) => y.has(b)).map((b) => y.get(b)!);
      return ys.length ? ys.reduce((a, b) => a + b, 0) / ys.length : g.top;
    };
    const ordered = d === 0 ? col : [...col].sort((a, b) => target(a) - target(b));
    let next: number = g.top;
    for (const key of ordered) {
      const placed = d === 0 ? next : Math.max(target(key), next);
      y.set(key, placed);
      next = placed + g.row;
    }
  });

  const pos = new Map<string, Point>();
  for (const n of input.nodes) pos.set(n.key, { x: colX(depthOf.get(n.key)!), y: y.get(n.key)! });

  const edges: Edge[] = [];
  for (const n of input.nodes) {
    const to = pos.get(n.key)!;
    for (const b of inViewBlockers(n.key)) {
      const from = pos.get(b)!;
      edges.push({
        from: b, to: n.key, external: false,
        path: edgePath(from.x + g.cardW, from.y + g.cardH / 2, to.x - 2, to.y + g.cardH / 2),
      });
    }
  }

  const stubs: Stub[] = [];
  let stubNext: number = g.top;
  for (const [key, targets] of external) {
    const avg = targets.reduce((s, t) => s + y.get(t)!, 0) / targets.length;
    const sy = Math.max(avg + g.cardH / 2 - 12, stubNext);
    stubNext = sy + g.stubPitch;
    stubs.push({ key, x: g.left, y: sy, targets });
    for (const t of targets) {
      const to = pos.get(t)!;
      edges.push({ from: key, to: t, external: true, path: edgePath(g.left + g.extW - 8, sy + 12, to.x - 2, to.y + g.cardH / 2) });
    }
  }

  const last = columns.length;
  const finX = colX(last) - 20;
  let frontier = columns.findIndex((col) => !col.every(input.isDone));
  if (frontier === -1) frontier = last;
  const playX = frontier === last ? finX - 30 : frontier === 0 ? colX(0) - 20 : colX(frontier) - 34;
  const maxY = Math.max(g.top, ...y.values(), ...stubs.map((s) => s.y));
  return {
    columns, pos, edges, stubs, frontier, playX, finX,
    width: finX + 220,
    height: maxY + g.cardH + 150,
    colX,
  };
}

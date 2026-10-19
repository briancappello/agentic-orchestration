import type { GraphNode, MergedGraph, Runtime } from "../src/lib/types";

export function node(key: string, extra: Partial<GraphNode> = {}): GraphNode {
  const story = key.includes("/");
  return {
    plan_key: key, kind: story ? "story" : "epic", change: key.split("/")[0], title: `Title ${key}`,
    approval: "approved", has_spec: true, depth: 0, deliverable_kind: story ? "story" : null,
    covers: story ? [`cap#Req ${key}`] : [], acceptance_criteria: story ? [`${key} works`] : [],
    status: "draft", tracker: null, runtime: null, ...extra,
  };
}

export function synced(key: string, state = "Todo", extra: Partial<GraphNode> = {}, runtime: Runtime | null = null): GraphNode {
  return node(key, {
    status: "synced", runtime,
    tracker: { id: `id-${key}`, identifier: `HULY-${key.length}`, title: key, state, terminal: state === "Done", url: `https://huly/${key}`, parent_id: null },
    ...extra,
  });
}

export function graph(nodes: GraphNode[], blocks: [string, string][] = [], extra: Partial<MergedGraph> = {}): MergedGraph {
  return {
    version: 1, generated_at: 0, nodes,
    parents: nodes.filter((n) => n.kind === "story").map((n) => ({ child: n.plan_key, parent: n.change })),
    blocks: blocks.map(([blocker, blocked]) => ({ blocker, blocked })),
    unplanned_changes: [],
    validation: { valid: true, errors: [], version: 1 },
    sortie: { reachable: true, error: null, capabilities: ["create_issue", "update_issue", "set_parent", "link_dependency"], generated_at: null },
    ...extra,
  };
}

/** accounts-api and billing; billing/invoice depends on accounts-api/close. */
export function planDoc(): MergedGraph {
  return graph(
    [
      synced("accounts-api", "In Progress"),
      synced("accounts-api/close", "Done", { depth: 0 }),
      synced("accounts-api/open", "In Progress", { depth: 0 }, { status: "running", turn_count: 3, last_message: "writing tests" }),
      synced("billing", "Todo", { depth: 1 }),
      synced("billing/invoice", "Todo", { depth: 0 }),
      node("billing/tax", { depth: 1, has_spec: false }),
      synced("billing/old", "Todo", { status: "orphaned", approval: null, has_spec: null }),
    ],
    [["accounts-api", "billing"], ["accounts-api/close", "billing/invoice"], ["billing/invoice", "billing/tax"]],
  );
}

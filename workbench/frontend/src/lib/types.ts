/** The merged graph the backend serves on /api/graph and /api/events. */

export type NodeStatus = "draft" | "synced" | "orphaned";

export interface Runtime {
  status: "running" | "retrying" | "budget_held";
  turn_count?: number | null;
  last_message?: string | null;
  attempt?: number | null;
}

export interface TrackerView {
  id: string;
  identifier: string;
  title: string;
  state: string;
  terminal: boolean;
  url: string | null;
  parent_id: string | null;
}

export interface GraphNode {
  plan_key: string;
  kind: "epic" | "story";
  change: string;
  title: string;
  body?: string;
  approval: "approved" | "draft" | "unplanned" | null;
  has_spec: boolean | null;
  depth: number;
  deliverable_kind: string | null;
  covers: string[];
  acceptance_criteria: string[];
  status: NodeStatus;
  tracker: TrackerView | null;
  runtime: Runtime | null;
  // Stories only: the plan status the workbench derives from approvals and Sortie.
  plan_status?: PlanStatus | null;
  held_by?: string[];
  rereview?: { reason: string; ref: string } | null;
  frozen?: boolean;
  approved_by?: { name: string; id: string } | null;
  approved_at?: number | null;
  review?: "human" | "criteria";
  supersedes?: string | null;
}

export type PlanStatus = "draft" | "held" | "ready" | "released" | "frozen" | "needs_rereview";

export interface PlanError {
  code: string;
  message: string;
  file: string | null;
  change: string | null;
  deliverable: string | null;
  members: string[];
}

export interface MergedGraph {
  version: number;
  generated_at: number;
  nodes: GraphNode[];
  parents: { child: string; parent: string }[];
  blocks: { blocker: string; blocked: string }[];
  unplanned_changes: string[];
  validation: { valid: boolean; errors: PlanError[]; version: number };
  sortie: {
    reachable: boolean; error: string | null; capabilities: string[]; generated_at: string | null;
    /** The tracker project, and whether Sortie runs agents for it (it does for its configured project only). */
    project?: string; dispatched?: boolean;
  };
}

/** A project as the projects list shows it. */
export interface ProjectSummary {
  id: number;
  slug: string;
  name: string;
  huly_project: string;
  store_path: string;
  created_at: number;
  valid: boolean;
  errors: number;
  epics: number;
  stories: number;
  session_active: boolean;
  sortie: { reachable: boolean; dispatched: boolean };
}

/** A tracker project as Sortie reports it. */
export interface TrackerProject {
  key: string;
  name: string | null;
  url: string | null;
  exists: boolean;
  created: boolean;
  ready: boolean;
  dispatched: boolean;
  problems: string[];
}

export function emptyGraph(): MergedGraph {
  return {
    version: 0, generated_at: 0, nodes: [], parents: [], blocks: [], unplanned_changes: [],
    validation: { valid: true, errors: [], version: 0 },
    sortie: { reachable: false, error: null, capabilities: [], generated_at: null },
  };
}

/** Where the person is in the graph; kept across live updates. */
export interface ViewState {
  epic: string | null;
  selected: string | null;
  showCross: boolean;
}

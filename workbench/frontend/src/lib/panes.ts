/** The two-pane split: graph and chat side by side from 1200px up, stacked below.
 * The graph takes 60% unless the person drags the divider; their share is kept. */
export const SPLIT_MIN_WIDTH = 1200;
export const DEFAULT_GRAPH_SHARE = 0.6;
export const MIN_GRAPH = 480;
export const MIN_CHAT = 360;
const STORAGE_KEY = "workbench.graphShare";

export type PaneLayout =
  | { mode: "split"; graph: number; chat: number }
  | { mode: "stacked" };

/** The graph's width for a share of the viewport, kept so neither pane gets too narrow. */
export function clampGraph(viewportWidth: number, graph: number): number {
  return Math.round(Math.min(Math.max(graph, MIN_GRAPH), viewportWidth - MIN_CHAT));
}

export function paneLayout(viewportWidth: number, graphShare = DEFAULT_GRAPH_SHARE): PaneLayout {
  if (viewportWidth < SPLIT_MIN_WIDTH) return { mode: "stacked" };
  const graph = clampGraph(viewportWidth, viewportWidth * graphShare);
  return { mode: "split", graph, chat: viewportWidth - graph };
}

export function loadGraphShare(): number {
  try {
    const v = Number(localStorage.getItem(STORAGE_KEY));
    return v > 0 && v < 1 ? v : DEFAULT_GRAPH_SHARE;
  } catch {
    return DEFAULT_GRAPH_SHARE;
  }
}

export function saveGraphShare(share: number): void {
  try {
    if (share === DEFAULT_GRAPH_SHARE) localStorage.removeItem(STORAGE_KEY);
    else localStorage.setItem(STORAGE_KEY, String(share));
  } catch {
    // storage unavailable: the share lasts for this page only
  }
}

/** The two-pane split: 60% graph and 40% chat from 1200px up, stacked below. */
export const SPLIT_MIN_WIDTH = 1200;

export type PaneLayout =
  | { mode: "split"; graph: number; chat: number }
  | { mode: "stacked" };

export function paneLayout(viewportWidth: number): PaneLayout {
  if (viewportWidth < SPLIT_MIN_WIDTH) return { mode: "stacked" };
  const graph = Math.round(viewportWidth * 0.6);
  return { mode: "split", graph, chat: viewportWidth - graph };
}

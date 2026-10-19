/** The app's places, kept in the URL hash so links and reloads land where they were. */
import type { ViewState } from "./types";

export type Route =
  | { name: "projects" }
  | { name: "new" }
  | { name: "project"; slug: string; view: ViewState };

export function parseRoute(hash: string): Route {
  const raw = hash.replace(/^#/, "");
  const [path, query = ""] = raw.split("?");
  const parts = path.split("/").filter(Boolean);
  if (parts[0] === "new" && parts.length === 1) return { name: "new" };
  if (parts[0] === "p" && parts[1] && parts.length === 2) {
    const q = new URLSearchParams(query);
    return {
      name: "project",
      slug: decodeURIComponent(parts[1]),
      view: { epic: q.get("epic"), selected: q.get("sel"), showCross: q.get("cross") !== "0" },
    };
  }
  return { name: "projects" };
}

export function formatRoute(route: Route): string {
  switch (route.name) {
    case "projects":
      return "#/";
    case "new":
      return "#/new";
    case "project": {
      const q = new URLSearchParams();
      if (route.view.epic) q.set("epic", route.view.epic);
      if (route.view.selected) q.set("sel", route.view.selected);
      if (!route.view.showCross) q.set("cross", "0");
      const s = q.toString();
      return `#/p/${encodeURIComponent(route.slug)}${s ? `?${s}` : ""}`;
    }
  }
}

export const projectHref = (slug: string) => formatRoute({ name: "project", slug, view: { epic: null, selected: null, showCross: true } });

/** A slug suggested from a project name, as the backend derives one. */
export function suggestSlug(name: string): string {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 48).replace(/-+$/, "");
}

/** A Huly project key suggested from a name: the initials of its words, or the start of a single word. */
export function suggestKey(name: string): string {
  const words = name.toUpperCase().replace(/[^A-Z0-9]+/g, " ").trim().split(" ").filter(Boolean);
  const key = words.length > 1 ? words.map((w) => w[0]).join("") : (words[0] ?? "").slice(0, 4);
  return key.replace(/^[0-9]+/, "").slice(0, 5);
}

import { flushSync, mount, tick, unmount } from "svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import NewProject from "../src/components/NewProject.svelte";
import ProjectsPage from "../src/components/ProjectsPage.svelte";
import { ApiError } from "../src/lib/api";
import { formatRoute, parseRoute, suggestKey, suggestSlug } from "../src/lib/router";
import type { ProjectSummary } from "../src/lib/types";
import Harness from "./GraphHarness.svelte";
import { planDoc } from "./fixtures";

let app: ReturnType<typeof mount> | undefined;
afterEach(() => {
  if (app) unmount(app);
  app = undefined;
  document.body.innerHTML = "";
});

const settle = async () => { for (let i = 0; i < 5; i++) { await tick(); await Promise.resolve(); } flushSync(); };
const $ = <T extends Element = HTMLElement>(sel: string) => document.querySelector<T>(sel);
const $$ = (sel: string) => [...document.querySelectorAll<HTMLElement>(sel)];
const text = (sel: string) => $(sel)?.textContent?.replace(/\s+/g, " ").trim() ?? "";
const type = (el: HTMLInputElement, value: string) => { el.value = value; el.dispatchEvent(new Event("input", { bubbles: true })); flushSync(); };

function summary(slug: string, extra: Partial<ProjectSummary> = {}): ProjectSummary {
  return {
    id: 1, slug, name: `Project ${slug}`, huly_project: slug.slice(0, 3).toUpperCase(), store_path: `/home/x/projects/${slug}`,
    created_at: 0, valid: true, errors: 0, epics: 2, stories: 5, session_active: false,
    sortie: { reachable: true, dispatched: false }, ...extra,
  };
}

describe("router", () => {
  it("round-trips every place", () => {
    for (const hash of ["#/", "#/new", "#/p/billing", "#/p/billing/graph", "#/p/billing/graph?epic=billing&sel=billing%2Ftax&cross=0",
      "#/p/billing/graph?mark=m1"]) {
      expect(formatRoute(parseRoute(hash))).toBe(hash);
    }
    expect(parseRoute("")).toEqual({ name: "projects" });
    expect(parseRoute("#/nonsense/here")).toEqual({ name: "projects" });
    expect(parseRoute("#/p/billing/graph?epic=billing")).toMatchObject({ slug: "billing", page: "graph", view: { epic: "billing", selected: null, showCross: true } });
  });

  it("opens a project on its home, and keeps the graph one link away", () => {
    expect(parseRoute("#/p/billing")).toMatchObject({ name: "project", page: "home" });
    expect(parseRoute("#/p/billing/graph")).toMatchObject({ name: "project", page: "graph" });
    // A link from before the home existed still lands in the graph, where it pointed.
    expect(parseRoute("#/p/billing?epic=billing&sel=billing%2Ftax")).toMatchObject({ page: "graph", view: { epic: "billing", selected: "billing/tax" } });
    expect(formatRoute(parseRoute("#/p/billing?epic=billing"))).toBe("#/p/billing/graph?epic=billing");
  });

  it("suggests a slug and a Huly key from a name", () => {
    expect(suggestSlug("Billing v2!")).toBe("billing-v2");
    expect(suggestKey("Billing")).toBe("BILL");
    expect(suggestKey("Customer onboarding flow")).toBe("COF");
    expect(suggestKey("2024 roadmap")).toBe("R");
    expect(suggestKey("")).toBe("");
  });
});

describe("projects page", () => {
  function render(projects: ProjectSummary[], overrides: Record<string, unknown> = {}) {
    const client = {
      projects: vi.fn(async () => ({ projects })),
      renameProject: vi.fn(async (slug: string, name: string) => ({ project: { ...projects.find((p) => p.slug === slug)!, name } })),
      deleteProject: vi.fn(async (slug: string) => ({ deleted: slug, store_path: `/home/x/projects/${slug}`, huly_project: "BIL" })),
      ...overrides,
    };
    app = mount(ProjectsPage, { target: document.body, props: { client } });
    return client;
  }

  it("lists each project with its facts and links to it", async () => {
    render([summary("billing", { session_active: true, sortie: { reachable: true, dispatched: true } }), summary("ops", { valid: false, errors: 3 })]);
    await settle();
    expect($$(".row .name").map((a) => a.getAttribute("href"))).toEqual(["#/p/billing", "#/p/ops"]);
    expect(text(".strip")).toBe("2 projects · 1 planning session open");
    const [billing, ops] = $$(".row");
    expect(billing.textContent).toContain("Planning session open");
    expect(billing.textContent).toContain("Agents dispatched");
    expect(ops.textContent).toContain("3 problems");
    expect(ops.textContent).toContain("Agents not dispatched");
    expect(text(".crumbs [aria-current=page]")).toBe("Projects");
    expect($(".crumbs button")).toBeNull();
  });

  it("shows how to start when there are no projects", async () => {
    render([]);
    await settle();
    expect(text(".empty h1")).toBe("No projects yet");
    expect($(".empty a")?.getAttribute("href")).toBe("#/new");
  });

  it("renames in place", async () => {
    const client = render([summary("billing")]);
    await settle();
    $<HTMLButtonElement>(".actions .small")!.click();
    await settle();
    const input = $<HTMLInputElement>("#rename-billing")!;
    type(input, "Billing 2");
    $<HTMLFormElement>(".rename")!.requestSubmit();
    await settle();
    expect(client.renameProject).toHaveBeenCalledWith("billing", "Billing 2");
    expect(text(".row .name")).toBe("Billing 2");
  });

  it("removes only after a confirmation that says what is kept", async () => {
    const client = render([summary("billing", { session_active: true })]);
    await settle();
    $$(".actions .small")[1].click();
    await settle();
    expect(text(".confirm")).toContain("Its planning session ends.");
    expect(text(".confirm")).toContain("/home/x/projects/billing");
    expect(client.deleteProject).not.toHaveBeenCalled();
    $<HTMLButtonElement>(".confirm .danger")!.click();
    await settle();
    expect(client.deleteProject).toHaveBeenCalledWith("billing");
    expect($$(".row")).toHaveLength(0);
    expect(text(".notice")).toContain("still at /home/x/projects/billing");
  });
});

describe("new project form", () => {
  it("fills slug and key from the name until the person edits them", async () => {
    const createProject = vi.fn(async (body: { name: string; slug: string; huly_project: string }) => ({
      project: summary(body.slug), tracker: { key: body.huly_project, name: body.name, url: null, exists: true, created: true, ready: true, dispatched: false, problems: [] },
    }));
    const oncreated = vi.fn();
    app = mount(NewProject, { target: document.body, props: { client: { createProject }, oncreated } });
    flushSync();
    type($<HTMLInputElement>("#np-name")!, "Customer Onboarding");
    expect($<HTMLInputElement>("#np-slug")!.value).toBe("customer-onboarding");
    expect($<HTMLInputElement>("#np-key")!.value).toBe("CO");

    type($<HTMLInputElement>("#np-key")!, "onb");
    expect($<HTMLInputElement>("#np-key")!.value).toBe("ONB");
    type($<HTMLInputElement>("#np-name")!, "Customer Onboarding v2");
    expect($<HTMLInputElement>("#np-key")!.value).toBe("ONB");
    expect($<HTMLInputElement>("#np-slug")!.value).toBe("customer-onboarding-v2");

    $<HTMLFormElement>("form")!.requestSubmit();
    await settle();
    expect(createProject).toHaveBeenCalledWith({ name: "Customer Onboarding v2", slug: "customer-onboarding-v2", huly_project: "ONB" });
    expect(oncreated).toHaveBeenCalledOnce();
  });

  it("puts a refusal next to the field it names", async () => {
    const createProject = vi.fn(async () => {
      throw new ApiError(409, "slug_taken", "a project already uses the slug billing", { error: { code: "slug_taken", message: "a project already uses the slug billing", field: "slug" } });
    });
    app = mount(NewProject, { target: document.body, props: { client: { createProject }, oncreated: vi.fn() } });
    flushSync();
    type($<HTMLInputElement>("#np-name")!, "Billing");
    $<HTMLFormElement>("form")!.requestSubmit();
    await settle();
    expect(text("#np-slug-err")).toBe("a project already uses the slug billing");
    expect($("#np-slug")!.getAttribute("aria-invalid")).toBe("true");
    expect($(".form-err")).toBeNull();
  });
});

describe("graph breadcrumb", () => {
  it("names the project as the current level and links back to the projects", () => {
    app = mount(Harness, { target: document.body, props: { initial: planDoc() } });
    flushSync();
    expect($(".crumbs a.up")?.getAttribute("href")).toBe("#/");
    expect($(".crumbs [aria-current=page]")?.tagName).toBe("SPAN");
    expect($(".crumbs button")).toBeNull();
  });
});

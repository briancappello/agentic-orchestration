import { flushSync, mount, tick, unmount } from "svelte";
import { afterEach, describe, expect, it } from "vitest";
import Login from "../src/components/Login.svelte";
import UserMenu from "../src/components/UserMenu.svelte";
import { can, session } from "../src/lib/identity.svelte";

let app: ReturnType<typeof mount> | undefined;
afterEach(() => {
  if (app) unmount(app);
  app = undefined;
  document.body.innerHTML = "";
  session.identity = null;
  session.about = null;
});

const settle = async () => { await tick(); flushSync(); };

describe("sign in", () => {
  it("links to the provider in OIDC mode, returning to the open page", async () => {
    location.hash = "#/p/billing";
    app = mount(Login, { target: document.body, props: { mode: "oidc", onsignedin: () => {} } });
    await settle();
    const a = document.querySelector<HTMLAnchorElement>("a.button")!;
    expect(a.textContent).toBe("Sign in");
    expect(a.getAttribute("href")).toBe("/api/auth/login?next=" + encodeURIComponent("/#/p/billing"));
    expect(document.querySelector("input[type=password]")).toBeNull();
  });

  it("keeps the password form in local mode", async () => {
    app = mount(Login, { target: document.body, props: { mode: "local", onsignedin: () => {} } });
    await settle();
    expect(document.querySelector("input[type=password]")).not.toBeNull();
    expect(document.body.textContent).toContain("Local mode");
  });

  it("says why a sign-in was refused, including having no role", async () => {
    app = mount(Login, { target: document.body, props: { mode: "oidc", error: "no_role", onsignedin: () => {} } });
    await settle();
    expect(document.querySelector('[role="alert"]')?.textContent).toContain("no role in the plan workbench");
  });
});

describe("user menu", () => {
  it("shows the person and a sign-out control", async () => {
    session.identity = { name: "Ana Ruiz", email: "ana@example.com", roles: ["planner"], id: "iss|ana" };
    app = mount(UserMenu, { target: document.body });
    await settle();
    expect(document.querySelector(".name")?.textContent).toBe("Ana Ruiz");
    expect(document.querySelector("button.out")?.textContent).toBe("Sign out");
  });

  it("can() follows the roles", () => {
    expect(can("planner")).toBe(false);
    session.identity = { name: "Ana", email: "", roles: ["planner"], id: "x" };
    expect(can("planner")).toBe(true);
    expect(can("approver")).toBe(false);
    session.identity = { name: "Bo", email: "", roles: ["planner", "approver"], id: "y" };
    expect(can("approver")).toBe(true);
  });
});

describe("source code", () => {
  const about = { license: "AGPL-3.0-or-later", source_url: "https://git.example.com/workbench" };

  it("is offered before signing in, once the backend says where it is", async () => {
    app = mount(Login, { target: document.body, props: { mode: "local", onsignedin: () => {} } });
    await settle();
    expect(document.querySelector(".source")).toBeNull();
    session.about = about;
    await settle();
    const a = document.querySelector<HTMLAnchorElement>(".source a")!;
    expect(a.getAttribute("href")).toBe(about.source_url);
    expect(document.querySelector(".source")?.textContent).toContain("AGPL-3.0-or-later");
  });

  it("is offered in the user menu", async () => {
    session.identity = { name: "Ana", email: "", roles: ["planner"], id: "x" };
    session.about = about;
    app = mount(UserMenu, { target: document.body });
    await settle();
    const a = document.querySelector<HTMLAnchorElement>("a.out")!;
    expect(a.textContent).toBe("Source");
    expect(a.getAttribute("href")).toBe(about.source_url);
  });
});

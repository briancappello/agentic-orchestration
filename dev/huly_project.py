"""Ensure, or empty, the Huly project the dev stack plans into.

Usage: huly_project.py <front-url> <workspace> <email> <password> <identifier> [--reset | --remove]

Prints a login token on stdout. Creates the project (a classic project) when
it does not exist. Gives the project's space type what the plan workflow
needs: the task types Epic and Story, and the status In Review (Sortie's
handoff state) in every task type. Every step checks first, so a run on a
set-up workspace changes nothing; huly_clean_check.py proves both from a
clean slate. A space type is shared: the change applies to every project of
that type. With --reset, removes every issue in the project. With --remove, removes its
issues and then the project itself, as Huly's own "delete project" does
(archive, then remove), and prints nothing. Standard library only.
"""

from __future__ import annotations

import binascii
import json
import os
import sys
import time
import urllib.request


def post(url: str, body: dict, token: str | None = None) -> dict:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read() or b"null")


def get(url: str, token: str | None = None) -> dict:
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + token} if token else {})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def gen_id() -> str:
    return binascii.hexlify(int(time.time()).to_bytes(4, "big") + os.urandom(8)).decode()


# What the plan workflow needs in the project's space type. A change to a
# space type applies to every project of that type.
PLAN_TASK_TYPES = ("Epic", "Story")
# The handoff state: where a story waits for its pull request to merge.
# Sortie's plan control needs a state that is neither active, terminal, nor
# the backlog state; the classic workflow has none.
HANDOFF = {"name": "In Review", "category": "task:statusCategory:Active", "after": "task:statusCategory:Active"}
ISSUE_STATUS_ATTR = "tracker:attribute:IssueStatus"


def ensure_space_type(find, tx, type_id: str) -> None:
    """Give the space type the plan task types and the handoff state, as the
    Settings pages would. Each step checks first, so a second run changes nothing."""
    model = "core:space:Model"
    ptype = find("task:class:ProjectType", {"_id": type_id})[0]
    task_types = find("task:class:TaskType", {"parent": type_id})
    names = {t["name"].lower() for t in task_types}
    base = next((t for t in task_types if t["ofClass"] == "tracker:class:Issue"), None)
    if base is None:
        sys.exit(f"huly_project: space type {type_id} has no issue task type to copy")

    for name in PLAN_TASK_TYPES:
        if name.lower() in names:
            continue
        # The settings page's "+ task type": a mixin of tracker:class:Issue for
        # the type's custom fields, then the task type, with the issue type's statuses.
        mixin, tt = gen_id(), gen_id()
        tx("core:class:TxCreateDoc", "core:class:Class", mixin, model, attributes={
            "extends": "tracker:class:Issue", "kind": 2, "label": f"embedded:embedded:{name}", "icon": "tracker:icon:Issue"})
        doc = {k: base[k] for k in ("descriptor", "icon", "kind", "ofClass", "statusCategories", "statusClass", "statuses")}
        tx("core:class:TxCreateDoc", "task:class:TaskType", tt, model, attributes={
            **doc, "name": name, "parent": type_id, "targetClass": mixin, "allowedAsChildOf": []})
        task_types.append({**doc, "_id": tt, "name": name})
        ptype["tasks"] = [*ptype["tasks"], tt]
        tx("core:class:TxUpdateDoc", "task:class:ProjectType", type_id, model, operations={"tasks": ptype["tasks"]})
        print(f"added task type {name} to space type {ptype['name']}", file=sys.stderr)

    # The handoff state: one status document, in every task type of the space type.
    query = {"name": HANDOFF["name"], "ofAttribute": ISSUE_STATUS_ATTR, "category": HANDOFF["category"]}
    found = find("tracker:class:IssueStatus", query)
    if found:
        status = found[0]["_id"]
    else:
        status = gen_id()
        tx("core:class:TxCreateDoc", "tracker:class:IssueStatus", status, model, attributes=dict(query))
        print(f"created status {HANDOFF['name']}", file=sys.stderr)
    categories = {s["_id"]: s.get("category") for s in find("tracker:class:IssueStatus", {})}
    changed = False
    for tt in task_types:
        if tt.get("statusClass") != "tracker:class:IssueStatus" or status in tt["statuses"]:
            continue
        # After the last status of its category, where the settings page puts it.
        idx = max((i for i, s in enumerate(tt["statuses"]) if categories.get(s) == HANDOFF["after"]), default=len(tt["statuses"]) - 1)
        tt["statuses"] = [*tt["statuses"][: idx + 1], status, *tt["statuses"][idx + 1:]]
        tx("core:class:TxUpdateDoc", "task:class:TaskType", tt["_id"], model, operations={"statuses": tt["statuses"]})
        changed = True
        print(f"added status {HANDOFF['name']} to task type {tt['name']}", file=sys.stderr)

    # The space type lists each (status, task type) pair once, keeping what it already holds.
    have = {(s["_id"], s["taskType"]): s for s in ptype["statuses"]}
    by_id = {t["_id"]: t for t in task_types}
    want = [have.get((s, t), {"_id": s, "taskType": t}) for t in ptype["tasks"] if t in by_id for s in by_id[t]["statuses"]]
    if changed or want != ptype["statuses"]:
        tx("core:class:TxUpdateDoc", "task:class:ProjectType", type_id, model, operations={"statuses": want})


def main() -> int:
    front, workspace, email, password, ident = sys.argv[1:6]
    reset = "--reset" in sys.argv[6:]
    remove = "--remove" in sys.argv[6:]
    front = front.rstrip("/")

    cfg = get(front + "/config.json")
    accounts = cfg["ACCOUNTS_URL"] if cfg["ACCOUNTS_URL"].startswith("http") else front + cfg["ACCOUNTS_URL"]
    token = post(accounts, {"method": "login", "params": {"email": email, "password": password}})["result"]["token"]
    login = post(accounts, {"method": "selectWorkspace", "params": {"workspaceUrl": workspace, "kind": "external"}}, token)["result"]
    if login.get("workspaceUrl") != workspace:
        sys.exit(f"huly_project: workspace {workspace!r} not found")
    ep = login["endpoint"].replace("ws://", "http://").replace("wss://", "https://")
    ep = ep if ep.startswith("http") else front + ep
    ws, wt = login["workspace"], login["token"]
    acct = get(f"{ep}/api/v1/account/{ws}", wt)
    me = acct["primarySocialId"]

    def find(cls: str, query: dict) -> list[dict]:
        return post(f"{ep}/api/v1/find-all/{ws}", {"_class": cls, "query": query, "options": {}}, wt)["value"]

    def tx(kind: str, cls: str, obj: str, space: str, **extra) -> None:
        t = {"_id": gen_id(), "_class": kind, "space": "core:space:Tx", "objectId": obj, "objectClass": cls,
             "objectSpace": space, "modifiedOn": int(time.time() * 1000), "modifiedBy": me, **extra}
        post(f"{ep}/api/v1/tx/{ws}", t, wt)

    projects = find("tracker:class:Project", {"identifier": {"$in": [ident]}})
    if remove:
        if not projects:
            print(f"no Huly project {ident}", file=sys.stderr)
            return 0
        project = projects[0]["_id"]
        issues = find("tracker:class:Issue", {"space": {"$in": [project]}})
        issues.sort(key=lambda i: -len(i.get("parents") or []))
        for issue in issues:
            tx("core:class:TxRemoveDoc", "tracker:class:Issue", issue["_id"], project)
        tx("core:class:TxUpdateDoc", "tracker:class:Project", project, "core:space:Space", operations={"archived": True})
        tx("core:class:TxRemoveDoc", "tracker:class:Project", project, "core:space:Space")
        print(f"removed Huly project {ident} and its {len(issues)} issues", file=sys.stderr)
        return 0
    if projects:
        project = projects[0]["_id"]
    else:
        project = gen_id()
        tx("core:class:TxCreateDoc", "tracker:class:Project", project, "core:space:Space", createdBy=me, attributes={
            "name": f"Plan workbench dev ({ident})", "description": "Scratch project for plan workbench development.",
            "private": False, "archived": False, "autoJoin": True, "members": [acct["uuid"]], "owners": [acct["uuid"]],
            "identifier": ident, "sequence": 0, "defaultIssueStatus": "tracker:status:Backlog",
            "defaultTimeReportDay": "PreviousWorkDay", "type": "tracker:ids:ClassingProjectType",
        })
        print(f"created Huly project {ident}", file=sys.stderr)

    project_type = find("tracker:class:Project", {"_id": project})[0]["type"]
    ensure_space_type(find, tx, project_type)

    if reset:
        issues = find("tracker:class:Issue", {"space": {"$in": [project]}})
        # Children first, so no sub-issue is left pointing at a removed parent.
        issues.sort(key=lambda i: -len(i.get("parents") or []))
        for issue in issues:
            tx("core:class:TxRemoveDoc", "tracker:class:Issue", issue["_id"], project)
        tx("core:class:TxUpdateDoc", "tracker:class:Project", project, "core:space:Space", operations={"sequence": 0})
        print(f"removed {len(issues)} issues from Huly project {ident}", file=sys.stderr)

    print(token)
    return 0


if __name__ == "__main__":
    sys.exit(main())

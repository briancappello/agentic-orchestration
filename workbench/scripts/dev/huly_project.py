"""Ensure, or empty, the Huly project the dev stack plans into.

Usage: huly_project.py <front-url> <workspace> <email> <password> <identifier> [--reset]

Prints a login token on stdout. Creates the project (a classic project, so
it has the Epic and Story task types the dev workflow names) when it does
not exist. With --reset, removes every issue in it. Standard library only.
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


def main() -> int:
    front, workspace, email, password, ident = sys.argv[1:6]
    reset = "--reset" in sys.argv[6:]
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

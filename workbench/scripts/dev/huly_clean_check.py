"""Check that huly_project.py sets up Huly from a clean slate, and is idempotent.

Usage: huly_clean_check.py <front-url> <email> <password>

Creates a throwaway workspace (only the stock space types), runs
huly_project.py on it twice, checks that the space type then has the Epic and
Story task types and the In Review status in each task type, and that the
second run changed nothing. Deletes the workspace at the end. Standard
library only.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import huly_project as h

HERE = Path(__file__).parent


def login(front: str, email: str, password: str) -> tuple[str, str]:
    cfg = h.get(front + "/config.json")
    accounts = cfg["ACCOUNTS_URL"] if cfg["ACCOUNTS_URL"].startswith("http") else front + cfg["ACCOUNTS_URL"]
    token = h.post(accounts, {"method": "login", "params": {"email": email, "password": password}})["result"]["token"]
    return accounts, token


def main() -> int:
    front, email, password = (a.rstrip("/") for a in sys.argv[1:4])
    accounts, token = login(front, email, password)
    name = f"pw-clean-{int(time.time())}"
    created = h.post(accounts, {"method": "createWorkspace", "params": {"workspaceName": name}}, token)
    if "result" not in created:
        sys.exit(f"could not create a workspace: {created}")
    url = created["result"]["workspaceUrl"]
    print(f"workspace {url}", file=sys.stderr)
    try:
        # The workspace service fills a new workspace in the background.
        for _ in range(120):
            info = h.post(accounts, {"method": "selectWorkspace", "params": {"workspaceUrl": url, "kind": "external"}}, token)
            if info.get("result", {}).get("endpoint"):
                ep = info["result"]["endpoint"].replace("ws://", "http://")
                ep = ep if ep.startswith("http") else front + ep
                try:
                    h.post(f"{ep}/api/v1/find-all/{info['result']['workspace']}",
                           {"_class": "task:class:ProjectType", "query": {}, "options": {}}, info["result"]["token"])
                    break
                except Exception:
                    pass
            time.sleep(2)
        else:
            sys.exit("the workspace did not become ready")

        runs = []
        for _ in range(2):
            r = subprocess.run([sys.executable, str(HERE / "huly_project.py"), front, url, email, password, "CLN"],
                               capture_output=True, text=True)
            if r.returncode:
                sys.exit(f"huly_project.py failed: {r.stderr}")
            runs.append(r.stderr)
        print("first run:\n" + runs[0], file=sys.stderr)

        res = info["result"]
        ep = res["endpoint"].replace("ws://", "http://")
        ep = ep if ep.startswith("http") else front + ep

        def find(cls, q):
            return h.post(f"{ep}/api/v1/find-all/{res['workspace']}", {"_class": cls, "query": q, "options": {}}, res["token"])["value"]

        ptype = find("tracker:class:Project", {"identifier": "CLN"})[0]["type"]
        tts = find("task:class:TaskType", {"parent": ptype})
        review = find("tracker:class:IssueStatus", {"name": "In Review"})
        problems = []
        if {t["name"] for t in tts} < {"Issue", "Epic", "Story"}:
            problems.append(f"task types: {[t['name'] for t in tts]}")
        if len(review) != 1:
            problems.append(f"In Review statuses: {len(review)}")
        else:
            for t in tts:
                if review[0]["_id"] not in t["statuses"]:
                    problems.append(f"{t['name']} lacks In Review")
            pairs = {(s["_id"], s["taskType"]) for s in find("task:class:ProjectType", {"_id": ptype})[0]["statuses"]}
            for t in tts:
                if (review[0]["_id"], t["_id"]) not in pairs:
                    problems.append(f"space type lacks In Review for {t['name']}")
        if "added" in runs[1] or "created status" in runs[1]:
            problems.append(f"second run changed something: {runs[1]}")
        if problems:
            print("FAIL: " + "; ".join(problems))
            return 1
        print("OK: Epic, Story, and In Review set up from a clean slate; a second run changed nothing")
        return 0
    finally:
        ws_token = h.post(accounts, {"method": "selectWorkspace", "params": {"workspaceUrl": url, "kind": "external"}}, token)
        h.post(accounts, {"method": "deleteWorkspace", "params": {}}, ws_token["result"]["token"])
        print(f"deleted workspace {url}", file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())

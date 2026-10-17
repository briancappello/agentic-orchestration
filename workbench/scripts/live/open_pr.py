"""The live run's after_run hook: commit the agent's work, push the story's
branch, open its pull request (or find the open one), and write
.sortie/scm.json so Sortie's merge-completion reaction watches it.

Runs in the issue's workspace. Reads SORTIE_ISSUE_IDENTIFIER and the
SORTIE_LIVE_GITEA_* variables live.sh exports (hooks see SORTIE_* only).
The token goes into one git command's header, never into the checkout.
Standard library only.
"""

from __future__ import annotations

import base64
import datetime
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ident = os.environ["SORTIE_ISSUE_IDENTIFIER"]
url = os.environ["SORTIE_LIVE_GITEA_URL"].rstrip("/")
project = os.environ["SORTIE_LIVE_GITEA_PROJECT"]
token = os.environ["SORTIE_LIVE_GITEA_TOKEN"]
owner, repo = project.split("/", 1)
branch = f"sortie/{ident}"


def git(*args: str, check: bool = True) -> str:
    return subprocess.run(["git", *args], check=check, capture_output=True, text=True).stdout.strip()


def api(method: str, path: str, body: dict | None = None):
    req = urllib.request.Request(f"{url}/api/v1{path}", method=method, data=json.dumps(body).encode() if body else None,
                                 headers={"Authorization": f"token {token}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read() or b"null")


def main() -> int:
    git("add", "-A")
    if subprocess.run(["git", "diff", "--cached", "--quiet"]).returncode:
        git("commit", "-qm", f"{ident}: changes from Sortie's agent")
    if not git("rev-list", "origin/main..HEAD"):
        print(f"open_pr: {ident} has no commits over main; nothing to propose")
        return 0
    basic = base64.b64encode(f"{owner}:{token}".encode()).decode()
    git("-c", f"http.extraHeader=Authorization: Basic {basic}", "push", "-q", "--force-with-lease", "origin", f"HEAD:refs/heads/{branch}")

    pr = next((p for p in api("GET", f"/repos/{project}/pulls?state=open&limit=50") if p["head"]["ref"] == branch), None)
    if pr is None:
        suggested = {}
        try:
            suggested = json.loads(Path(".sortie/pr.json").read_text())
        except (OSError, ValueError):
            pass
        pr = api("POST", f"/repos/{project}/pulls", {
            "head": branch, "base": "main",
            "title": suggested.get("title") or git("log", "-1", "--format=%s"),
            "body": suggested.get("body") or f"Story {ident}, from Sortie's agent.",
        })
        print(f"open_pr: opened #{pr['number']} for {ident}")
    Path(".sortie").mkdir(exist_ok=True)
    Path(".sortie/scm.json").write_text(json.dumps({
        "pr_number": pr["number"], "owner": owner, "repo": repo, "branch": branch,
        "pushed_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (subprocess.CalledProcessError, urllib.error.URLError) as exc:
        detail = getattr(exc, "stderr", "") or getattr(exc, "reason", "") or exc
        print(f"open_pr: {exc}: {detail}", file=sys.stderr)
        sys.exit(1)

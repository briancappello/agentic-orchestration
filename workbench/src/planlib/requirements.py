"""Requirement names of a change, for checking ``covers`` refs.

OpenSpec is the authority on its spec format, but its JSON output (tested
with 1.13) carries each delta requirement's text and not its name. So the
names come from the ``### Requirement:`` headers of the change's delta specs,
and every header's requirement is cross-checked against ``openspec show
<change> --type change --json``: the same capabilities, the same number of
requirements, the same text, in the same order. Any disagreement is an error,
never a silent pass.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .store import CHANGES_DIR

# The OpenSpec version whose `show --json` output this module was tested with.
TESTED_OPENSPEC_VERSION = "1.13"

# Delta operations whose requirements exist in the change once it is applied.
_LIVE_OPERATIONS = ("ADDED", "MODIFIED")
_SECTION = re.compile(r"^##\s+(ADDED|MODIFIED|REMOVED|RENAMED)\s+Requirements\s*$")
_REQUIREMENT = re.compile(r"^###\s+Requirement:\s*(.+?)\s*$")
_RENAME_TO = re.compile(r"^\s*-?\s*TO:\s*`?###\s+Requirement:\s*(.+?)`?\s*$")
_FENCE = re.compile(r"^\s*(```|~~~)")


class RequirementsError(Exception):
    """OpenSpec could not be run, or its output did not have the expected shape."""


ShowRunner = Callable[[Path, str], Any]


@dataclass(frozen=True)
class _HeaderRequirement:
    operation: str
    name: str
    text: str


def openspec_show(store: Path, change: str) -> Any:
    """Run ``openspec show <change> --type change --json`` in the store."""
    cmd = ["openspec", "show", change, "--type", "change", "--json", "--no-interactive"]
    try:
        proc = subprocess.run(cmd, cwd=store, capture_output=True, text=True, timeout=60)
    except FileNotFoundError as exc:
        raise RequirementsError("openspec is not installed or not on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise RequirementsError(f"`{' '.join(cmd)}` timed out") from exc
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip().splitlines()
        raise RequirementsError(f"`{' '.join(cmd)}` failed: {detail[-1] if detail else proc.returncode}")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RequirementsError(f"`{' '.join(cmd)}` did not print JSON: {exc}") from exc


def requirement_names(store: Path, change: str, show: ShowRunner = openspec_show) -> dict[str, set[str]]:
    """Map each capability path in the change to its live requirement names.

    Raises ``RequirementsError`` when OpenSpec fails or disagrees with the
    delta spec headers.
    """
    headers = _read_headers(Path(store) / CHANGES_DIR / change / "specs")
    reported = _reported_texts(show(Path(store), change), change)

    problems: list[str] = []
    for capability in sorted(set(headers) | set(reported)):
        mine = [_norm(h.text) for h in headers.get(capability, []) if h.operation in _LIVE_OPERATIONS]
        theirs = reported.get(capability, [])
        if len(mine) != len(theirs):
            problems.append(
                f"{capability}: the delta spec has {len(mine)} added or modified requirements, "
                f"OpenSpec reports {len(theirs)}"
            )
            continue
        for i, (a, b) in enumerate(zip(mine, theirs)):
            if a != b and not (b and a.startswith(b)):
                name = [h.name for h in headers[capability] if h.operation in _LIVE_OPERATIONS][i]
                problems.append(f"{capability}: requirement '{name}' does not match OpenSpec's text for it")
    if problems:
        raise RequirementsError(
            "requirement headers disagree with `openspec show --json` "
            f"(tested with OpenSpec {TESTED_OPENSPEC_VERSION}): " + "; ".join(problems)
        )

    names: dict[str, set[str]] = {}
    for capability, items in headers.items():
        live = {h.name for h in items if h.operation in _LIVE_OPERATIONS}
        live |= {h.name for h in items if h.operation == "RENAMED"}
        names[capability] = live
    return names


def _reported_texts(payload: Any, change: str) -> dict[str, list[str]]:
    def shape(msg: str) -> RequirementsError:
        return RequirementsError(
            f"unexpected `openspec show {change} --type change --json` output "
            f"(tested with OpenSpec {TESTED_OPENSPEC_VERSION}): {msg}"
        )

    if not isinstance(payload, dict) or not isinstance(payload.get("deltas"), list):
        raise shape("no 'deltas' list")
    out: dict[str, list[str]] = {}
    for i, delta in enumerate(payload["deltas"]):
        if not isinstance(delta, dict):
            raise shape(f"delta {i} is not an object")
        spec, op = delta.get("spec"), delta.get("operation")
        if not isinstance(spec, str) or not isinstance(op, str):
            raise shape(f"delta {i} has no 'spec' or 'operation' string")
        if op not in _LIVE_OPERATIONS:
            continue
        req = delta.get("requirement")
        if not isinstance(req, dict) or not isinstance(req.get("text"), str):
            raise shape(f"delta {i} ({spec}) has no 'requirement.text' string")
        out.setdefault(spec, []).append(_norm(req["text"]))
    return out


def _read_headers(specs_dir: Path) -> dict[str, list[_HeaderRequirement]]:
    out: dict[str, list[_HeaderRequirement]] = {}
    if not specs_dir.is_dir():
        return out
    for spec in sorted(specs_dir.rglob("spec.md")):
        capability = spec.parent.relative_to(specs_dir).as_posix()
        out[capability] = list(_parse_delta(spec.read_text()))
    return out


def _parse_delta(text: str):
    section: str | None = None
    current: tuple[str, str] | None = None
    body: list[str] = []
    in_fence = False

    def flush():
        if current is not None:
            yield _HeaderRequirement(current[0], current[1], "\n".join(body))

    for line in text.splitlines():
        # OpenSpec leaves fenced code out of a requirement's text, and a header
        # inside a fence is not a header.
        if _FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = _SECTION.match(line)
        if m or (line.startswith("## ") and not line.startswith("### ")):
            yield from flush()
            current, body = None, []
            section = m.group(1) if m else None
            continue
        if section is None:
            continue
        if section == "RENAMED":
            r = _RENAME_TO.match(line)
            if r:
                yield _HeaderRequirement("RENAMED", r.group(1), "")
            continue
        m = _REQUIREMENT.match(line)
        if m:
            yield from flush()
            current, body = (section, m.group(1)), []
            continue
        if current is not None:
            if line.startswith("#### ") or line.startswith("### "):
                # Scenarios and anything after them are not part of the requirement text.
                yield from flush()
                current, body = None, []
                continue
            body.append(line)
    yield from flush()


def _norm(text: str) -> str:
    return " ".join(text.split())

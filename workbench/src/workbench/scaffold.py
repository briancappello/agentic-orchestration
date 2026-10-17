"""Create a project's empty spec store: the planning schemas, an empty plan, and git."""

from __future__ import annotations

import shutil
import subprocess
from importlib import resources
from pathlib import Path

PLAN_YAML = "# The order between changes. Format: openspec/schemas/planning/plan.schema.json\nschema_version: 1\nchanges: []\n"
CONFIG_YAML = "schema: spec-driven-planned\n"


class ScaffoldError(Exception):
    pass


def scaffold_store(root: Path, name: str) -> None:
    """Create the store at ``root``, which must not exist yet."""
    root = Path(root)
    if root.exists():
        raise ScaffoldError(f"{root} already exists")
    openspec = root / "openspec"
    template = resources.files("workbench").joinpath("store_template", "openspec", "schemas")
    try:
        (openspec / "changes").mkdir(parents=True)
        (openspec / "specs").mkdir()
        with resources.as_file(template) as src:
            shutil.copytree(src, openspec / "schemas")
        (openspec / "config.yaml").write_text(CONFIG_YAML)
        (openspec / "plan.yaml").write_text(PLAN_YAML)
        for d in ("changes", "specs"):
            (openspec / d / ".gitkeep").touch()
        _git(root, "init", "-q")
        _git(root, "add", "-A")
        _git(root, "-c", "user.name=plan workbench", "-c", "user.email=workbench@localhost",
             "commit", "-qm", f"Create the spec store for {name}")
    except BaseException:
        shutil.rmtree(root, ignore_errors=True)
        raise


def upgrade_schemas(root: Path) -> list[str]:
    """Bring the workbench's own schema files in an existing store up to the
    ones this workbench ships, and commit them. Only files the store already
    has are replaced: a store that never took the workbench's schemas keeps
    its own. Returns the paths it changed, relative to ``root``."""
    root = Path(root)
    dest = root / "openspec" / "schemas"
    if not dest.is_dir():
        return []
    template = resources.files("workbench").joinpath("store_template", "openspec", "schemas")
    changed: list[str] = []
    with resources.as_file(template) as src:
        for f in sorted(Path(src).rglob("*")):
            target = dest / f.relative_to(src)
            if f.is_file() and target.is_file() and target.read_bytes() != f.read_bytes():
                target.write_bytes(f.read_bytes())
                changed.append(str(target.relative_to(root)))
    if changed and (root / ".git").exists():
        _git(root, "add", "--", *changed)
        _git(root, "-c", "user.name=plan workbench", "-c", "user.email=workbench@localhost",
             "commit", "-qm", "Update the planning schemas", "--", *changed)
    return changed


def _git(cwd: Path, *args: str) -> None:
    try:
        subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise ScaffoldError("git is not installed") from exc
    except subprocess.CalledProcessError as exc:
        raise ScaffoldError(f"git {args[0]} failed: {exc.stderr.strip()}") from exc

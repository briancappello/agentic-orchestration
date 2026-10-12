from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Callable

import pytest
import yaml

FIXTURES = Path(__file__).parent / "fixtures"


class StoreBuilder:
    """Builds a throwaway spec store under a temp dir."""

    def __init__(self, root: Path):
        self.root = root
        schema_dir = root / "openspec" / "schemas" / "planning"
        schema_dir.mkdir(parents=True)
        for f in (FIXTURES / "schemas").glob("*.schema.json"):
            shutil.copy(f, schema_dir / f.name)
        (root / "openspec" / "changes").mkdir(parents=True)

    def plan(self, changes: list[tuple[str, list[str]]] | dict | str) -> Path:
        if isinstance(changes, list):
            changes = {
                "schema_version": 1,
                "changes": [{"name": n, "depends_on": d} for n, d in changes],
            }
        return self._write(self.root / "openspec" / "plan.yaml", changes)

    def change(self, name: str, breakdown: dict | str | None = None) -> Path:
        d = self.root / "openspec" / "changes" / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "proposal.md").write_text(f"## Why\n\n{name}\n")
        if breakdown is not None:
            self._write(d / "breakdown.yaml", breakdown)
        return d

    @staticmethod
    def _write(path: Path, content: Any) -> Path:
        text = content if isinstance(content, str) else yaml.safe_dump(content, sort_keys=False)
        path.write_text(text)
        return path


def deliverable(id: str, depends_on: list[str] | None = None, covers: list[str] | None = None, **extra) -> dict:
    d = {
        "id": id,
        "title": extra.pop("title", f"Do {id}"),
        "kind": extra.pop("kind", "story"),
        "depends_on": depends_on or [],
        "covers": covers or [],
        "acceptance_criteria": extra.pop("acceptance_criteria", [f"{id} works"]),
    }
    d.update(extra)
    return d


def breakdown(*deliverables: dict, **top) -> dict:
    doc = {"schema_version": 1, "status": "draft", "deliverables": list(deliverables)}
    doc.update(top)
    return doc


@pytest.fixture
def store(tmp_path: Path) -> StoreBuilder:
    return StoreBuilder(tmp_path / "store")


@pytest.fixture
def make_store(tmp_path: Path) -> Callable[[str], StoreBuilder]:
    def make(name: str) -> StoreBuilder:
        return StoreBuilder(tmp_path / name)

    return make

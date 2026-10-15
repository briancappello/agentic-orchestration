"""The project registry: which projects exist, in SQLite.

Plans themselves live in each project's spec store, a git repository the
planning agent edits. The registry records only the projects: a slug that
names the project in URLs and on disk, a display name, the tracker project
it syncs into, and where its store is.
"""

from __future__ import annotations

import re
import sqlite3
import threading
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from importlib import resources
from pathlib import Path
from typing import Iterator

SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,47}$")
TRACKER_KEY = re.compile(r"^[A-Z][A-Z0-9]{0,4}$")
MAX_NAME = 80


class RegistryError(Exception):
    """A request the registry refuses; ``code`` names the reason for the API."""

    def __init__(self, status: int, code: str, message: str, field: str | None = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.field = field


@dataclass(frozen=True)
class Project:
    id: int
    slug: str
    name: str
    huly_project: str
    store_path: str
    created_at: int

    def store(self, home: Path) -> Path:
        """The store's directory; a relative path is under the workbench home."""
        p = Path(self.store_path)
        return p if p.is_absolute() else home / p

    def to_dict(self) -> dict:
        return asdict(self)


def check_new(slug: str, name: str, huly_project: str) -> tuple[str, str, str]:
    """Normalize and check the fields of a new project."""
    slug, name, huly_project = slug.strip(), " ".join(name.split()), huly_project.strip()
    if not name:
        raise RegistryError(400, "invalid_name", "a project needs a name", "name")
    if len(name) > MAX_NAME:
        raise RegistryError(400, "invalid_name", f"the name is longer than {MAX_NAME} characters", "name")
    if not SLUG.match(slug) or slug.endswith("-"):
        raise RegistryError(400, "invalid_slug",
                            "the slug is lower-case letters, digits and dashes, starts with a letter or digit, "
                            "and is at most 48 characters", "slug")
    if not TRACKER_KEY.match(huly_project):
        raise RegistryError(400, "invalid_huly_project",
                            "the Huly project key is a capital letter, then up to four capital letters or digits",
                            "huly_project")
    return slug, name, huly_project


def suggest_slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s[:48].rstrip("-")


def _migrations() -> list[tuple[int, str]]:
    out = []
    for entry in resources.files("workbench").joinpath("sql").iterdir():
        m = re.match(r"^(\d+)_.*\.sql$", entry.name)
        if m:
            out.append((int(m.group(1)), entry.read_text()))
    return sorted(out)


class Registry:
    """Thread-safe access to the registry database."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._db = self._connect()
        self._db.execute("PRAGMA journal_mode=WAL")
        self._migrate()

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=60, check_same_thread=False, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def _migrate(self) -> None:
        with self._lock:
            current = self._db.execute("PRAGMA user_version").fetchone()[0]
            for version, sql in _migrations():
                if version <= current:
                    continue
                self._db.execute("BEGIN IMMEDIATE")
                try:
                    for stmt in _statements(sql):
                        self._db.execute(stmt)
                    self._db.execute(f"PRAGMA user_version={version}")
                    self._db.execute("COMMIT")
                except BaseException:
                    self._db.execute("ROLLBACK")
                    raise

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def list(self) -> list[Project]:
        with self._lock:
            rows = self._db.execute("SELECT * FROM projects ORDER BY lower(name), slug").fetchall()
        return [Project(**dict(r)) for r in rows]

    def get(self, slug: str) -> Project | None:
        with self._lock:
            row = self._db.execute("SELECT * FROM projects WHERE slug = ?", (slug,)).fetchone()
        return Project(**dict(row)) if row else None

    def by_store(self, store_path: str) -> Project | None:
        with self._lock:
            row = self._db.execute("SELECT * FROM projects WHERE store_path = ?", (store_path,)).fetchone()
        return Project(**dict(row)) if row else None

    def rename(self, slug: str, name: str) -> Project:
        name = " ".join(name.split())
        if not name or len(name) > MAX_NAME:
            raise RegistryError(400, "invalid_name", f"a name is 1 to {MAX_NAME} characters", "name")
        with self._lock:
            cur = self._db.execute("UPDATE projects SET name = ? WHERE slug = ?", (name, slug))
        if cur.rowcount == 0:
            raise RegistryError(404, "project_not_found", f"no project {slug}")
        return self.get(slug)  # type: ignore[return-value]

    def delete(self, slug: str) -> None:
        with self._lock:
            self._db.execute("DELETE FROM projects WHERE slug = ?", (slug,))

    @contextmanager
    def reserve(self, slug: str, name: str, huly_project: str, store_path: str) -> Iterator[Project]:
        """Insert a project in an open transaction, yield it, and commit when
        the block finishes; an exception rolls the insert back. The row holds
        the slug, the tracker key and the store path from the moment it is
        inserted, so a concurrent create of the same values waits, then fails."""
        db = self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            try:
                cur = db.execute(
                    "INSERT INTO projects (slug, name, huly_project, store_path, created_at) VALUES (?, ?, ?, ?, ?)",
                    (slug, name, huly_project, store_path, int(time.time())),
                )
            except sqlite3.IntegrityError as exc:
                db.execute("ROLLBACK")
                raise _conflict(str(exc), slug, huly_project) from exc
            project = Project(cur.lastrowid, slug, name, huly_project, store_path, int(time.time()))
            try:
                yield project
            except BaseException:
                db.execute("ROLLBACK")
                raise
            db.execute("COMMIT")
        finally:
            db.close()


def _conflict(message: str, slug: str, huly_project: str) -> RegistryError:
    if "projects.slug" in message:
        return RegistryError(409, "slug_taken", f"a project already uses the slug {slug}", "slug")
    if "projects.huly_project" in message:
        return RegistryError(409, "huly_project_taken", f"a project already syncs into Huly project {huly_project}", "huly_project")
    if "projects.store_path" in message:
        return RegistryError(409, "store_taken", "a project already uses that store", "slug")
    return RegistryError(400, "invalid_project", message)


def _statements(sql: str) -> list[str]:
    """Split a migration into statements; migrations hold no literal semicolons."""
    lines = [ln for ln in sql.splitlines() if not ln.strip().startswith("--")]
    return [s.strip() for s in "\n".join(lines).split(";") if s.strip()]

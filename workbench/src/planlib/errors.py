"""Validation problems, collected rather than raised."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class PlanError:
    """One problem found in the store's planning files.

    ``file`` is relative to the store root. ``change`` and ``deliverable`` name
    what the problem is about when it is about something specific; ``members``
    lists every plan key involved when there are several (a cycle, for example).
    """

    code: str
    message: str
    file: str | None = None
    change: str | None = None
    deliverable: str | None = None
    members: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        d = asdict(self)
        d["members"] = list(self.members)
        return d

    def __str__(self) -> str:
        where = self.file or "-"
        subject = ""
        if self.change and self.deliverable:
            subject = f" [{self.change}/{self.deliverable}]"
        elif self.change:
            subject = f" [{self.change}]"
        return f"{where}{subject}: {self.code}: {self.message}"


class PlanLoadError(Exception):
    """Raised when the store itself cannot be used (missing or unsupported schemas)."""

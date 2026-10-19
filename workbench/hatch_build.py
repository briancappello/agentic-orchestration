"""Bundle the built frontend and the planning prompt into the wheel.

workbench.config.bundled finds them inside the installed package. An
editable install skips this: it runs from the source tree, where config
finds frontend/dist and prompts/ directly.
"""

from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version: str, build_data: dict) -> None:
        if version == "editable":
            return
        root = Path(self.root)
        dist = root / "frontend" / "dist"
        if not (dist / "index.html").is_file():
            raise RuntimeError("frontend/dist has no build: run `make wheel`, which builds the frontend first")
        build_data["force_include"][str(dist)] = "workbench/frontend"
        build_data["force_include"][str(root / "prompts" / "planning-session.md")] = "workbench/prompts/planning-session.md"

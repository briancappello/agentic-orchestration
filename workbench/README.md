# Plan workbench

Plan a software project as epics and stories, validate the plan, approve
it, and sync it to the tracker. Then watch and steer the coding agents that
Sortie runs on it.

This package holds two programs:

- `planlib`: validates an OpenSpec store's plan (`plan.yaml` and each
  change's `breakdown.yaml`) and builds its dependency graph.
- `workbench`: the web application. A FastAPI backend serves the Svelte
  frontend, reads the spec store, and talks to Sortie and to the agents'
  `acp-broker` sessions.

The [operator guide](docs/operator-guide.md) covers setup and every
setting.

## Develop

```sh
uv sync
uv run pytest
cd frontend && npm ci && npm run check && npm test
```

`make wheel` builds the frontend, then a wheel that serves it.

## License

AGPL-3.0-or-later. A workbench serves `/api/about`, and links to its
source from the sign-in page and the top bar. If you run a modified
workbench for others, set `WORKBENCH_SOURCE_URL` to your source.

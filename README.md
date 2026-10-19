# Agentic orchestration

A platform for running autonomous coding agents against tracker tickets,
and for the people who plan, watch, steer, and review that work.

## Components

| Directory | What it is | Language |
|---|---|---|
| `workbench/` | The plan workbench and `planlib`: plan a project as epics and stories, validate the plan, approve it, and sync it to the tracker. Watch and steer the agents that work on it. | Python, Svelte |
| `acp-broker/` | Sits between an orchestrator and an Agent Client Protocol (ACP) agent. One session, two inputs: the autonomous driver and people, who can watch, steer, take over, hand back, and answer permission requests. | Go |
| `smol-builder/` | Builds the smolvm machine images that agents run in. | Go |
| `specs/` | The OpenSpec store: the requirements of every component, and the record of each change. | Markdown |
| `docs/` | Documentation for the whole system. | Markdown |
| `dev/` | The development setup: runs every component locally against a local tracker and forge. | Shell, Python |
| `sortie/` | Git submodule: our fork of [Sortie](https://github.com/sortie-ai/sortie), the orchestrator. It is licensed separately, under Apache-2.0. | Go |

## License

Everything in this repository is licensed under the GNU Affero General
Public License, version 3 or later (AGPL-3.0-or-later). See `LICENSE`.

The `sortie/` submodule is a separate project, with its own license
(Apache-2.0).

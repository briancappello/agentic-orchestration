## 1. planlib

- [x] 1.1 Add `milestones.schema.json` to the shipped planning schemas and the test fixtures; load and validate `openspec/milestones.yaml` (references, cycles, one goal); test each error and a store without the file.
- [x] 1.2 Parse `tasks.md` items with their kinds (`[metal]`, `[operator]`, untagged); test the three kinds and ticked versus open.
- [x] 1.3 Compute milestone membership, progress (stories, agent tasks, person tasks), the goal, the next milestone and its critical path; test each `planning/milestones` scenario.

## 2. Backend

- [x] 2.1 Compute execution health from Sortie's state and the last sync (verdict, reasons, slots, runway); test each verdict.
- [x] 2.2 Compute "not ready to execute" with reasons and urgency; test the ordering scenario and each reason.
- [x] 2.3 Serve the home document (`GET /api/projects/<slug>/home`) and publish it on the project's event stream with the graph; test that it updates when a story finishes.

## 3. Frontend

- [x] 3.1 Route a project to its home, and give the graph its own address; deep links select a story and attach it to the planning chat.
- [x] 3.2 Build the timeline, the two focal points and milestone progress, with every state in `planning/project-home` (invalid plan, Sortie unreachable, no milestones file, done); tests for each.
- [x] 3.3 Mark changed stories briefly; honor reduced motion; check that no state relies on color alone.

## 4. Proof

- [x] 4.1 Write `openspec/milestones.yaml` for `ortus-nova-specs` (M0 to M4, M2 the goal) and tag its person tasks, as a spec store pull request. (M0 is declared `done: true`, design D1; M4 maps no change yet and is left out.)
- [ ] 4.2 Live: the stage-0 workbench home shows the homelab plan's milestones, progress, execution health and not-ready list, and they agree with the store and Sortie. (Checked with this build on a read-only workbench, `WORKBENCH_SYNC=0` on 127.0.0.1:8795, against the spec store branch and the stage-0 Sortie: every count matched an independent count of the store and Sortie's state. The stage-0 workbench shows it after its next deploy.)

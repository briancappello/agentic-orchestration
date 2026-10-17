# sortie/guest-repository-sync Specification

## Purpose
Moves git work into and out of a sandboxed environment without giving the guest git credentials or network access to the git host, and without the host ever running git on a repository the guest controls.

## Requirements

### Requirement: Repository configuration
With the `smolvm` kind, `environment.smolvm.repository` SHALL be optional. When present, it SHALL have:

- `url`: required
- `base`: required
- `branch_prefix`: defaults to `sortie/`
- `max_bundle_mib`: a positive integer, defaults to 512
- `provider` and `project`: optional, and `project` is required when `provider` is set

When `repository` is absent, Sortie SHALL neither seed nor export, and a run SHALL end without an export step.

#### Scenario: Provider without project
- **WHEN** `repository.provider` is `github` and `repository.project` is absent
- **THEN** validation fails with an error naming `environment.smolvm.repository.project`

### Requirement: A host-owned mirror
Sortie SHALL keep one bare mirror for each distinct `repository.url`, in its state directory and outside every workspace. Only Sortie SHALL write it. Every git command Sortie runs on the mirror SHALL disable hooks and the filesystem monitor, and SHALL check every received object. Sortie SHALL use the host's git credentials for the upstream. It SHALL NOT give those credentials to the guest.

#### Scenario: Planted hook in an exported branch
- **WHEN** an exported commit adds `.git/hooks`-style files or a `.gitattributes` filter to the repository
- **THEN** importing it into the mirror runs no hook and no filter on the host

### Requirement: The issue branch
The issue branch SHALL be `branch_prefix` followed by the workspace key. When that is not a valid git branch name, preparation SHALL fail with an error naming the branch.

#### Scenario: Default prefix
- **WHEN** the workspace key is `ENG-42`
- **THEN** the issue branch is `sortie/ENG-42`

### Requirement: Seeding a new workspace
When Sortie creates an issue's environment, and before `after_create` runs, it SHALL:

1. fetch the upstream into the mirror;
2. place in `/workspace` a clone that holds `origin/<base>`, and `origin/<issue branch>` when that branch exists upstream;
3. check out the issue branch, tracking `origin/<issue branch>` when it exists, or created at `origin/<base>` when it does not;
4. set `origin`'s URL to `repository.url`.

A failed upstream fetch SHALL fail preparation. Git data SHALL enter the guest only as a bundle, outside the workspace.

#### Scenario: New issue
- **WHEN** issue `ENG-42` is dispatched for the first time and `sortie/ENG-42` does not exist upstream
- **THEN** `after_create` runs in a `/workspace` whose current branch is `sortie/ENG-42`, at the same commit as `origin/main`

#### Scenario: Existing upstream branch
- **WHEN** `sortie/ENG-42` exists upstream with commit `abc123`
- **AND** the issue's environment is created
- **THEN** the guest's current branch is `sortie/ENG-42` at `abc123`

### Requirement: Refreshing before each run
Before each run in an existing environment, Sortie SHALL fetch the upstream into the mirror and update the guest's `origin/<base>` and `origin/<issue branch>` to the upstream state. It SHALL NOT change the guest's local branches, index, or work tree. When the upstream fetch fails, Sortie SHALL log a warning and refresh from the mirror's last state.

#### Scenario: Base moved between runs
- **WHEN** `main` gained a commit upstream since the last run
- **THEN** in the next run, the guest's `origin/main` contains that commit
- **AND** the guest's `sortie/ENG-42` and its uncommitted changes are unchanged

### Requirement: Export after each run
After every run that ends normally, and after `after_run`, Sortie SHALL export the guest's issue branch before any tracker handoff. The export SHALL:

- take the guest's committed `refs/heads/<issue branch>` as a bundle, read through the environment, outside the workspace and outside the shared control directory;
- refuse a bundle larger than `max_bundle_mib`;
- refuse a bundle naming any ref other than `refs/heads/<issue branch>`;
- import the branch only into the mirror.

When the issue branch is missing in the guest, or equals the upstream branch tip, or equals `origin/<base>` while no upstream branch exists, the export SHALL succeed without pushing. Uncommitted changes SHALL NOT be exported.

#### Scenario: Extra ref refused
- **WHEN** the guest's bundle also names `refs/heads/main`
- **THEN** the export fails with an error naming the unexpected ref
- **AND** the mirror's refs are unchanged

#### Scenario: Oversized bundle
- **WHEN** `max_bundle_mib` is 1 and the bundle is 5 MiB
- **THEN** the export fails with an error naming the limit

#### Scenario: Nothing committed
- **WHEN** the agent changed files but made no commit
- **THEN** the export succeeds without a push
- **AND** the changes are still in the guest workspace

### Requirement: Push without overwriting others
After importing new commits, Sortie SHALL push them to `refs/heads/<issue branch>` upstream. The push SHALL succeed only when the upstream branch is absent, if Sortie never pushed it, or still at the commit Sortie pushed last. A replacement of Sortie's own earlier push, such as after a rebase, SHALL be allowed. When the upstream branch moved since Sortie's last push, the export SHALL fail with `branch moved upstream`, and the upstream branch SHALL be unchanged.

#### Scenario: Agent rebased its branch
- **WHEN** Sortie last pushed `sortie/ENG-42` at `aaa111` and nobody changed it since
- **AND** the agent rebased the branch onto a newer `main`
- **THEN** the push replaces `aaa111` with the rebased commit

#### Scenario: Human pushed to the branch
- **WHEN** a human pushed `bbb222` onto `sortie/ENG-42` after Sortie's last push
- **AND** the agent's branch does not contain `bbb222`
- **THEN** the export fails with `branch moved upstream`
- **AND** `sortie/ENG-42` upstream is still at `bbb222`

### Requirement: Export gates the handoff
When any step of the export fails, Sortie SHALL report the run as failed with an export error, SHALL NOT transition the tracker issue, SHALL keep the environment and its workspace, and SHALL retry the issue with its normal backoff.

#### Scenario: Push rejected
- **WHEN** the push is rejected
- **THEN** the issue stays in its active state
- **AND** its VM and committed work remain for the retry

### Requirement: Sortie owns the SCM record
Under `smolvm` with `repository`, Sortie SHALL write the issue's SCM record in a host-only location that the guest cannot reach. The record holds `branch`, `sha`, `pushed_at`, and, when a pull request is known, `pr_number`, `owner`, and `repo`. Every reader of workspace SCM metadata SHALL use this record and ignore `.sortie/scm.json`. Each run history row SHALL record the commit exported by that run.

#### Scenario: Agent forges scm.json
- **WHEN** the agent writes `{"pr_number": 999}` to `/workspace/.sortie/scm.json`
- **THEN** CI and review reactions poll the pull request Sortie recorded, not 999

## Purpose

Lets Sortie open, or find, the pull request for an issue branch through the SCM adapter it already configures, so that an agent with no git credentials still ends its work in a reviewable pull request.

## ADDED Requirements

### Requirement: Ensure a pull request for a branch
The `github`, `gitlab`, and `gitea` SCM adapters SHALL each support ensuring a pull request (a merge request on GitLab) from a head branch to a base branch in a given repository. When an open pull request with that head already exists, the operation SHALL return it unchanged. Otherwise it SHALL create one with the given title and body. The result SHALL carry the pull request's number, its web URL, and whether it was created.

#### Scenario: First push opens a pull request
- **WHEN** no pull request exists from `sortie/ENG-42` to `main`
- **THEN** ensuring one creates it and reports it as created, with its number and URL

#### Scenario: Later push finds it
- **WHEN** an open pull request from `sortie/ENG-42` to `main` exists
- **THEN** ensuring one returns that pull request, reports it as not created, and leaves its title and body unchanged

### Requirement: Errors are normalized
Failures SHALL be reported with Sortie's SCM error kinds. A permission or scope failure SHALL be reported as an authentication error that names the scope the provider requires.

#### Scenario: Token without write scope
- **WHEN** the configured token can read but not create pull requests
- **THEN** the operation fails with an authentication error naming the missing scope

### Requirement: Sortie opens the pull request after a push
After Sortie pushes an issue branch, and when `environment.smolvm.repository.provider` is set, Sortie SHALL ensure the branch's pull request against `repository.base`, in the repository named by `repository.project`. It SHALL record the result in the issue's SCM record. A failure SHALL fail the export.

Validation SHALL fail when the provider differs from the provider of any active SCM reaction, or when its adapter cannot open pull requests.

#### Scenario: Provider mismatch
- **WHEN** `repository.provider` is `gitea` and `reactions.ci_failure.provider` is `github`
- **THEN** validation fails with an error naming both settings

### Requirement: Agent-suggested title and body
When `.sortie/pr.json` holds a JSON object with string `title` and `body`, Sortie SHALL use them for a new pull request. Sortie SHALL:

- read the file with the same link refusal as other control files, at most 64 KiB;
- remove control characters other than newline and tab;
- shorten the title to 256 characters.

When the file is absent or invalid, the title SHALL be `<identifier>: <issue title>` and the body SHALL link the issue. Sortie SHALL NOT pass the text through a shell.

#### Scenario: Agent suggests a title
- **WHEN** `.sortie/pr.json` is `{"title": "Fix add()", "body": "Adds a test."}`
- **THEN** the new pull request's title is `Fix add()` and its body is `Adds a test.`

#### Scenario: No suggestion
- **WHEN** `.sortie/pr.json` is absent for issue `ENG-42` titled `Calculator adds wrong`
- **THEN** the new pull request's title is `ENG-42: Calculator adds wrong`

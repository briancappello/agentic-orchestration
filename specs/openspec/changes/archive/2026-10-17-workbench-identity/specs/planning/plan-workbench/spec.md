## MODIFIED Requirements

### Requirement: Access
The workbench SHALL require a person to sign in before showing any plan or chat. Sign-in and roles SHALL follow `planning/workbench-identity`. It SHALL use its own server-side credentials for Sortie and `acp-broker`, and SHALL never expose those credentials, or any identity provider token, to the browser.

#### Scenario: Credentials stay server-side
- **WHEN** a person uses the workbench
- **THEN** no response to the browser contains the Sortie or broker token

#### Scenario: Signed out
- **WHEN** a person without a session opens a project
- **THEN** the workbench shows no plan or chat before they sign in

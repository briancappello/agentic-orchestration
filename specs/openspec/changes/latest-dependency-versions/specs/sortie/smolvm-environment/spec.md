## MODIFIED Requirements

### Requirement: Supported smolvm version
With the `smolvm` kind, Sortie SHALL run the configured smolvm binary's version command when it starts, and on every reload that selects the kind. Sortie SHALL refuse a version below the minimum supported version, which is the smolvm release the smolvm checks were last run against, initially `1.32.4`. Sortie SHALL accept every later release, with no upper bound. At startup the refusal SHALL stop Sortie. On reload the previous configuration SHALL be kept. The error SHALL name the version found and the minimum version. A missing binary, or a version that cannot be parsed, SHALL be refused the same way.

#### Scenario: Unsupported version at startup
- **WHEN** the workflow selects `smolvm` and `smolvm --version` prints `smolvm 1.26.1`
- **THEN** Sortie exits at startup with an error naming `1.26.1` and `1.32.4`

#### Scenario: Newer version accepted
- **WHEN** the workflow selects `smolvm` and `smolvm --version` prints `smolvm 2.0.0`
- **THEN** Sortie starts

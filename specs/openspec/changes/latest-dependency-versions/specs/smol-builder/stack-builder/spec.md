## MODIFIED Requirements

### Requirement: Temporary machines are cleaned up
Any smolvm machine the tool creates while building SHALL be deleted before the tool exits, whether the build succeeded or failed.

The tool SHALL also delete, before it creates a machine, every machine an earlier run of the tool left behind, for example when that run was killed or the host restarted. It SHALL label each machine it creates with its own process ID and the host's boot ID, and SHALL treat a labeled machine as left behind only when its boot ID is not the current one, or its process no longer runs. It SHALL NOT delete a machine of a build that is still running, and SHALL NOT delete any machine without its label.

#### Scenario: Build interrupted by a failure
- **WHEN** packing fails after the builder machine was created
- **THEN** no machine created by the tool remains in `smolvm machine ls`

#### Scenario: Builder left by a restart
- **WHEN** the host restarted while a build ran, leaving its builder machine
- **AND** a new build starts
- **THEN** the new build deletes that machine before creating its own

#### Scenario: Two builds at once
- **WHEN** a second build starts while the first build's builder machine exists
- **THEN** the first build's machine is not deleted

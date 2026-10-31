## MODIFIED Requirements

### Requirement: Temporary machines are cleaned up
Any smolvm machine, and any temporary file or directory, the tool creates while building SHALL be deleted before the tool exits, whether the build succeeded or failed.

The tool SHALL also delete, before it creates a machine, every machine and temporary directory an earlier run of the tool left behind, for example when that run was killed or the host restarted. It SHALL mark each machine (with labels) and each temporary directory (with an owner file) with its own process ID, that process's start time, and the host's boot ID. It SHALL treat a marked machine or directory as left behind only when its boot ID is not the current one, or no process with that ID and start time runs. It SHALL NOT delete a machine or directory of a build that is still running, and SHALL NOT delete any machine or directory without its mark.

#### Scenario: Build interrupted by a failure
- **WHEN** packing fails after the builder machine was created
- **THEN** no machine created by the tool remains in `smolvm machine ls`

#### Scenario: Builder left by a restart
- **WHEN** the host restarted while a build ran, leaving its builder machine
- **AND** a new build starts
- **THEN** the new build deletes that machine, and that build's temporary directories, before creating its own

#### Scenario: Two builds at once
- **WHEN** a second build starts while the first build's builder machine exists
- **THEN** the first build's machine is not deleted

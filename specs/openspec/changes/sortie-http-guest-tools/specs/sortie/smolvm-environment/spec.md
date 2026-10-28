## MODIFIED Requirements

### Requirement: Host resources given to the VM
Sortie SHALL give the VM exactly these host resources:

- the issue's `.sortie` directory, read-write
- the issue's tool channel socket

Sortie SHALL NOT put a Sortie binary in the guest. Sortie SHALL NOT enable nested virtualization, system mounts, a Docker socket bridge, or published ports. It SHALL NOT mount any other host path.

#### Scenario: No other host paths
- **WHEN** a VM is created for an issue
- **THEN** listing its mounts shows exactly the two resources above
- **AND** the guest has no `/opt/sortie`

## ADDED Requirements

### Requirement: The guest serves the tool channel
After every start of a VM, Sortie SHALL start, in the guest, a listener on the guest loopback at port `47800` that joins each connection to the issue's tool channel socket at `/run/sortie/tools.sock`. The listener SHALL be `socat`, from the pack. A pack without `socat` SHALL fail preparation with an error that names `socat`. Sortie SHALL retry a failed check for `socat` a few times before it concludes the pack lacks it, because right after a start smolvm can run a command before the pack's root filesystem is in place.

#### Scenario: Listener after a restart
- **WHEN** a stopped VM is started again for a later run
- **THEN** a `socat` process listens on `127.0.0.1:47800` in the guest

#### Scenario: Pack without socat
- **WHEN** the pack has no `socat`
- **THEN** preparation fails with an error naming `socat`

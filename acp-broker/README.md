# acp-broker

`acp-broker` sits between an orchestrator, such as Sortie, and an Agent
Client Protocol (ACP) agent. It keeps one session with two inputs: the
autonomous driver, and people. People can watch the session, steer it,
interrupt it, take it over, and hand it back. Permission requests and
questions that nobody watching answers go to the orchestrator, which
calls people.

The broker is the agent command's prefix: the driver starts
`acp-broker [flags] -- <agent command>` where it would start the agent.

- [Operator guide](docs/guide.md): build, flags, viewers, use with Sortie,
  telemetry, and isolating each agent.
- [Notes](docs/notes.md): the upstream work the broker depends on, and
  what each agent does over ACP.
- [Examples](examples/): a Pi wrapper and extension, and an
  OpenTelemetry Collector configuration.

## Develop

Go only, standard library only, no CGo.

```sh
make build   # bin/acp-broker
make test    # the tests, with the race detector
make lint    # golangci-lint for Linux, macOS and Windows
make check-latest   # fail when a Go module is behind its latest release
```

`make check-latest` sets `ACP_BROKER_LATEST_TEST=1` and compares every module in acp-broker's build list with its latest release, through `go list -m -u all` outside the workspace. It needs the network. Without the variable the test is skipped.

## License

AGPL-3.0-or-later, as the rest of this repository. See `../LICENSE`.

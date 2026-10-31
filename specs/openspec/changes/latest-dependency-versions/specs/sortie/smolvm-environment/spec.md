## MODIFIED Requirements

### Requirement: Supported smolvm version
With the `smolvm` kind, Sortie SHALL run the configured smolvm binary's version command when it starts, and on every reload that selects the kind. Sortie SHALL refuse a version below the minimum supported version, which is the smolvm release the smolvm checks were last run against, initially `1.32.4`. Sortie SHALL accept every later release, with no upper bound. At startup the refusal SHALL stop Sortie. On reload the previous configuration SHALL be kept. The error SHALL name the version found and the minimum version. A missing binary, or a version that cannot be parsed, SHALL be refused the same way.

#### Scenario: Unsupported version at startup
- **WHEN** the workflow selects `smolvm` and `smolvm --version` prints `smolvm 1.26.1`
- **THEN** Sortie exits at startup with an error naming `1.26.1` and `1.32.4`

#### Scenario: Newer version accepted
- **WHEN** the workflow selects `smolvm` and `smolvm --version` prints `smolvm 2.0.0`
- **THEN** Sortie starts

### Requirement: Credentials enter only as bindings
Each entry of `environment.smolvm.credentials` SHALL bind a host environment variable to a guest variable of the same name for the listed hosts, optionally setting one header. The guest SHALL see only a placeholder in that variable. The real value SHALL be substituted only on HTTPS requests to the listed hosts.

When an entry names a `header`, every HTTPS request to the entry's hosts SHALL carry that header with the real value, replacing any value the guest sent for it. No other request SHALL carry it. The header name SHALL be an HTTP token, and SHALL NOT be one of the routing or framing headers smolvm refuses: `Host`, `Content-Length`, `Transfer-Encoding`, `Connection`, `Upgrade`, `TE`, `Trailer`, `Keep-Alive`, `Proxy-Connection`, `Proxy-Authorization`, `Proxy-Authenticate`, and `Cookie`, in any case. Validation SHALL fail on any other name, naming the entry.

A host variable listed in `environment.smolvm.pass_env` SHALL reach the guest in plain text. That copy is opt-in.

Before dispatching, Sortie SHALL check every credential variable the session's agent kind declares. If one is set in Sortie's environment and is listed in neither `credentials` nor `pass_env`, the dispatch preflight SHALL fail with an error that names the variable. Sortie SHALL NOT copy any other host variable into the guest.

#### Scenario: Key used but never seen
- **WHEN** `credentials` binds `OPENROUTER_API_KEY` to `openrouter.ai`
- **AND** the agent in the VM calls the OpenRouter API
- **THEN** the call succeeds
- **AND** the key's value does not appear in any guest file or guest process environment

#### Scenario: Unbound agent credential refused
- **WHEN** the agent kind declares `ANTHROPIC_API_KEY`
- **AND** `ANTHROPIC_API_KEY` is set in Sortie's environment
- **AND** neither `credentials` nor `pass_env` lists it
- **THEN** the dispatch preflight fails with an error naming `ANTHROPIC_API_KEY`

#### Scenario: Header set on every request to the bound hosts
- **WHEN** `credentials` binds `SERVICE_KEY` to `api.example.com` with `header: X-Api-Key`
- **AND** a guest program sends an HTTPS request to `api.example.com` with no `X-Api-Key` header
- **THEN** the request arrives with `X-Api-Key` set to the real value of `SERVICE_KEY`

#### Scenario: Refused header name
- **WHEN** a credential names `header: Cookie`
- **THEN** validation fails with an error naming `environment.smolvm.credentials[0].header`

## ADDED Requirements

### Requirement: Report the HTTP listener to Sortie
A broker that serves HTTP viewers and runs under Sortie, with `SORTIE_API_URL`, `SORTIE_ISSUE_IDENTIFIER`, and `SORTIE_SESSION_TOKEN` set, SHALL report its HTTP URL and its viewer token to Sortie (`sortie/worker-discovery`) after its listener accepts connections. It SHALL retry a failed report with backoff while the session lives. A failed report SHALL NOT stop the session or the relay. A broker without an HTTP listener, or without those variables, SHALL NOT report. A credential-check broker SHALL NOT report.

#### Scenario: A broker under Sortie
- **WHEN** a broker for `LIVE-1` starts with `-http 127.0.0.1:0` under Sortie
- **THEN** after its listener is up, Sortie's state shows its URL for `LIVE-1`

#### Scenario: Sortie unreachable
- **WHEN** the broker cannot reach Sortie
- **THEN** the session runs and viewers on the unix socket are served
- **AND** the broker retries the report

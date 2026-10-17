## Purpose

Lets a caller acting for a running session, normally the ACP broker relaying an agent's question, call people through the notification destinations Sortie already routes to, instead of a separate alerting path.

## ADDED Requirements

### Requirement: Escalate a running issue
Sortie SHALL accept `POST /api/v1/{identifier}/escalate` with a JSON body `{"message": "<text>", "kind": "<question|permission|other>", "url": "<optional link>"}`. When the issue has a running worker, Sortie SHALL emit one `session.escalated` event and answer `202`. When the issue has no running worker, Sortie SHALL answer `409`. When the message is empty, Sortie SHALL answer `400`.

#### Scenario: Agent question escalated
- **WHEN** issue `LIVE-1` has a running worker
- **AND** a caller posts `{"message": "Which database should I target?", "kind": "question"}`
- **THEN** Sortie answers `202`
- **AND** emits one `session.escalated` event for `LIVE-1`

#### Scenario: Empty message
- **WHEN** a caller posts an escalation with an empty message
- **THEN** Sortie answers `400` and emits nothing

### Requirement: Escalations use existing notification routing
The `session.escalated` event SHALL reach exactly the destinations whose `notifications` entry lists it, through the same routing, pacing, and delivery rules as Sortie's other events. Before routing, Sortie SHALL mask registered secrets in the message. The event SHALL carry the issue identity, the run's rule and attempt, the kind, the masked message, and the URL when given.

#### Scenario: Slack subscription
- **WHEN** a Slack destination lists `session.escalated`
- **AND** an escalation arrives for `LIVE-1`
- **THEN** that Slack destination receives one message naming `LIVE-1` and containing the masked text

#### Scenario: No subscription
- **WHEN** no destination lists `session.escalated`
- **THEN** an escalation is accepted and delivered nowhere
- **AND** Sortie logs one record noting that the escalation had no destination

#### Scenario: Secret in the message
- **WHEN** the escalation message contains the value of a registered secret
- **THEN** every delivered copy shows the secret masked

### Requirement: Escalations are rate limited per issue
Sortie SHALL deliver at most one escalation per issue per 60 seconds. It SHALL answer later requests in that window with `429` and deliver nothing for them.

#### Scenario: Burst of escalations
- **WHEN** a caller sends three escalations for `LIVE-1` within ten seconds
- **THEN** the first is delivered
- **AND** the second and third receive `429`

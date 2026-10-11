## Purpose

Gets a person to answer agent questions and permission requests during autonomous runs, wherever that person is, before falling back to the driver's automatic answer.

## ADDED Requirements

### Requirement: Viewers answer permission requests first
When the agent sends `session/request_permission` and at least one viewer is attached, the broker SHALL hold the request and send it to every viewer with its ID and options. The first valid viewer answer SHALL go to the agent. An answer may name an option by its ID or its kind. A later answer SHALL be rejected.

#### Scenario: Viewer allows once
- **WHEN** a viewer is attached and the agent asks permission with options `allow_once` and `reject_once`
- **AND** the viewer answers with `allow_once`
- **THEN** the agent receives the `selected` outcome with that option's ID
- **AND** the driver never sees the request

### Requirement: Escalate when nobody answers
When a permission request has waited for the escalation delay (30 seconds by default) without an answer, the broker SHALL escalate it through Sortie's escalation endpoint. The broker SHALL do the same at once when the request arrives and no viewer is attached. The escalation SHALL use kind `permission`, the tool title as the message, and a link to the session when a public viewer URL is configured. The broker SHALL hold Sortie's run while the request waits.

#### Scenario: No viewer attached
- **WHEN** no viewer is attached and the agent asks permission
- **THEN** the broker calls Sortie's escalation endpoint with kind `permission`
- **AND** calls Sortie's hold endpoint

#### Scenario: Viewer attached but idle
- **WHEN** a viewer is attached and does not answer for 30 seconds
- **THEN** the broker escalates the request once

### Requirement: Driver decides after the answer timeout
When a permission request has had no answer for the answer timeout (10 minutes by default; 0 means no limit), the broker SHALL forward it to the driver. The driver's answer SHALL go to the agent. The broker SHALL release any hold it took for that request.

#### Scenario: Nobody answers
- **WHEN** a permission request is escalated and nobody answers for 10 minutes
- **THEN** the driver receives the request
- **AND** the broker releases the hold it took for that request

### Requirement: Cancelled turns cancel waiting requests
When the turn that asked is cancelled, by a takeover, a viewer cancel, or the driver, the broker SHALL answer each waiting permission request with the `cancelled` outcome.

#### Scenario: Takeover while a request waits
- **WHEN** a permission request waits
- **AND** a viewer takes over
- **THEN** the agent receives the `cancelled` outcome for that request

### Requirement: Agent questions escalate the same way
A `session/request_permission` is a question when none of its options has an `allow_once` or `allow_always` kind, for example a list of answers to choose from. The broker SHALL handle a question like a permission request and escalate it with kind `question`. The message SHALL contain the request's title and its option names. The broker SHALL NOT try to detect questions in free text at the end of a turn.

#### Scenario: Multiple-choice question
- **WHEN** the agent sends a request whose options are `postgres` and `sqlite`, neither of an allow kind
- **AND** no viewer is attached
- **THEN** the broker escalates with kind `question` and a message naming both options

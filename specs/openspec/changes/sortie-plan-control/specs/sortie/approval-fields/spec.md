## Purpose

Shows in the tracker who approved each story and when, so that people who only look at the tracker can see the approval without opening the workbench.

## ADDED Requirements

### Requirement: Approver on each node
Each story node in the plan graph SHALL be able to carry `approved_by` (a display name and a stable identity) and `approved_at` (an RFC 3339 time). A sync SHALL write them to the story's issue as explicit tracker fields when the adapter declares **approval fields**. A change to either value SHALL be an update in the preview, like a changed title. A sync SHALL NOT write approval fields to an adapter that does not declare **approval fields**, and the preview SHALL then say that the fields were not written.

#### Scenario: Approver written
- **WHEN** story `billing/invoice` carries `approved_by` "Ana Ruiz" and `approved_at` `2026-10-16T14:02:00Z`
- **AND** the adapter declares **approval fields**
- **THEN** after the sync the issue shows both values in their own fields

#### Scenario: An adapter without the fields
- **WHEN** the adapter does not declare **approval fields**
- **THEN** the sync writes no approval values
- **AND** the preview reports `approval_fields_unsupported`
- **AND** the rest of the sync still applies

### Requirement: Huly stores approvals as custom attributes
The Huly adapter SHALL declare **approval fields**. It SHALL store the approver's display name, the approver's stable identity, and the approval time as custom issue attributes, created the same way as the plan key attribute. The attributes SHALL be read-only for people in Huly.

#### Scenario: Huly shows the approver
- **WHEN** a sync writes `approved_by` for a story in Huly
- **THEN** the Huly issue shows the approver in a custom attribute that a person cannot edit

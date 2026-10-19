## Purpose

Generates and sends monthly invoices for every active account in the system.

## ADDED Requirements

### Requirement: Monthly invoice
The system SHALL generate an invoice on the first day of each month:
- one line per active subscription;
- totals in the account currency.

Invoices SHALL be immutable once sent.

#### Scenario: First of the month
- **WHEN** the clock reaches the first day of a month
- **THEN** an invoice exists for every active account

### Requirement: Tax lines
The system SHALL add tax lines computed with this rule:

```
### Requirement: not a header
tax = subtotal * rate
```

#### Scenario: Tax applied
- **WHEN** an invoice is generated
- **THEN** it has tax lines

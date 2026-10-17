## ADDED Requirements

### Requirement: Unknown products
`price(product)` SHALL raise `ValueError` with a message that names the product when the product has no price.

#### Scenario: An unknown product
- **WHEN** a caller asks for `price("gold")`
- **THEN** it raises `ValueError`, and the message contains `gold`

### Requirement: Cart totals
`total(items)` SHALL return the sum, in cents, of price times quantity over a list of `(product, quantity)` pairs. An unknown product SHALL raise the same `ValueError` as `price`. A quantity below 1 SHALL raise `ValueError`.

#### Scenario: A cart
- **WHEN** a caller asks for `total([("basic", 2), ("pro", 1)])`
- **THEN** it returns `2500`

#### Scenario: A bad quantity
- **WHEN** a caller asks for `total([("basic", 0)])`
- **THEN** it raises `ValueError`

### Requirement: Team product
The library SHALL price the product `team` at 4000 cents.

#### Scenario: The team price
- **WHEN** a caller asks for `price("team")`
- **THEN** it returns `4000`

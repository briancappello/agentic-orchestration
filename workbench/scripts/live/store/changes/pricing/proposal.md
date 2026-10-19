## Why

The live-lab billing library (`billing/prices.py`) prices one product at a time
and fails with a bare `KeyError` on a product it does not know. Checkout needs
the total of a cart, and a clear error for an unknown product.

## What Changes

- `price()` raises a `ValueError` that names an unknown product.
- A new `total()` returns the price of a cart: a list of (product, quantity).
- A new product, `team`, priced at 4000 cents.

## Capabilities

### New Capabilities
- `billing/pricing`: product prices, the unknown-product error, and cart totals.

## Impact

`billing/prices.py` and its tests in the `live-lab` repository.

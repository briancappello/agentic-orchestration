"""Prices of the products, in cents."""

PRICES = {"basic": 500, "pro": 1500}


def price(product: str) -> int:
    """The price of a product, in cents."""
    return PRICES[product]

"""Canonical pricing rules. Every consumer should import from here."""
PREMIUM_DISCOUNT = 0.10
TAX_RATE = 0.15


def compute_total(amount, tier):
    if tier == "premium":
        amount = amount * (1 - PREMIUM_DISCOUNT)
    tax = amount * TAX_RATE
    return round(amount + tax, 2)

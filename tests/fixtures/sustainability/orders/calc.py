"""Order total computation. Duplicates pricing logic from canonical.pricing."""
PREMIUM_DISCOUNT = 0.10
TAX_RATE = 0.15


def order_total(amount, tier):
    subtotal = amount
    if tier == "premium":
        subtotal = subtotal * (1 - PREMIUM_DISCOUNT)
    tax = subtotal * TAX_RATE
    return round(subtotal + tax, 2)

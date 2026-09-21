"""Invoice computation. Duplicates pricing logic from canonical.pricing."""
PREMIUM_DISCOUNT = 0.10
TAX_RATE = 0.15


def invoice_amount(amount, tier):
    base = amount
    if tier == "premium":
        base = base * (1 - PREMIUM_DISCOUNT)
    vat = base * TAX_RATE
    return round(base + vat, 2)

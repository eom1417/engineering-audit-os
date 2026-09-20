"""Order API."""
VAT_RATE = 0.15


def total(amount):
    return round(amount * (1 + VAT_RATE), 2)

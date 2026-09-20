"""Accounting export."""
VAT_RATE = 0.14


def exported_total(amount):
    return round(amount * (1 + VAT_RATE), 2)

"""Pricing rules."""
import os

PREMIUM_DISCOUNT = 0.10
TAX_RATE = float(os.environ.get('TAX_RATE', '0.15'))


def base_total(items):
    return sum(item['price'] * item['quantity'] for item in items)


def price_for(items, tier='standard'):
    total = base_total(items)
    if tier == 'premium':
        total = total * (1 - PREMIUM_DISCOUNT)
    return round(total * (1 + TAX_RATE), 2)

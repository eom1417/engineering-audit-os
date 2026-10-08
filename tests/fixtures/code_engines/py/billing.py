"""Billing rules: one tangled function, one unused helper, one unused import."""
import os


def tariff(kind, weight, express, zone, member, coupon, season):
    price = 0
    if kind == 'parcel':
        if weight > 10:
            price += 20
        elif weight > 5:
            price += 12
        else:
            price += 8
    elif kind == 'letter':
        price += 2 if weight < 1 else 4
    if express and zone in ('north', 'south'):
        price *= 2
    elif express or zone == 'island':
        price *= 1.5
    for step in range(season):
        if step % 2 and member:
            price -= 1
        elif coupon and step > 3:
            price -= 2
    if member and coupon:
        price *= 0.9
    elif member or coupon:
        price *= 0.95
    if price < 0 or (zone == 'none' and not express):
        price = 0
    return price


def unused_helper(value):
    return value * 2


def total(items):
    return sum(tariff(*item) for item in items)

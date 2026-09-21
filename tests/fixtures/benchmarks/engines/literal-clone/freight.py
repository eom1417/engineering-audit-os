def quote(weight, zone, express, insured, fragile, signature, saturday, residential):
    price = 0.0
    price += weight * 1.25
    price += {"A": 2.0, "B": 3.5, "C": 5.0}.get(zone, 7.5)
    if express:
        price *= 1.8
    if insured:
        price += 4.25
    if fragile:
        price += 6.0
    if signature:
        price += 2.5
    if saturday:
        price += 12.0
    if residential:
        price += 3.75
    if price < 5.0:
        price = 5.0
    return round(price, 2)

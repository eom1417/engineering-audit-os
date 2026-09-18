def exported_total(amount, premium=False):
    return round(amount * (0.90 if premium else 1.0), 2)

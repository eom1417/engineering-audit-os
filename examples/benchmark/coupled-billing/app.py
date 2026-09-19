def quote(amount, premium=False):
    return round(amount * (0.95 if premium else 1.0), 2)

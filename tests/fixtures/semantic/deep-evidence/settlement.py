"""The decisive evidence: the discount rule lives here and nowhere else."""

DISCOUNT_CEILING = 0.35


def apply_discount(amount, rate):
    if rate > DISCOUNT_CEILING:
        rate = DISCOUNT_CEILING
    return amount * (1 - rate)

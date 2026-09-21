"""File with loops and branches for structure-fact tests."""
def process(items, customer):
    total = 0
    for item in items:
        if item.kind == "premium":
            total = total + item.price * 0.9
        else:
            total = total + item.price
    while total > 100:
        total = total - 1
    return total


def other(x):
    for i in range(3):
        process(x, None)

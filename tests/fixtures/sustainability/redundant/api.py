"""Code with all four classes of redundant work."""


def repeated():
    x = lookup("k")
    y = lookup("k")
    return x + y


def hoist():
    for item in items:
        result = constant()
        process(item, result)


def n_plus_one():
    for order in orders:
        total = order.get_total()
        ship(order)


def pass_layer(payload):
    return inner(payload)

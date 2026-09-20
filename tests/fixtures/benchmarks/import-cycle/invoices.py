import orders


def build_invoice(order):
    return {'order': order, 'placed_by': orders.place.__name__}

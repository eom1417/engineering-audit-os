from invoices import build_invoice


def place(order):
    return build_invoice(order)

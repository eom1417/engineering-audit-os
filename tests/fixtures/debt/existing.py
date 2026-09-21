"""A project that already carries debt: two symbols with the same shape under different names."""


def compute_order_total(items, tax_rate):
    subtotal = 0
    for item in items:
        subtotal = subtotal + item
    return subtotal * (1 + tax_rate)


def invoice_amount(lines, rate):
    running = 0
    for line in lines:
        running = running + line
    return running * (1 + rate)

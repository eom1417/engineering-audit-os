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


def expense_total(rows, tax):
    running = 0
    for row in rows:
        running = running + row
    return running * (1 + tax)


def report_sum(entries, percentage):
    accumulated = 0
    for entry in entries:
        accumulated = accumulated + entry
    return accumulated * (1 + percentage)


def ledger_amount(records, percent):
    sum_ = 0
    for record in records:
        sum_ = sum_ + record
    return sum_ * (1 + percent)


def payment_total(rows, pct):
    total = 0
    for row in rows:
        total = total + row
    return total * (1 + pct)

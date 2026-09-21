"""Three controllers performing the same coordination sequence."""
def flow_a(payload):
    validate(payload)
    save(payload)
    notify(payload)
    return payload

def flow_b(item):
    validate(item)
    save(item)
    notify(item)
    return item

def flow_c(record):
    validate(record)
    save(record)
    notify(record)
    return record

def unrelated(x):
    return x + 1

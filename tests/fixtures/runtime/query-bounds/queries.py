"""A fixture for query-bound detection.

Each function shows one observable pattern: bounded, unbounded, or neither.
"""
def get_unbounded():
    # .all() without a preceding bound -> unbounded
    return Order.query.filter(Order.paid == True).all()

def get_limited(n):
    # .limit( with literal integer -> bounded
    return Order.query.limit(50).all()

def get_first():
    # .first() always returns at most one row -> bounded
    return Order.query.first()

def get_offset():
    # .offset(N) is a positional bound
    return Order.query.offset(10).limit(20).all()

def get_sliced():
    # [:N] is a bound too
    return Order.query.all()[:10]

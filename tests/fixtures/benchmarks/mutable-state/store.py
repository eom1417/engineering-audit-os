CACHE = {}


def remember(key, value):
    CACHE[key] = value
    return CACHE

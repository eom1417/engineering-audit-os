"""Process-scoped cache: lru_cache, functools.cache, cached_property."""
import functools

@functools.lru_cache(maxsize=128)
def fib(n):
    return n if n < 2 else fib(n - 1) + fib(n - 2)

@functools.cache
def square(n):
    return n * n

"""A fixture for rate-limit and concurrency-bound detection.

Some entry points are bounded; others are not.
"""
import asyncio
from limits import RateLimitItem

# Bounded with explicit limit value
@limiter.limit(limit_value=100, per=60)
def throttled():
    return 'ok'

# Bounded with concurrency
sem = asyncio.Semaphore(10)

async def guarded():
    async with sem:
        return 'ok'

# Bounded worker pool
pool = ThreadPoolExecutor(max_workers=8)

def wide_open():
    # No limiter, no semaphore -> unbounded
    return 'unbounded'

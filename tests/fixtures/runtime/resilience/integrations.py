"""A fixture for resilience-policy detection.

Each function calls the same external host with a different policy: protected, bare,
retry-only, breaker-only.
"""
import requests

HOST = 'https://api.example.com'

def protected():
    # timeout=30 + tenacity retry + pybreaker
    @retry
    @pybreaker.CircuitBreaker(fail_max=5)
    def call():
        return requests.get(HOST, timeout=30)
    return call()

def bare():
    # no timeout, no retry, no breaker -> the dangerous default
    return requests.get(HOST)

def with_retry_only():
    from tenacity import retry
    @retry
    def call():
        return requests.get(HOST)
    return call()

def with_breaker_only():
    return pybreaker.CircuitBreaker(fail_max=5).call(lambda: requests.get(HOST))

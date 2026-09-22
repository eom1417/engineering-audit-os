class _Limiter:
    def limit(self, rule):
        def decorate(fn):
            return fn
        return decorate


limiter = _Limiter()
RATE_LIMIT = "100/minute"

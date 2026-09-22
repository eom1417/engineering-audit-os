"""HTTP cache: Cache-Control headers, @Cacheable."""
from fastapi import Response

def cached_response():
    resp = Response()
    resp.headers["Cache-Control"] = "max-age=60"
    return resp

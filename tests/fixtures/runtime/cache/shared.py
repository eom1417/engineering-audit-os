"""Shared cache: redis, memcached, Django cache."""
import redis
import memcache

r = redis.Redis(host='localhost', port=6379)

def get_user(uid):
    return r.get(f'user:{uid}')

def put_user(uid, data, ttl=60):
    return r.set(f'user:{uid}', data, ex=ttl)

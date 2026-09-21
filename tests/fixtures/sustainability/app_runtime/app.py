"""Sample application with auth, observability, integrations, and an ORM model."""
from flask import Flask
from prometheus_client import Counter
import sentry_sdk
import requests

requests_counter = Counter('requests_total', 'Total requests')
sentry_sdk.init(dsn='https://examplePublicKey@o0.ingest.sentry.io/0')


class Order:
    id = None
    amount = None
    tier = None


def public_endpoint():
    """Anyone can call this; no auth."""
    return {'ok': True}


def protected_endpoint():
    """This needs authentication."""
    if not authenticate():
        return {'error': 'unauthorized'}, 401
    return {'ok': True}


def call_external():
    """Outbound call to a third-party service."""
    return requests.get('https://api.stripe.com/v1/charges').json()

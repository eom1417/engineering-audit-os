from flask import Flask
from functools import lru_cache

from store import Order, session

app = Flask(__name__)


@app.route('/items', methods=['GET'])
def list_items():
    return {"rate": _rate("usd")}


@lru_cache(maxsize=64)
def _rate(code):
    return session.query(Order).limit(1).first().amount


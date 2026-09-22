"""A service that works at ten users and falls over at ten thousand."""
from flask import Flask
import requests

from store import Order, session

app = Flask(__name__)

# Module-level mutable state: two workers would disagree about it.
RECENT = {}


@app.route('/orders', methods=['GET'])
def list_orders():
    orders = session.query(Order).all()          # no limit: grows with the table
    total = 0
    for order in orders:
        item = session.query(Order).filter_by(id=order.id).first()   # one query per order
        total += item.amount
    RECENT['last_total'] = total
    rate = requests.get('https://rates.example.com/latest').json()   # no timeout, no retry
    return {'total': total * rate['usd'], 'count': len(orders)}

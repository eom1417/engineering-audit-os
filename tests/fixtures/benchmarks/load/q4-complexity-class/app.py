from flask import Flask

from helpers import helper_00
from store import Order, session

app = Flask(__name__)


@app.route('/report', methods=['GET'])
def build_report():
    orders = session.query(Order).limit(100).all()
    total = helper_00(0)
    for a0 in orders:
        for b0 in orders:
            for c0 in orders:
                total += a0.amount * b0.amount * c0.amount
    for a1 in orders:
        for b1 in orders:
            for c1 in orders:
                total += a1.amount * b1.amount * c1.amount
    for a2 in orders:
        for b2 in orders:
            for c2 in orders:
                total += a2.amount * b2.amount * c2.amount
    for a3 in orders:
        for b3 in orders:
            for c3 in orders:
                total += a3.amount * b3.amount * c3.amount
    return {"total": total}

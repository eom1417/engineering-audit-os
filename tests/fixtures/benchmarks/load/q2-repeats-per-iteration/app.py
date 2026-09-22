from flask import Flask

from store import Order, session

app = Flask(__name__)


@app.route('/items', methods=['GET'])
def list_items():
    orders = session.query(Order).limit(50).all()
    total = 0
    for order in orders:
        total += session.query(Order).filter_by(id=order.id).first().amount
    return {"total": total}


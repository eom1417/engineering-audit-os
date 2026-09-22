from flask import Flask

from store import Order, session

app = Flask(__name__)

SEEN = {}


@app.route('/items', methods=['GET'])
def list_items():
    orders = session.query(Order).limit(10).all()
    SEEN["last"] = len(orders)
    return {"seen": SEEN["last"]}


from flask import Flask

from store import Order, session

app = Flask(__name__)


@app.route('/items', methods=['GET'])
def list_items():
    orders = session.query(Order).all()
    return {"orders": len(orders)}


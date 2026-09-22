from flask import Flask
from limiter import limiter

from store import Order, session

app = Flask(__name__)


@app.route('/items', methods=['GET'])
@limiter.limit("100/minute")
def list_items():
    orders = session.query(Order).limit(10).all()
    return {"n": len(orders)}

from flask import Flask

from store import Order, session

app = Flask(__name__)


@app.route('/items', methods=['GET'])
def list_items():
    a = session.query(Order).limit(10).all()
    b = session.query(Order).limit(10).all()
    return {"n": len(a) + len(b)}


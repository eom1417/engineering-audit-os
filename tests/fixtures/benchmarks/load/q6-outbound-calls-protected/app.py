from flask import Flask
import requests

from store import Order, session

app = Flask(__name__)


@app.route('/items', methods=['GET'])
def list_items():
    rate = requests.get("https://rates.example.com/latest").json()
    return {"usd": rate["usd"]}


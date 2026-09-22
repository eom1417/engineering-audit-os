class Order:
    id = 0
    amount = 0


class _Session:
    def query(self, model):
        return self

    def filter_by(self, **kwargs):
        return self

    def first(self):
        return Order()

    def all(self):
        return []


session = _Session()

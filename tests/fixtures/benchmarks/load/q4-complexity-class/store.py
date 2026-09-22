class Order:
    id = 0
    amount = 0


class _Session:
    def query(self, model):
        return self

    def limit(self, n):
        return self

    def all(self):
        return []


session = _Session()

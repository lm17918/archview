"""Order data model."""
from app.models.user import User


class Order:
    def __init__(self, user_id, items, total, id=None, status="pending"):
        self.id = id
        self.user_id = user_id
        self.items = items
        self.total = total
        self.status = status

    def __repr__(self):
        return f"Order(#{self.id}, total={self.total})"

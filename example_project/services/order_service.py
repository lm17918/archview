"""Order processing service."""
from models.order import Order
from models.user import User
from services.email_service import send_confirmation
from utils.logger import log


class OrderService:
    def __init__(self, settings):
        self.settings = settings

    def place_order(self, user: User, items: list, total: float):
        order = Order(user_id=user.id, items=items, total=total)
        send_confirmation(user.email, order)
        log(f"Order placed: {order.id}")
        return order

    def list_orders(self):
        log("Listing orders")
        return []

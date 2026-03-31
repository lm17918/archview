"""Payment processing service — BROKEN: missing closing parenthesis."""

from models.order import Order
from utils.logger import log


def process_payment(order: Order, amount: float:
    """Process a payment for an order."""
    log(f"Processing payment of {amount} for order {order.id}")
    return {"status": "paid", "amount": amount}

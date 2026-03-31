"""Payment processing service — BROKEN: missing closing parenthesis."""

from app.models.order import Order
from app.utils.logger import log


def process_payment(order: Order, amount: float:
    """Process a payment for an order."""
    log(f"Processing payment of {amount} for order {order.id}")
    return {"status": "paid", "amount": amount}

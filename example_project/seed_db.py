"""Seed the database with sample data."""
from services.user_service import UserService
from services.order_service import OrderService
from config import Settings


def seed():
    settings = Settings()
    user_svc = UserService(settings)
    order_svc = OrderService(settings)

    alice = user_svc.create_user("Alice", "alice@example.com", "pass123")
    bob = user_svc.create_user("Bob", "bob@example.com", "secret")

    order_svc.place_order(alice, ["Widget", "Gadget"], 49.99)
    order_svc.place_order(bob, ["Thingamajig"], 19.99)


if __name__ == "__main__":
    seed()

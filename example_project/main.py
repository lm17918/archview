"""Application entry point — wires together routes, services, and config."""
from config import Settings
from api.routes import register_routes
from api.auth import require_token
from services.user_service import UserService
from services.order_service import OrderService


def create_app():
    settings = Settings()
    user_svc = UserService(settings)
    order_svc = OrderService(settings)
    routes = register_routes(user_svc, order_svc)
    return routes

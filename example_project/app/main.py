"""Application entry point — wires together routes, services, and config."""
from app.config import Settings
from app.api.routes import register_routes
from app.api.auth import require_token
from app.services.user_service import UserService
from app.services.order_service import OrderService


def create_app():
    settings = Settings()
    user_svc = UserService(settings)
    order_svc = OrderService(settings)
    routes = register_routes(user_svc, order_svc)
    return routes

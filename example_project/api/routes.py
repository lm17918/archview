"""Route definitions for the REST API."""
from api.auth import require_token
from utils.logger import log
from utils.validators import validate_email


def register_routes(user_svc, order_svc):
    log("Registering routes")
    return {
        "GET /users": user_svc.list_users,
        "POST /users": user_svc.create_user,
        "GET /orders": order_svc.list_orders,
        "POST /orders": order_svc.place_order,
    }

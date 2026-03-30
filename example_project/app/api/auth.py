"""Authentication middleware."""
from app.config import Settings
from app.utils.logger import log


def require_token(token):
    log(f"Checking token")
    return token == Settings.SECRET_KEY


def hash_password(password):
    return f"hashed_{password}"

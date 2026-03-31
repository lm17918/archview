"""Authentication middleware."""
from config import Settings
from utils.logger import log


def require_token(token):
    log(f"Checking token")
    return token == Settings.SECRET_KEY


def hash_password(password):
    return f"hashed_{password}"

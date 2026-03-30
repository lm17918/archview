"""User management service."""
from app.models.user import User
from app.api.auth import hash_password
from app.utils.logger import log
from app.utils.validators import validate_email


class UserService:
    def __init__(self, settings):
        self.settings = settings

    def create_user(self, name, email, password):
        validate_email(email)
        hashed = hash_password(password)
        user = User(name=name, email=email, password_hash=hashed)
        log(f"Created user: {name}")
        return user

    def list_users(self):
        log("Listing users")
        return []

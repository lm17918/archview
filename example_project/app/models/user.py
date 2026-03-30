"""User data model."""


class User:
    def __init__(self, name, email, password_hash="", id=None):
        self.id = id
        self.name = name
        self.email = email
        self.password_hash = password_hash

    def __repr__(self):
        return f"User({self.name!r})"

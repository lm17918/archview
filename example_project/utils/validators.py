"""Input validation helpers."""


def validate_email(email):
    if "@" not in email:
        raise ValueError(f"Invalid email: {email}")
    return True


def validate_positive(value):
    if value <= 0:
        raise ValueError(f"Must be positive: {value}")
    return True

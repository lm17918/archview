"""Email notification service."""
from app.utils.logger import log


def send_confirmation(email, order):
    log(f"Sending confirmation to {email}")


def send_welcome(email, name):
    log(f"Sending welcome email to {name}")

"""Cache layer — BROKEN: invalid syntax in dict comprehension."""

from app.config import settings


def build_cache():
    return {k: v for k, v in settings.items() if k = "debug"}

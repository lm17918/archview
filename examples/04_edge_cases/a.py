"""Module A — imports B (circular pair)."""
from b import fn_b


def fn_a():
    return fn_b()

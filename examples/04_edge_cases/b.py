"""Module B — imports A (circular pair, lazy to avoid runtime cycle)."""


def fn_b():
    from a import fn_a  # noqa: F401
    return 1

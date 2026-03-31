"""Database cleanup script — BROKEN: indentation error."""

from utils.logger import log


def run_cleanup():
    log("Starting cleanup")
        items = get_stale_items()
    for item in items:
        delete(item)

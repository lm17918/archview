"""Data formatters for export."""
from utils.logger import log


def to_csv(records):
    log(f"Formatting {len(records)} records as CSV")
    return "\n".join(str(r) for r in records)


def to_json(records):
    log(f"Formatting {len(records)} records as JSON")
    return [str(r) for r in records]

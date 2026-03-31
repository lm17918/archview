"""Export orders report to CSV."""
from services.order_service import OrderService
from config import Settings
from utils.logger import log
from data.formatters import to_csv


def export():
    settings = Settings()
    orders = OrderService(settings).list_orders()
    csv = to_csv(orders)
    log(f"Exported {len(orders)} orders")
    return csv


if __name__ == "__main__":
    export()

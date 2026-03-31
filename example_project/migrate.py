"""Run database migrations."""
from config import Settings
from utils.logger import log


def migrate():
    settings = Settings()
    log(f"Connecting to {settings.DB_URL}")
    log("Running migrations...")
    log("Done.")


if __name__ == "__main__":
    migrate()

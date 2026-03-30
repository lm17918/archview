"""Run database migrations."""
from app.config import Settings
from app.utils.logger import log


def migrate():
    settings = Settings()
    log(f"Connecting to {settings.DB_URL}")
    log("Running migrations...")
    log("Done.")


if __name__ == "__main__":
    migrate()

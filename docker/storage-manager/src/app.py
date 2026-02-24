import logging
import os

from flask import Flask

from .api import create_api_blueprint
from .discovery import discover_registrations_from_containers, sync_discovered_registrations
from .models import init_db
from .scheduler import StorageScheduler


def create_app() -> Flask:
    app = Flask(__name__)

    log_level = str(os.getenv("SM_LOG_LEVEL", "INFO")).upper()
    logging.basicConfig(level=getattr(logging, log_level, logging.INFO))

    db_path = str(os.getenv("SM_DB_PATH", "/data/storage_manager.db"))
    check_interval_seconds = int(str(os.getenv("SM_CHECK_INTERVAL_SECONDS", "300")))

    init_db(db_path)

    try:
        discovered = discover_registrations_from_containers()
        sync_discovered_registrations(db_path=db_path, registrations=discovered)
    except Exception:
        logging.getLogger("storage_manager").warning(
            "[STORAGE]: Failed to auto-discover storage registrations from docker labels",
            exc_info=True,
        )

    scheduler = StorageScheduler(db_path=db_path, check_interval_seconds=check_interval_seconds)
    scheduler.start()

    app.register_blueprint(create_api_blueprint(db_path=db_path, scheduler=scheduler), url_prefix="/api")
    app.extensions["storage_scheduler"] = scheduler

    return app


def main() -> None:
    app = create_app()
    api_port = int(str(os.getenv("SM_API_PORT", "9100")))
    app.run(host="0.0.0.0", port=api_port)


if __name__ == "__main__":
    main()

"""Application-wide logging setup. Call setup_logging() once at startup."""
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging() -> None:
    """Configure root logger: rotating file in %APPDATA%\\Lyudochka\\lyudochka.log."""
    log_dir = (
        Path(os.environ["APPDATA"]) if "APPDATA" in os.environ
        else Path.home() / "AppData" / "Roaming"
    ) / "Lyudochka"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "lyudochka.log"

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=2,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        fmt="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(file_handler)

    logging.info("=== Lyudochka started ===  log: %s", log_path)

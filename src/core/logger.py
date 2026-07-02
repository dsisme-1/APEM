import logging
from pathlib import Path

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)


def setup_logger(name: str = "APEM") -> logging.Logger:
    """Sentralisasi logging untuk sistem APEM."""
    logger = logging.getLogger(name)

    if logger.hasHandlers():
        return logger

    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Handler untuk terminal/console
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # Handler untuk file log fisik
    file_handler = logging.FileHandler(
        LOG_DIR / "app.log",
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger
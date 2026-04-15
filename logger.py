import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

MAX_LOG_BYTES = 10 * 1024 * 1024


class TimestampedRotatingFileHandler(RotatingFileHandler):
    def __init__(self, log_path: str, max_bytes: int = MAX_LOG_BYTES, encoding: str = "utf-8"):
        self.base_path = Path(log_path)
        self.base_path.parent.mkdir(parents=True, exist_ok=True)
        initial_path = self._build_timestamped_name(self.base_path)
        super().__init__(initial_path, maxBytes=max_bytes, backupCount=0, encoding=encoding)

    @staticmethod
    def _build_timestamped_name(base_path: Path) -> str:
        stamp = datetime.now().strftime("%d-%m-%Y_%H-%M-%S")
        return str(base_path.with_name(f"{base_path.stem}_{stamp}{base_path.suffix}"))

    def doRollover(self):
        if self.stream:
            self.stream.close()
            self.stream = None
        self.baseFilename = self._build_timestamped_name(self.base_path)
        self.mode = "a"
        self.stream = self._open()


def get_rotating_handler(log_path: str, datefmt: str = "%d/%m/%y %H:%M:%S") -> logging.Handler:
    handler = TimestampedRotatingFileHandler(log_path)
    formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s', datefmt)
    handler.setFormatter(formatter)
    return handler


def get_test_logger(log_path: str = 'logs/test.log') -> logging.Logger:
    logger_name = f"door_test_runtime:{log_path}"
    logger = logging.getLogger(logger_name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.addHandler(get_rotating_handler(log_path))
    return logger

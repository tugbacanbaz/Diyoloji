import logging
import sys

# ANSI renk kodları
class LogColors:
    RESET = '\033[0m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'

# Renkli formatter
class ColorFormatter(logging.Formatter):
    def format(self, record):
        color = LogColors.RESET
        if record.levelno == logging.INFO:
            color = LogColors.GREEN
        elif record.levelno == logging.WARNING:
            color = LogColors.YELLOW
        elif record.levelno >= logging.ERROR:
            color = LogColors.RED

        message = super().format(record)
        return f"{color}{message}{LogColors.RESET}"

# Logger kur
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Stream handler → stdout
stream_handler = logging.StreamHandler(sys.stdout)
formatter = ColorFormatter('%(asctime)s - %(levelname)s - %(message)s')
stream_handler.setFormatter(formatter)

# Handler'ı ekle (sadece bir kez)
if not logger.handlers:
    logger.addHandler(stream_handler)


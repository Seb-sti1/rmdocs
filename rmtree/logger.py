import logging
import sys


class ColorFormatter(logging.Formatter):
    COLORS = {
        logging.DEBUG: "\033[36m",  # Cyan
        logging.INFO: "\033[0m",  # Default terminal color
        logging.WARNING: "\033[33m",  # Dark yellow / amber
        logging.ERROR: "\033[31m",  # Red
        logging.CRITICAL: "\033[1;31m",  # Bold red
    }
    RESET = "\033[0m"

    def format(self, record):
        prefix = ""
        if logging.getLogger("rmtree").level == logging.DEBUG:
            prefix = f"[{record.name}] "
        color = self.COLORS.get(record.levelno, self.RESET)
        return f"{prefix}{color}{record.getMessage()}{self.RESET}"


def setup_logging(debug: bool, test_compatibility: bool) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(ColorFormatter())
    logging.basicConfig(handlers=[handler], level=logging.DEBUG if debug else logging.INFO)
    logging.getLogger("rmtree").setLevel(logging.DEBUG if debug else logging.INFO)
    logging.getLogger("rmtree.debug").setLevel(logging.DEBUG if debug else
                                               logging.INFO if test_compatibility else
                                               logging.WARNING)
    logging.getLogger("rmscene").setLevel(logging.DEBUG if debug else logging.CRITICAL)

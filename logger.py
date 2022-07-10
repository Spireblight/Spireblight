import logging
import os

__all__ = ["logger"]

logger = logging.getLogger("Twitch-Discord-Bot")
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter("{asctime} :: {levelname:>8} - {message}", "(%Y-%m-%d %H:%M:%S)", "{")

h_debug = logging.FileHandler(os.path.join("data", "debug.log"))
h_debug.setLevel(logging.DEBUG)
h_debug.setFormatter(formatter)

logger.addHandler(h_debug)

h_info = logging.FileHandler(os.path.join("data", "info.log"))
h_info.setLevel(logging.INFO)
h_info.setFormatter(formatter)

logger.addHandler(h_info)

h_rest = logging.FileHandler(os.path.join("data", "error.log"))
h_rest.setLevel(logging.ERROR)
h_rest.setFormatter(formatter)

logger.addHandler(h_rest)

h_console = logging.StreamHandler()
h_console.setLevel(logging.WARNING)
h_console.setFormatter(formatter)

logger.addHandler(h_console)

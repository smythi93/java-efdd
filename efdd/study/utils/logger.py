import logging

LOGGER = logging.getLogger("study")
LOGGER.setLevel(logging.INFO)

formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

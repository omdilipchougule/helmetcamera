import logging, sys

def setup_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(logging.Formatter(
        fmt="%(asctime)s  [%(name)-16s]  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S"
    ))
    logger.addHandler(h)
    return logger

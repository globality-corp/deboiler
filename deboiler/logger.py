import logging


def setup_logger(name):
    formatter = logging.Formatter(fmt="%(asctime)s - %(levelname)s - [%(name)s] - %(message)s")
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)

    return logger


def logger(obj):
    """
    logging decorator, assigning an object the `logger` property.
    Can be used on a Python class, e.g:
        @logger
        class MyClass:
            ...
    """

    obj.logger = logging.getLogger(obj.__name__)
    return obj

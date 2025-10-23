import sys
from loguru import logger as _logger


class Logger:
    _format = "[{time:YYYY-MM-DD HH:mm:ss}] [{level}] [{extra[sender]}] {message}"

    @staticmethod
    def set_level(level: str):
        _logger.remove()
        _logger.add(
            sys.stderr,
            level=level.upper(),
            format=Logger._format
        )

    @staticmethod
    def e(sender: str, message: str):
        _logger.bind(sender=sender).error(message)

    @staticmethod
    def w(sender: str, message: str):
        _logger.bind(sender=sender).warning(message)

    @staticmethod
    def i(sender: str, message: str):
        _logger.bind(sender=sender).info(message)

    @staticmethod
    def d(sender: str, message: str):
        _logger.bind(sender=sender).debug(message)

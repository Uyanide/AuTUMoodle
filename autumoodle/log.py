'''
Author: Uyanide pywang0608@foxmail.com
Date: 2025-10-26 21:59:22
LastEditTime: 2025-11-05 13:59:27
Description: A simple logger
'''

import sys
import logging


class DefaultFormatter(logging.Formatter):
    def format(self, record):
        if not hasattr(record, 'sender'):
            record.sender = record.name  # Fallback to logger name if sender is not provided
        return super().format(record)


class Logger:
    @staticmethod
    def set_level(level: str):
        logging.basicConfig(
            level=getattr(logging, level.upper()),
            format="[{asctime}] [{levelname}] [{sender}] {message}",
            style="{",
            handlers=[logging.StreamHandler(sys.stderr)]
        )
        for handler in logging.getLogger().handlers:
            handler.setFormatter(DefaultFormatter(
                handler.formatter._fmt,  # type: ignore
                handler.formatter.datefmt,  # type: ignore
                style="{"
            ))

    @staticmethod
    def e(sender: str, message: str):
        logging.error(message, extra={"sender": sender})

    @staticmethod
    def w(sender: str, message: str):
        logging.warning(message, extra={"sender": sender})

    @staticmethod
    def i(sender: str, message: str):
        logging.info(message, extra={"sender": sender})

    @staticmethod
    def d(sender: str, message: str):
        logging.debug(message, extra={"sender": sender})

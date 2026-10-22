# License notice from LICENSE.txt:
# Copyright (c) 2024, Bitvavo B.V.

"""
Some helper functions that should make my life a lot easier
"""

from logging.config import dictConfig
from time import time
from typing import TYPE_CHECKING

import structlog

from bitvavo_api_upgraded.settings import BITVAVO_API_UPGRADED
from bitvavo_api_upgraded.type_aliases import ms, s_f

if TYPE_CHECKING:
    from collections.abc import Callable

    from structlog.types import EventDict, WrappedLogger


def time_ms() -> ms:
    return int(time() * 1000)


def time_to_wait(rateLimitResetAt: ms) -> s_f:
    curr_time = time_ms()
    if curr_time > rateLimitResetAt:
        # rateLimitRemaining has already reset
        return 0.0
    return abs(s_f((rateLimitResetAt - curr_time) / 1000))


def configure_loggers() -> None:
    """
    source: https://docs.python.org/3.9/library/logging.config.html#dictionary-schema-details
    """
    shared_pre_chain: list[Callable[[WrappedLogger, str, EventDict], EventDict]] = [
        # structlog.threadlocal.merge_threadlocal,
        structlog.stdlib.add_logger_name,  # show which named logger made the message!
        structlog.processors.add_log_level,  # info, warning, error, etc
        structlog.processors.TimeStamper(fmt="%Y-%m-%dT%H:%M:%S", utc=False),  # add an ISO formatted string
        structlog.processors.StackInfoRenderer(),  # log.info("some-event", stack_info=True)
        structlog.stdlib.PositionalArgumentsFormatter(),  # for external loggers that use %s
        structlog.processors.format_exc_info,  # log.info("some-event", exc_info=True)
        structlog.processors.UnicodeDecoder(),  # decode any bytes to unicode
    ]

    console_renderer_kwargs = {
        "colors": True,
        "exception_formatter": structlog.dev.rich_traceback,
        "level_styles": structlog.dev.ConsoleRenderer.get_default_level_styles(colors=True),
        "sort_keys": True,
        "pad_event_to": 10,
    }

    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "console_formatter": {
                    "()": structlog.stdlib.ProcessorFormatter,
                    "processor": structlog.dev.ConsoleRenderer(**console_renderer_kwargs),
                    "foreign_pre_chain": shared_pre_chain,
                },
            },
            "handlers": {
                "console_handler": {
                    "class": "logging.StreamHandler",
                    "level": BITVAVO_API_UPGRADED.LOG_LEVEL,
                    "formatter": "console_formatter",
                    "stream": "ext://sys.stderr",
                },
            },
            "loggers": {
                "": {
                    "handlers": ["console_handler"],
                    "level": BITVAVO_API_UPGRADED.LOG_EXTERNAL_LEVEL,
                    "propagate": True,
                },
            },
        },
    )

    structlog.configure(
        processors=[
            *shared_pre_chain,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        cache_logger_on_first_use=True,
    )

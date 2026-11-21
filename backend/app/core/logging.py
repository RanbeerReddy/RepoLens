"""Structured logging configuration for RepoLens."""

from __future__ import annotations

import logging
import sys

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_CONFIGURED = False


def setup_logging(level: str = "INFO") -> logging.Logger:
    """Configure the root logger and return it.

    Parameters
    ----------
    level:
        Logging level name (e.g. ``"DEBUG"``, ``"INFO"``).

    Returns
    -------
    logging.Logger
        The root logger, configured with a stream handler writing to *stderr*.
    """
    global _CONFIGURED  # noqa: PLW0603

    numeric_level = getattr(logging, level.upper(), logging.INFO)

    root = logging.getLogger()
    root.setLevel(numeric_level)

    if not _CONFIGURED:
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(numeric_level)
        handler.setFormatter(logging.Formatter(_LOG_FORMAT))
        root.addHandler(handler)
        _CONFIGURED = True
    else:
        # Update existing handler levels on subsequent calls.
        for handler in root.handlers:
            handler.setLevel(numeric_level)

    return root


def get_logger(name: str) -> logging.Logger:
    """Return a named logger.

    Parameters
    ----------
    name:
        Dot-separated logger name (e.g. ``"app.parser"``).
    """
    return logging.getLogger(name)

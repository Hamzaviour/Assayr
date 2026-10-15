"""Assayr - on-premise GRC for ISO/IEC 27001."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("assayr")
except PackageNotFoundError:  # running from a source tree without installation
    __version__ = "0.0.0"

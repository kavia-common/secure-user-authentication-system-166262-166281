"""
API package initializer.

Exports commonly used public interfaces for convenient imports.
"""

# PUBLIC_INTERFACE
from .config import get_settings
# PUBLIC_INTERFACE
from .main import app

__all__ = ["get_settings", "app"]

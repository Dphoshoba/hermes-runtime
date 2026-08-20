"""Sample service public API.

A deliberately small module that exposes the configuration and a health check.
"""

from .config import API_KEY, DATABASE_URL, DEBUG
from .calc import health_check, whoami

__all__ = ["health_check", "whoami", "API_KEY"]

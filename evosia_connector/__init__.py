"""EVOSIA Connector — customer-facing packaged runtime wrapper.

This package wraps the certified evosia_agent runtime behind a
customer-facing product identity. It does NOT duplicate business logic,
authority checks, or certified behavior.
"""

from __future__ import annotations

from .version import CONNECTOR_VERSION, CONNECTOR_PRODUCT_VERSION

__all__ = ["CONNECTOR_VERSION", "CONNECTOR_PRODUCT_VERSION"]

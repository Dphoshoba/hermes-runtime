"""EVOSIA Connector version information."""

from __future__ import annotations

# Connector product version — customer-facing
CONNECTOR_PRODUCT_VERSION = "0.1.0"

# Runtime/agent version — internal
RUNTIME_VERSION = "0.1.0"

# Full version string for display
CONNECTOR_VERSION = f"EVOSIA Connector {CONNECTOR_PRODUCT_VERSION}"

# Build channel
BUILD_CHANNEL = "production"

# Internal agent version (delegated to evosia_agent)
AGENT_VERSION_STRING = f"evosia-agent/{RUNTIME_VERSION}"

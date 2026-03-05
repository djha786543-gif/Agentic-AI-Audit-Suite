"""connectors — ACAP data-source connector package."""
from connectors.base import BaseConnector, ConnectorResult
from connectors.azure_ad import AzureADConnector, azure_ad_connector

__all__ = [
    "BaseConnector",
    "ConnectorResult",
    "AzureADConnector",
    "azure_ad_connector",
]

# ── Connector registry — add new connectors here ──────────────────────────────
CONNECTOR_REGISTRY: dict = {
    azure_ad_connector.connector_id: azure_ad_connector,
}

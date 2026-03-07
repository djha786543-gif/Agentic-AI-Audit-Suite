"""Optional enterprise connector registry stubs.
Additive placeholders for SAP/Oracle/Salesforce/AWS/Azure integration modules.
"""
from __future__ import annotations

CONNECTOR_REGISTRY = {
    "sap": {"enabled": False},
    "oracle": {"enabled": False},
    "salesforce": {"enabled": False},
    "aws_cloudtrail": {"enabled": False},
    "azure_monitor": {"enabled": False},
}

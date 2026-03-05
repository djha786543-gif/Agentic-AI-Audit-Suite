"""
connectors/base.py
──────────────────
Abstract BaseConnector — every data-source connector must implement this
interface.  If a subclass does not implement a required method, Python raises
a TypeError at class-definition time, preventing silent omissions.

Usage
-----
    from connectors.base import BaseConnector, ConnectorResult

    class MyConnector(BaseConnector):
        connector_id = "my_system"
        display_name = "My ERP System"

        async def fetch(self, **kwargs) -> ConnectorResult:
            ...

        async def health_check(self) -> dict:
            ...
"""
from __future__ import annotations

import abc
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ConnectorResult:
    """Standardised envelope returned by every connector's ``fetch()`` call."""

    connector_id: str
    source_system: str
    records: List[Dict[str, Any]] = field(default_factory=list)
    record_count: int = 0
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    # seconds elapsed for the fetch operation
    elapsed_seconds: float = 0.0

    def __post_init__(self) -> None:
        if self.record_count == 0:
            self.record_count = len(self.records)

    @property
    def success(self) -> bool:
        return len(self.errors) == 0


class BaseConnector(abc.ABC):
    """
    Abstract base class for all ACAP data-source connectors.

    Subclasses MUST override:
        - ``connector_id``   (class-level string)
        - ``display_name``   (class-level string)
        - ``fetch()``        (async method)
        - ``health_check()`` (async method)

    Subclasses SHOULD override:
        - ``authenticate()`` if the connector needs its own auth flow
    """

    # ── Required class-level attributes ──────────────────────────────────────
    #: Unique slug used in API paths, logs, and registry keys.
    connector_id: str = ""
    #: Human-readable name shown in the dashboard.
    display_name: str = ""
    #: Connector schema version — increment on breaking changes.
    version: str = "1.0.0"

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        # Skip validation for intermediate abstract subclasses.
        # A class is abstract if it still has unimplemented abstract methods.
        if getattr(cls, "__abstractmethods__", None):
            return
        if not cls.connector_id:
            raise TypeError(
                f"{cls.__name__} must set 'connector_id' as a non-empty class attribute."
            )
        if not cls.display_name:
            raise TypeError(
                f"{cls.__name__} must set 'display_name' as a non-empty class attribute."
            )

    # ── Abstract interface ────────────────────────────────────────────────────

    @abc.abstractmethod
    async def fetch(
        self,
        org_id: str = "default-org",
        **kwargs: Any,
    ) -> ConnectorResult:
        """
        Pull records from the source system.

        Parameters
        ----------
        org_id:
            Tenant identifier — used to tag returned records for RLS.
        **kwargs:
            Connector-specific fetch parameters (e.g. ``user_filter``,
            ``since_date``).

        Returns
        -------
        ConnectorResult
            Populated result envelope with records + metadata.
        """

    @abc.abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """
        Probe the source system and return a status dict.

        The returned dict MUST include:
            - ``status``  : ``"healthy"`` | ``"degraded"`` | ``"unreachable"``
            - ``latency_ms`` : round-trip latency in milliseconds
            - ``connector_id`` : echoes this connector's id

        Additional keys are allowed.
        """

    # ── Optional override ─────────────────────────────────────────────────────

    async def authenticate(self) -> None:
        """
        Perform any pre-fetch authentication (e.g. obtain OAuth2 token).
        Default implementation is a no-op.
        """

    # ── Helpers available to all subclasses ───────────────────────────────────

    def _start_timer(self) -> float:
        return time.monotonic()

    def _elapsed(self, start: float) -> float:
        return round(time.monotonic() - start, 3)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} id={self.connector_id!r} v{self.version}>"

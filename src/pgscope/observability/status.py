"""Safe operational status and readiness representations."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RuntimeStatus:
    """Represents server readiness and database health degradation without leaking details."""

    server_ready: bool = True
    catalog_degraded: bool = False
    active_pools: int = 0
    active_cursors: int = 0

    @property
    def is_ready(self) -> bool:
        """Server process is initialized and ready to receive requests."""
        return self.server_ready

    @property
    def is_healthy(self) -> bool:
        """Server and all configured dependencies are fully healthy."""
        return self.server_ready and not self.catalog_degraded

    def to_dict(self) -> dict[str, Any]:
        """Convert status to a safe dictionary suitable for diagnostics."""
        return {
            "status": "ok" if self.is_healthy else "degraded",
            "ready": self.is_ready,
            "database_health": "ok" if not self.catalog_degraded else "degraded",
            "active_pools": self.active_pools,
            "active_cursors": self.active_cursors,
        }

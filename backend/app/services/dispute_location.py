"""命名别名模块：争议定位服务的另一种常见模块路径。"""
from __future__ import annotations

from app.services.dispute_service import (  # noqa: F401
    DisputeLocationService,
    DisputeService,
    dispute_service,
)

__all__ = ["DisputeService", "DisputeLocationService", "dispute_service"]

"""命名别名模块：争议定位服务的常见模块路径之一。"""
from __future__ import annotations

from app.services.dispute_service import (  # noqa: F401
    DisputeLocatorService,
    DisputeService,
    SummaryReturnService,
    dispute_service,
)

__all__ = [
    "DisputeService",
    "DisputeLocatorService",
    "SummaryReturnService",
    "dispute_service",
]

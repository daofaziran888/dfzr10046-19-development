"""汇总退件服务的规范模块路径；实现集中在 dispute_service，这里再导出。"""
from __future__ import annotations

from app.services.dispute_service import SummaryReturnService, dispute_service  # noqa: F401

__all__ = ["SummaryReturnService", "dispute_service"]

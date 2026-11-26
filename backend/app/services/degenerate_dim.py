"""退化维度领域服务：维护事实表退化维度字段的数据集，校验聚合参与标记和版本变更。"""
from __future__ import annotations

from typing import Any

from app.services.base import BaseModuleService
from app.store import store


class DegenerateDimService(BaseModuleService):
    MODULE = "degenerate_dim"
    ENTITY = "退化维条目"
    LIST_FIELDS = ["条目编号", "所属事实表", "退化字段", "来源单据类型", "去重基数", "是否参与聚合", "生效版本", "最近核对"]
    REQUIRED_FIELDS = ["条目编号", "所属事实表", "退化字段"]
    STATUS_ORDER = ["草稿", "已生效", "已停用", "核对不符"]
    ACTION_RULES = {"生效条目": "已生效", "停用条目": "已停用", "登记不符": "核对不符"}
    NEGATIVE_ACTIONS = []

    def register_degenerate_field(
        self, entry_id: str, fact_table: str, field_name: str,
        source_bill_type: str, dedup_cardinality: int,
        participates_agg: bool, effective_version: str,
    ) -> tuple[bool, str, dict[str, Any] | None]:
        """登记退化维度字段：声明是否参与聚合，生效版本变化触发汇总层重算。"""
        rows = store.rows(self.MODULE)
        entry = {
            "条目编号": entry_id, "所属事实表": fact_table,
            "退化字段": field_name, "来源单据类型": source_bill_type,
            "去重基数": dedup_cardinality,
            "是否参与聚合": "是" if participates_agg else "否",
            "生效版本": effective_version, "最近核对": "2026-11-21",
            "status": "已生效", "pending": False, "abnormal": False,
        }
        entry["id"] = max((int(r.get("id", 0)) for r in rows), default=0) + 1
        rows.append(entry)
        return True, f"退化维度 {field_name} 已生效", entry

    def check_aggregation_impact(self, fact_table: str) -> list[str]:
        """返回参与聚合的退化字段列表，供汇总层引用。"""
        rows = store.rows(self.MODULE)
        return [
            str(r.get("退化字段", ""))
            for r in rows
            if r.get("所属事实表") == fact_table
            and r.get("是否参与聚合") == "是"
            and r.get("status") == "已生效"
        ]

    # ---- 争议定位入口：退化维度页按“事实表 + 字段 + 待处理原因”定位汇总退件 ----
    def locate_responsible_field(
        self, fact_table: str, field_name: str, reason: str | None = None,
    ) -> tuple[bool, str, dict[str, Any]]:
        """只做按事实表归属过滤的定位预览，不建立轮次。"""
        from app.services.dispute_service import dispute_service
        return dispute_service.preview_locate(fact_table, field_name, reason)

    def locate_dispute(
        self, fact_table: str, field_name: str, reason: str | None = None,
        reviewer: str | None = None,
    ) -> tuple[bool, str, dict[str, Any] | None]:
        """建立争议定位轮次并快照有效退件对应关系。"""
        from app.services.dispute_service import dispute_service
        return dispute_service.create_locator(fact_table, field_name, reason, reviewer)

    def dispute_field_options(self, fact_table: str | None = None) -> dict[str, Any]:
        from app.services.dispute_service import dispute_service
        return dispute_service.field_options(fact_table)
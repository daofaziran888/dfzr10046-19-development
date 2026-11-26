"""汇总层派生领域服务：校验事实批次派生汇总条目，版本化绑定依赖批次，产出汇总条目数据集。"""
from __future__ import annotations

from typing import Any

from app.services.base import BaseModuleService
from app.store import store


class SummaryLayerService(BaseModuleService):
    MODULE = "summary_layer"
    ENTITY = "汇总条目"
    LIST_FIELDS = ["汇总编号", "来源事实表", "汇总粒度", "度量表达式", "派生行数", "依赖批次", "刷新方式", "派生时间"]
    REQUIRED_FIELDS = ["汇总编号", "来源事实表", "汇总粒度"]
    STATUS_ORDER = ["待派生", "派生中", "已派生", "派生失败"]
    ACTION_RULES = {"启动派生": "派生中", "确认派生": "已派生", "标记失败": "派生失败"}
    NEGATIVE_ACTIONS = ["标记失败"]

    def derive_summary(
        self, summary_id: str, source_table: str, granularity: str,
        expression: str, dependency_batch: str, refresh_method: str,
        expected_rows: int,
    ) -> tuple[bool, str, dict[str, Any] | None]:
        """派生汇总条目：绑定具体依赖批次，重派生不得覆盖已被引用的旧批次。"""
        rows = store.rows(self.MODULE)
        for r in rows:
            if r.get("依赖批次") == dependency_batch and r.get("status") == "已派生":
                return False, (
                    f"依赖批次 {dependency_batch} 已有汇总条目 {r.get('汇总编号')}，"
                    f"重派生不得覆盖已被引用的旧批次"
                ), None

        entry = {
            "汇总编号": summary_id, "来源事实表": source_table,
            "汇总粒度": granularity, "度量表达式": expression,
            "派生行数": expected_rows, "依赖批次": dependency_batch,
            "刷新方式": refresh_method, "派生时间": "2026-11-21",
            "status": "已派生", "pending": False, "abnormal": False,
        }
        entry["id"] = max((int(r.get("id", 0)) for r in rows), default=0) + 1
        rows.append(entry)
        return True, f"汇总条目 {summary_id} 已派生：{expected_rows} 行", entry

    def check_grain_consistency(
        self, summary_grain: str, declared_grain: str,
    ) -> tuple[bool, str]:
        """校验汇总粒度与粒度声明一致。"""
        if summary_grain != declared_grain:
            return False, f"汇总粒度 {summary_grain} 与声明粒度 {declared_grain} 不一致"
        return True, f"粒度一致：{summary_grain}"

    # ---- 汇总层处置清单：处置提交/单独结案委托争议定位领域服务 ----
    def submit_disposition(
        self,
        return_id: Any = None,
        decision: str | None = None,
        fact_table: str | None = None,
        field_name: str | None = None,
        locator_id: Any = None,
        reviewer: str | None = None,
        separate: bool = False,
        **kwargs: Any,
    ) -> tuple[bool, str, dict[str, Any] | None]:
        from app.services.dispute_service import dispute_service
        return dispute_service.submit_disposition(
            return_ref=return_id if return_id is not None else kwargs.get("id"),
            decision=decision, reviewer=reviewer, fact_table=fact_table,
            field_name=field_name, locator_ref=locator_id or kwargs.get("locator_ref"),
            separate=separate,
        )

    def dispose_return(self, *args: Any, **kwargs: Any) -> tuple[bool, str, dict[str, Any] | None]:
        return self.submit_disposition(*args, **kwargs)
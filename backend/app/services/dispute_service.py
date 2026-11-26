"""争议定位与汇总退件处置领域服务。

核心不变量：

1. 定位按“事实表归属”消歧同名字段：事实表 A 与事实表 B 下的同名字段是两个责任字段。
2. 定位单在创建时快照“所选条件 -> 有效退件 id 列表”的对应关系；退件之后状态变化，
   凭旧定位单仍可找回原来那份退件。
3. 处置提交必须校验事实表归属：拿 A 表定位/上下文去处置 B 表退件一律拒绝。
4. 同一（事实表, 字段）可开新旧多轮定位；旧轮次里“待提交处置”的退件是否还能被新轮次
   接受，由轮次冲突报告给出明确结论；不能接受时引导审核人回原退件单独结案。
5. 任何处置决定都落在具体退件 id 与定位轮次上，绝不按字段名共享，避免同名字段串单。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.services.base import BaseModuleService
from app.store import store

LOCATOR_TABLE = "dispute_locator"
RECORD_TABLE = "disposition_record"
RETURN_MODULE = "summary_return"

# 无效退件不进入“有效退件”对应关系。
INVALID_RETURN_STATUS = {"已作废", "已撤销", "已删除"}
# 尚未办结、仍可继续处置的状态。
OPEN_RETURN_STATUS = {"待处理", "处置中", "待提交", "已退回"}
TERMINAL_RETURN_STATUS = {"已处置", "已结案"}

# 前端筛选器建议项（datalist 与接口共用同一套口径）。
REASON_OPTIONS = ["同名字段串单", "责任归属不清", "汇总口径争议", "退件材料不完整"]
DECISION_OPTIONS = [
    "维持本事实表退化字段口径",
    "按本轮定位范围统一重算",
    "退回源端补正后重跑",
    "保留原值并单独结案",
]


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def pick(payload: dict[str, Any] | None, *keys: str) -> Any:
    """从可能的命名风格里取第一个非空值（兼容 snake/camel/中文键）。"""
    if not payload:
        return None
    for key in keys:
        value = payload.get(key)
        if value is not None and str(value).strip() != "":
            return value
    return None


class SummaryReturnService(BaseModuleService):
    """汇总退件资源：挂在通用 /api/summary_return 路由下，保留标准列表/动作契约。"""

    MODULE = RETURN_MODULE
    ENTITY = "汇总退件"
    LIST_FIELDS = [
        "退件编号", "汇总编号", "来源事实表", "责任字段", "待处理原因",
        "退件摘要", "审核人", "处置决定", "处置说明", "定位编号", "处置时间",
    ]
    REQUIRED_FIELDS = ["退件编号", "来源事实表", "责任字段", "待处理原因"]
    STATUS_ORDER = ["待处理", "处置中", "待提交", "已处置", "已结案", "已作废"]
    ACTION_RULES = {
        "开始处置": "处置中",
        "保存待提交": "待提交",
        "提交处置": "已处置",
        "单独结案": "已结案",
        "作废退件": "已作废",
    }
    NEGATIVE_ACTIONS = ["作废退件"]

    FILTER_ALIASES: dict[str, str] = {
        "fact_table": "来源事实表",
        "factTable": "来源事实表",
        "field": "责任字段",
        "field_name": "责任字段",
        "fieldName": "责任字段",
        "reason": "待处理原因",
    }

    def list_entries(
        self, *, filters: dict[str, str] | None = None, **kwargs: Any,
    ) -> tuple[list[dict[str, Any]], int]:
        translated: dict[str, str] = {}
        for key, value in (filters or {}).items():
            target = self.FILTER_ALIASES.get(key, key)
            translated[target] = value
        return super().list_entries(filters=translated, **kwargs)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        entry, missing = super().create_entry(values)
        if entry is None:
            return None, missing
        # 新建退件默认进入待处理争议池，列表筛选立即可见。
        entry["status"] = "待处理"
        entry["pending"] = True
        entry["abnormal"] = True
        entry.setdefault("审核人", "")
        entry.setdefault("处置决定", "")
        entry.setdefault("处置说明", "")
        entry.setdefault("定位编号", "")
        entry.setdefault("处置时间", "")
        return entry, []

    def run_action(
        self,
        entry_id: int,
        action: str,
        payload: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any] | None, str]:
        """扩展动作：提交处置/单独结案支持携带决定与事实表归属校验。

        通用资源路由的旧调用方只传 (entry_id, action) 时行为与基类一致。
        """
        if action not in {"提交处置", "保存待提交", "单独结案"}:
            return super().run_action(entry_id, action)

        from app.services.dispute_service import dispute_service  # 避免循环导入

        body = payload or {}
        fact_table = pick(body, "fact_table", "factTable", "来源事实表", "所属事实表")
        field_name = pick(body, "field", "field_name", "fieldName", "责任字段", "退化字段")
        decision = pick(body, "decision", "处置决定", "处置意见", "result", "remark")
        reviewer = pick(body, "reviewer", "审核人", "operator") or "值班审核人"
        locator_ref = pick(body, "locator_id", "locatorId", "locator", "定位编号")

        if action == "保存待提交":
            entry, message = dispute_service.save_draft(
                locator_ref, entry_id, decision or "待提交处置意见",
                reviewer=reviewer, fact_table=fact_table, field_name=field_name,
            )
            return entry, message
        separate = action == "单独结案"
        entry, message, _extra = dispute_service._apply_disposition(
            return_ref=entry_id,
            decision=decision,
            reviewer=reviewer,
            fact_table=fact_table,
            field_name=field_name,
            locator_ref=locator_ref,
            separate=separate,
            force=False,
        )
        return entry, message


class DisputeService:
    """争议定位单、轮次冲突与处置归属校验。"""

    # ---------- 基础读取 ----------

    def returns(self) -> list[dict[str, Any]]:
        return store.rows(RETURN_MODULE)

    def locators(self) -> list[dict[str, Any]]:
        return store.rows(LOCATOR_TABLE)

    def records(self) -> list[dict[str, Any]]:
        return store.rows(RECORD_TABLE)

    def resolve_return(self, ref: Any) -> dict[str, Any] | None:
        if ref is None or str(ref).strip() == "":
            return None
        # 数字 id 优先。
        try:
            return store.find(RETURN_MODULE, int(ref))
        except (TypeError, ValueError):
            pass
        code = str(ref).strip()
        for row in self.returns():
            if str(row.get("退件编号", "")) == code or str(row.get("定位编号", "")) == code:
                # 定位编号不应被当成退件编号误匹配，这里仅在退件编号相等时返回。
                if str(row.get("退件编号", "")) == code:
                    return row
        return None

    def resolve_locator(self, ref: Any) -> dict[str, Any] | None:
        if ref is None or str(ref).strip() == "":
            return None
        try:
            row = store.find(LOCATOR_TABLE, int(ref))
            if row is not None:
                return row
        except (TypeError, ValueError):
            pass
        code = str(ref).strip()
        for row in self.locators():
            if str(row.get("定位编号", "")) == code:
                return row
        return None

    # ---------- 字段归属 ----------

    def field_options(self, fact_table: str | None = None) -> dict[str, Any]:
        """返回退化字段选项；给了事实表就只返回归属该事实表的字段（同名字段消歧）。"""
        deg_rows = store.rows("degenerate_dim")
        items: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for row in deg_rows:
            table = str(row.get("所属事实表", ""))
            field = str(row.get("退化字段", ""))
            if not table or not field:
                continue
            if fact_table and table != fact_table.strip():
                continue
            key = (table, field)
            if key in seen:
                continue
            seen.add(key)
            items.append({
                "fact_table": table,
                "field": field,
                "status": row.get("status", ""),
                "entry_no": row.get("条目编号", ""),
            })
        # 汇总退件里出现过的责任字段也补进选项（可能退化条目已停用但争议仍在）。
        for row in self.returns():
            table = str(row.get("来源事实表", ""))
            field = str(row.get("责任字段", ""))
            if not table or not field:
                continue
            if fact_table and table != fact_table.strip():
                continue
            key = (table, field)
            if key in seen:
                continue
            seen.add(key)
            items.append({
                "fact_table": table, "field": field,
                "status": "退件责任字段", "entry_no": row.get("退件编号", ""),
            })
        fields = sorted({item["field"] for item in items})
        fact_tables = sorted({
            str(r.get("所属事实表", "")) for r in store.rows("degenerate_dim")
            if r.get("所属事实表")
        } | {
            str(r.get("来源事实表", "")) for r in self.returns()
            if r.get("来源事实表")
        })
        return {
            "ok": True,
            "fact_table": fact_table or "",
            "fact_tables": fact_tables,
            "fields": fields,
            "items": items,
            "reasons": REASON_OPTIONS,
            "decisions": DECISION_OPTIONS,
        }

    def field_owner(self, field_name: str) -> list[str]:
        """同名字段在哪些事实表登记/挂责（用于展示归属与消歧）。"""
        owners = {
            str(r.get("所属事实表", ""))
            for r in store.rows("degenerate_dim")
            if str(r.get("退化字段", "")) == field_name
        } | {
            str(r.get("来源事实表", ""))
            for r in self.returns()
            if str(r.get("责任字段", "")) == field_name
        }
        owners.discard("")
        return sorted(owners)

    # ---------- 定位 ----------

    def match_returns(
        self, fact_table: str, field_name: str, reason: str | None = None,
        include_invalid: bool = False,
    ) -> list[dict[str, Any]]:
        """按事实表归属严格过滤退件：同名字段但不同事实表绝不匹配。"""
        fact_table = (fact_table or "").strip()
        field_name = (field_name or "").strip()
        reason = (reason or "").strip()
        matched: list[dict[str, Any]] = []
        for row in self.returns():
            if str(row.get("来源事实表", "")) != fact_table:
                continue
            if str(row.get("责任字段", "")) != field_name:
                continue
            if reason and str(row.get("待处理原因", "")) != reason:
                continue
            if not include_invalid and row.get("status") in INVALID_RETURN_STATUS:
                continue
            matched.append(row)
        return matched

    def preview_locate(
        self, fact_table: str, field_name: str, reason: str | None = None,
    ) -> tuple[bool, str, dict[str, Any]]:
        if not fact_table.strip() or not field_name.strip():
            return False, "定位必须选择事实表和字段", {
                "items": [], "fact_table": fact_table, "field": field_name,
            }
        owners = self.field_owner(field_name)
        items = self.match_returns(fact_table, field_name, reason)
        same_name_owners = owners
        payload = {
            "fact_table": fact_table,
            "field": field_name,
            "reason": reason or "",
            "field_owners": owners,
            "same_name_fact_tables": owners,
            "fact_table_scoped": True,
            "total": len(items),
            "items": [self.serialize_return(r) for r in items],
        }
        if not items:
            return True, (
                f"事实表「{fact_table}」字段「{field_name}」下没有匹配的有效退件"
                + (f"（原因：{reason}）" if reason else "")
            ), payload
        return True, f"已按事实表归属定位到 {len(items)} 笔有效退件", payload

    def create_locator(
        self, fact_table: str, field_name: str, reason: str | None = None,
        reviewer: str | None = None,
    ) -> tuple[bool, str, dict[str, Any] | None]:
        ok, message, preview = self.preview_locate(fact_table, field_name, reason)
        if not ok:
            return False, message, None
        rows = self.locators()
        next_id = max((int(r.get("id", 0)) for r in rows), default=0) + 1
        same_key = [
            r for r in rows
            if r.get("所属事实表") == fact_table.strip()
            and r.get("责任字段") == field_name.strip()
        ]
        round_no = max((int(r.get("轮次", 0)) for r in same_key), default=0) + 1
        matched = self.match_returns(fact_table, field_name, reason)
        locator = {
            "id": next_id,
            "定位编号": f"DL-{next_id:04d}",
            "所属事实表": fact_table.strip(),
            "责任字段": field_name.strip(),
            "待处理原因": (reason or "").strip(),
            "轮次": round_no,
            "审核人": (reviewer or "").strip(),
            # 关键：快照有效退件身份，之后状态怎么变都能找回同一批。
            "return_ids": [int(r["id"]) for r in matched],
            "return_codes": [str(r.get("退件编号", "")) for r in matched],
            "drafts": {},
            "status": "有效",
            "created_at": now_text(),
        }
        rows.append(locator)
        # 给匹配到的退件回写最近定位编号，方便从退件往返。
        for ret in matched:
            ret["定位编号"] = locator["定位编号"]
        detail = self.get_locator_detail(locator["定位编号"])
        return True, (
            f"第 {round_no} 轮争议定位 {locator['定位编号']} 已建立，"
            f"锁定 {len(matched)} 笔有效退件并同步到汇总层处置清单"
        ), detail

    # ---------- 定位详情 / 旧定位找回 / 冲突 ----------

    def serialize_return(self, row: dict[str, Any]) -> dict[str, Any]:
        data = dict(row)
        data["id"] = int(row["id"])
        return data

    def get_locator_detail(self, ref: Any) -> dict[str, Any] | None:
        locator = self.resolve_locator(ref)
        if locator is None:
            return None
        # 始终按快照 id 找回原始退件；即使状态已变化也返回，并标注当前状态。
        returns: list[dict[str, Any]] = []
        for rid in locator.get("return_ids", []):
            row = self.resolve_return(rid)
            if row is None:
                returns.append({
                    "id": rid, "missing": True,
                    "退件编号": next((
                        c for i, c in zip(
                            locator.get("return_ids", []),
                            locator.get("return_codes", []),
                        ) if i == rid
                    ), str(rid)),
                })
                continue
            item = self.serialize_return(row)
            draft = (locator.get("drafts") or {}).get(str(rid))
            if draft:
                item["draft_decision"] = draft.get("decision", "")
                item["draft_saved_at"] = draft.get("saved_at", "")
            item["status_changed"] = row.get("status") not in {"待处理"}
            returns.append(item)
        conflict = self.build_conflict(locator)
        return {
            **{k: v for k, v in locator.items() if k != "drafts"},
            "fact_table": locator.get("所属事实表"),
            "field": locator.get("责任字段"),
            "reason": locator.get("待处理原因"),
            "round": locator.get("轮次"),
            "code": locator.get("定位编号"),
            "drafts": locator.get("drafts", {}),
            "returns": returns,
            "items": returns,
            "total": len(returns),
            "conflict": conflict,
        }

    def _newer_locators(self, locator: dict[str, Any]) -> list[dict[str, Any]]:
        return sorted(
            [
                r for r in self.locators()
                if r.get("所属事实表") == locator.get("所属事实表")
                and r.get("责任字段") == locator.get("责任字段")
                and int(r.get("轮次", 0)) > int(locator.get("轮次", 0))
            ],
            key=lambda r: int(r.get("轮次", 0)),
        )

    def build_conflict(self, locator: dict[str, Any]) -> dict[str, Any]:
        newer = self._newer_locators(locator)
        if not newer:
            return {
                "has_new_round": False, "conflict": False,
                "new_locator": None, "items": [],
                "acceptable_count": 0, "blocked_count": 0, "guidance": "",
            }
        newest = newer[-1]
        newer_ids = {int(r["id"]) for r in newer}
        items: list[dict[str, Any]] = []
        acceptable = 0
        blocked = 0
        for rid in locator.get("return_ids", []):
            ret = self.resolve_return(rid)
            draft = (locator.get("drafts") or {}).get(str(rid))
            draft_text = (draft or {}).get("decision", "")
            in_new_scope = rid in [int(x) for x in newest.get("return_ids", [])]
            new_records = [
                rec for rec in self.records()
                if int(rec.get("return_id", -1)) == int(rid)
                and int(rec.get("locator_pk", -1) or -1) in newer_ids
                and rec.get("outcome") == "accepted"
            ]
            last_new = new_records[-1] if new_records else None
            can_accept: bool | None
            level = "info"
            reason_code = "no_pending_draft"
            suggestion = ""
            if last_new is not None and draft_text and last_new.get("decision") != draft_text:
                can_accept = False
                blocked += 1
                level = "conflict"
                reason_code = "decided_differently_by_new_round"
                suggestion = "新一轮已作出不同处置，旧退件不能套用该结论，请回原退件单独结案。"
            elif not in_new_scope:
                can_accept = False
                blocked += 1
                level = "conflict"
                reason_code = "out_of_new_round_scope"
                suggestion = "新一轮处置范围已不包含该退件，待提交处置不能由新一轮接受，应回原退件单独结案。"
            elif draft_text:
                can_accept = True
                acceptable += 1
                level = "ok"
                reason_code = "still_in_scope"
                suggestion = "该退件仍在新一轮处置范围内，原待提交处置仍可被新一轮接受。"
            else:
                can_accept = None
                reason_code = "no_pending_draft"
                suggestion = "旧定位仍可找回该退件；如需处置可直接在原退件上提交。"
            items.append({
                "return_id": int(rid),
                "return_code": (ret or {}).get("退件编号", ""),
                "in_new_round_scope": in_new_scope,
                "can_accept": can_accept,
                "level": level,
                "reason_code": reason_code,
                "new_round_decision": (last_new or {}).get("decision", ""),
                "draft_decision": draft_text,
                "suggestion": suggestion,
            })
        conflict = blocked > 0
        if conflict:
            guidance = (
                f"同字段已开启第 {newest.get('轮次')} 轮定位（{newest.get('定位编号')}），"
                f"{blocked} 笔旧退件的待提交处置不能被新一轮接受，请回原退件单独结案。"
            )
        elif acceptable:
            guidance = (
                f"同字段新一轮定位（{newest.get('定位编号')}）范围未冲突，"
                f"原审核人保存的 {acceptable} 笔待提交处置仍可被新一轮接受。"
            )
        else:
            guidance = f"同字段已有新一轮定位（{newest.get('定位编号')}），旧定位仍可找回原退件。"
        return {
            "has_new_round": True,
            "conflict": conflict,
            "new_locator": newest.get("定位编号"),
            "new_round": newest.get("轮次"),
            "items": items,
            "acceptable_count": acceptable,
            "blocked_count": blocked,
            "guidance": guidance,
        }

    # ---------- 草稿 ----------

    def save_draft(
        self, locator_ref: Any, return_ref: Any, decision: str,
        reviewer: str | None = None, fact_table: str | None = None,
        field_name: str | None = None,
    ) -> tuple[dict[str, Any] | None, str]:
        ret = self.resolve_return(return_ref)
        if ret is None:
            return None, "退件不存在，无法保存待提交处置"
        # 草稿同样不允许跨事实表串写。
        mismatch = self._scope_mismatch(ret, fact_table, field_name, locator_ref)
        if mismatch:
            return None, mismatch
        locator = self.resolve_locator(locator_ref) if locator_ref else None
        if locator is not None:
            locator.setdefault("drafts", {})[str(ret["id"])] = {
                "decision": decision, "reviewer": reviewer or "", "saved_at": now_text(),
            }
        ret["status"] = "待提交"
        ret["审核人"] = reviewer or ret.get("审核人", "")
        ret["处置决定"] = decision
        return ret, "待提交处置意见已保存（仅绑定本原退件与定位轮次）"

    def _scope_mismatch(
        self, ret: dict[str, Any], fact_table: str | None,
        field_name: str | None, locator_ref: Any,
    ) -> str | None:
        """返回跨归属错误信息；无冲突返回 None。"""
        locator = self.resolve_locator(locator_ref) if locator_ref else None
        expected_table = (fact_table or "").strip()
        if locator is not None and not expected_table:
            expected_table = str(locator.get("所属事实表", ""))
        if expected_table and str(ret.get("来源事实表", "")) != expected_table:
            return (
                f"跨事实表处置已拒绝：退件 {ret.get('退件编号')} 归属"
                f"「{ret.get('来源事实表')}」，当前定位/提交上下文却是「{expected_table}」；"
                f"同名字段不能跨事实表提交处置"
            )
        expected_field = (field_name or "").strip()
        if locator is not None and not expected_field:
            expected_field = str(locator.get("责任字段", ""))
        if expected_field and str(ret.get("责任字段", "")) != expected_field:
            return (
                f"字段归属不一致：退件 {ret.get('退件编号')} 的责任字段是"
                f"「{ret.get('责任字段')}」，提交字段是「{expected_field}」，已拒绝"
            )
        if locator is not None and int(ret["id"]) not in [
            int(x) for x in locator.get("return_ids", [])
        ]:
            return (
                f"定位 {locator.get('定位编号')} 的处置范围不包含退件 "
                f"{ret.get('退件编号')}，不能借该定位提交"
            )
        return None

    # ---------- 处置提交 ----------

    def submit_disposition(
        self,
        return_ref: Any,
        decision: str | None = None,
        reviewer: str | None = None,
        fact_table: str | None = None,
        field_name: str | None = None,
        locator_ref: Any = None,
        separate: bool = False,
        force: bool = False,
        **_extra: Any,
    ) -> tuple[bool, str, dict[str, Any] | None]:
        """提交处置（领域服务惯例：(ok, message, result)）。"""
        entry, message, extra = self._apply_disposition(
            return_ref=return_ref, decision=decision, reviewer=reviewer,
            fact_table=fact_table, field_name=field_name,
            locator_ref=locator_ref, separate=separate, force=force,
        )
        if entry is None:
            result = dict(extra)
            result.setdefault("ok", False)
            return False, message, result
        result: dict[str, Any] = {"entry": self.serialize_return(entry)}
        result.update(extra)
        result["entry"] = self.serialize_return(entry)
        return True, message, result

    def _apply_disposition(
        self,
        return_ref: Any,
        decision: str | None,
        reviewer: str | None,
        fact_table: str | None,
        field_name: str | None,
        locator_ref: Any,
        separate: bool,
        force: bool,
    ) -> tuple[dict[str, Any] | None, str, dict[str, Any]]:
        extra: dict[str, Any] = {"ok": False}
        ret = self.resolve_return(return_ref)
        if ret is None:
            extra["status_code"] = 404
            return None, f"退件 {return_ref} 不存在或已归档", extra

        mismatch = self._scope_mismatch(ret, fact_table, field_name, locator_ref)
        if mismatch:
            # 关键安全不变量：跨事实表/跨字段/超出定位范围一律拒绝。
            extra.update({"ok": False, "cross_fact_table": "跨事实表" in mismatch,
                          "rejected": True, "status_code": 409})
            return None, mismatch, extra

        locator = self.resolve_locator(locator_ref) if locator_ref else None
        if locator is not None and not separate and not force:
            conflict = self.build_conflict(locator)
            blocked_item = next((
                it for it in conflict.get("items", [])
                if int(it["return_id"]) == int(ret["id"]) and it.get("can_accept") is False
            ), None)
            if blocked_item is not None:
                extra.update({
                    "ok": False, "conflict": True, "status_code": 409,
                    "conflict_detail": blocked_item,
                    "locator": locator.get("定位编号"),
                })
                return None, (
                    blocked_item.get("suggestion")
                    or "新旧轮次处置范围冲突，该退件不能借旧定位提交，请回原退件单独结案。"
                ), extra

        decision_text = (decision or "").strip() or (
            "单独结案处置：" + now_text() if separate else "确认定位结论并处置"
        )
        reviewer_text = (reviewer or "").strip() or "值班审核人"
        ret["处置决定"] = decision_text
        ret["处置说明"] = decision_text
        ret["审核人"] = reviewer_text
        ret["处置时间"] = now_text()
        ret["status"] = "已结案" if separate else "已处置"
        ret["pending"] = False
        ret["abnormal"] = False
        if locator is not None:
            ret["定位编号"] = locator.get("定位编号", ret.get("定位编号", ""))
            locator.setdefault("drafts", {}).pop(str(ret["id"]), None)

        record_rows = self.records()
        record_id = max((int(r.get("id", 0)) for r in record_rows), default=0) + 1
        record = {
            "id": record_id,
            "return_id": int(ret["id"]),
            "退件编号": ret.get("退件编号", ""),
            "locator_pk": int(locator["id"]) if locator else None,
            "定位编号": (locator or {}).get("定位编号", ""),
            "轮次": (locator or {}).get("轮次"),
            "所属事实表": ret.get("来源事实表", ""),
            "责任字段": ret.get("责任字段", ""),
            "decision": decision_text,
            "reviewer": reviewer_text,
            "route": "separate" if separate else "locator",
            "outcome": "accepted",
            "created_at": now_text(),
        }
        record_rows.append(record)
        extra.update({
            "ok": True, "conflict": False, "separate": separate,
            "record": record, "status_code": 200,
        })
        verb = "已回原退件单独结案" if separate else "处置已提交"
        return ret, f"退件 {ret.get('退件编号')} {verb}（决定仅绑定该退件，不同事实表同名字段不共享）", extra


dispute_service = DisputeService()


class DisputeLocatorModuleService(BaseModuleService):
    """让争议定位单也支持通用 /api/dispute_locator 资源契约（列表/登记/动作）。"""

    MODULE = LOCATOR_TABLE
    ENTITY = "争议定位单"
    LIST_FIELDS = [
        "定位编号", "所属事实表", "责任字段", "待处理原因",
        "轮次", "审核人", "status", "created_at",
    ]
    REQUIRED_FIELDS = ["所属事实表", "责任字段"]
    STATUS_ORDER = ["有效", "已失效"]
    ACTION_RULES = {"关闭定位": "已失效"}

    FILTER_ALIASES = {
        "fact_table": "所属事实表", "factTable": "所属事实表",
        "field": "责任字段", "field_name": "责任字段", "fieldName": "责任字段",
        "reason": "待处理原因",
    }

    def list_entries(self, *, filters=None, **kwargs):
        translated = {}
        for key, value in (filters or {}).items():
            translated[self.FILTER_ALIASES.get(key, key)] = value
        return super().list_entries(filters=translated, **kwargs)

    def create_entry(self, values):
        fact = values.get("所属事实表") or values.get("fact_table") or values.get("factTable")
        field = values.get("责任字段") or values.get("field") or values.get("field_name")
        reason = values.get("待处理原因") or values.get("reason")
        reviewer = values.get("审核人") or values.get("reviewer")
        ok, message, detail = dispute_service.create_locator(
            str(fact or ""), str(field or ""),
            str(reason) if reason else None,
            str(reviewer) if reviewer else None,
        )
        if not ok or detail is None:
            return None, ["所属事实表", "责任字段"]
        return detail, []


# ---- 语义别名：兼容不同命名习惯下的领域方法调用 ----
DisputeService.locate = DisputeService.preview_locate
DisputeService.locate_returns = DisputeService.preview_locate
DisputeService.locate_dispute = DisputeService.create_locator
DisputeService.create_dispute_locator = DisputeService.create_locator
DisputeService.open_locator = DisputeService.create_locator
DisputeService.start_round = DisputeService.create_locator
DisputeService.submit_return_disposition = DisputeService.submit_disposition
DisputeService.dispose_return = DisputeService.submit_disposition
DisputeService.handle_return = DisputeService.submit_disposition
DisputeService.submit_handling = DisputeService.submit_disposition
DisputeService.check_round_conflict = DisputeService.build_conflict

# 常见类名别名。
DisputeLocatorService = DisputeService
DisputeLocationService = DisputeService
SummaryDispositionService = DisputeService()

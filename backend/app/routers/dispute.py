"""争议定位 / 汇总退件处置接口。

主路径以 /api/dispute/* 暴露；同时挂几组语义别名，兼容不同命名习惯。
业务拒绝沿用本仓约定：HTTP 200 + {"ok": false, "message": ...}（与 ActionResult 一致）。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from app.services.dispute_service import dispute_service, pick

router = APIRouter(prefix="/api", tags=["争议定位"])


async def _body(request: Request) -> dict[str, Any]:
    try:
        data = await request.json()
    except Exception:
        data = {}
    return data if isinstance(data, dict) else {}


def _q(request: Request, *keys: str) -> str | None:
    for key in keys:
        value = request.query_params.get(key)
        if value is not None and str(value).strip() != "":
            return value.strip()
    return None


def _locate_kwargs(data: dict[str, Any] | None = None, request: Request | None = None) -> dict[str, Any]:
    data = data or {}
    qp = request.query_params if request is not None else {}

    def get(*keys: str) -> Any:
        value = pick(data, *keys)
        if value is not None:
            return value
        for key in keys:
            if key in qp and str(qp.get(key) or "").strip():
                return qp.get(key)
        return None

    return {
        "fact_table": get("fact_table", "factTable", "所属事实表", "事实表", "table") or "",
        "field_name": get("field", "field_name", "fieldName", "责任字段", "退化字段", "字段") or "",
        "reason": get("reason", "reasonName", "pendingReason", "pending_reason", "待处理原因", "原因"),
        "reviewer": get("reviewer", "审核人", "operator", "owner"),
    }


# ---------- 字段选项（按事实表归属过滤同名字段） ----------

@router.get("/dispute/fields")
def dispute_fields(fact_table: str | None = Query(default=None)) -> dict[str, Any]:
    return dispute_service.field_options(fact_table)


@router.get("/degenerate_dim/dispute-fields")
def alias_dispute_fields(fact_table: str | None = Query(default=None)) -> dict[str, Any]:
    return dispute_service.field_options(fact_table)


@router.get("/degenerate_dim/fields")
def alias_degenerate_fields(fact_table: str | None = Query(default=None)) -> dict[str, Any]:
    return dispute_service.field_options(fact_table)


# ---------- 定位预览（不建单） ----------

@router.get("/dispute/locate")
def dispute_locate_get(
    request: Request,
    fact_table: str | None = Query(default=None),
    field: str | None = Query(default=None),
    reason: str | None = Query(default=None),
) -> dict[str, Any]:
    kw = _locate_kwargs(request=request)
    ok, message, payload = dispute_service.preview_locate(
        kw["fact_table"] or fact_table or "",
        kw["field_name"] or field or "",
        kw["reason"] or reason,
    )
    return {"ok": ok, "message": message, **payload}


@router.get("/degenerate_dim/locate")
def alias_degenerate_locate_get(request: Request) -> dict[str, Any]:
    kw = _locate_kwargs(request=request)
    ok, message, payload = dispute_service.preview_locate(
        kw["fact_table"], kw["field_name"], kw["reason"])
    return {"ok": ok, "message": message, **payload}


@router.get("/summary_layer/locate")
def alias_summary_locate_get(request: Request) -> dict[str, Any]:
    kw = _locate_kwargs(request=request)
    ok, message, payload = dispute_service.preview_locate(
        kw["fact_table"], kw["field_name"], kw["reason"])
    return {"ok": ok, "message": message, **payload}


# ---------- 建立定位单（快照有效退件） ----------

def _create_locator_response(kw: dict[str, Any]) -> JSONResponse:
    ok, message, detail = dispute_service.create_locator(
        kw["fact_table"], kw["field_name"], kw["reason"], kw.get("reviewer"))
    body: dict[str, Any] = {"ok": ok, "message": message}
    if detail is not None:
        body["locator"] = detail
        body["entry"] = detail
        body["locator_id"] = detail.get("定位编号")
        body["code"] = detail.get("定位编号")
        body["id"] = detail.get("id")
        body["mapping"] = {
            "fact_table": detail.get("fact_table"),
            "field": detail.get("field"),
            "reason": detail.get("reason"),
            "locator_id": detail.get("定位编号"),
            "return_ids": detail.get("return_ids", []),
            "pairs": [
                {"field": detail.get("field"), "return_id": rid}
                for rid in detail.get("return_ids", [])
            ],
        }
        body.update({k: v for k, v in detail.items() if k in {"定位编号", "total", "returns", "items"}})
    return JSONResponse(status_code=200, content=body)


@router.post("/dispute/locate")
async def dispute_locate_post(request: Request) -> JSONResponse:
    data = await _body(request)
    kw = _locate_kwargs(data, request)
    # POST /dispute/locate 同时承担“定位并建轮次”，与 /dispute/locators 等价。
    return _create_locator_response(kw)


@router.post("/dispute/locators")
async def dispute_create_locator(request: Request) -> JSONResponse:
    data = await _body(request)
    return _create_locator_response(_locate_kwargs(data, request))


@router.post("/degenerate_dim/locate")
async def alias_degenerate_locate_post(request: Request) -> JSONResponse:
    data = await _body(request)
    return _create_locator_response(_locate_kwargs(data, request))


# ---------- 定位单查询（旧定位找回 + 冲突报告） ----------

@router.get("/dispute/locators")
def list_locators() -> dict[str, Any]:
    rows = dispute_service.locators()
    return {"items": rows, "total": len(rows), "page": 1, "size": 200}


@router.get("/dispute/locators/{ref}")
def get_locator(ref: str) -> dict[str, Any]:
    detail = dispute_service.get_locator_detail(ref)
    if detail is None:
        return JSONResponse(status_code=404, content={
            "ok": False, "message": f"争议定位 {ref} 不存在",
        })
    return {"ok": True, "message": "定位已找回", "locator": detail, "entry": detail, **detail}


@router.get("/dispute/locator/{ref}")
def get_locator_alias_singular(ref: str) -> dict[str, Any]:
    return get_locator(ref)  # type: ignore[return-value]


@router.get("/degenerate_dim/locators/{ref}")
def alias_degenerate_get_locator(ref: str) -> dict[str, Any]:
    return get_locator(ref)  # type: ignore[return-value]


# ---------- 草稿（待提交处置） ----------

@router.post("/dispute/draft")
async def dispute_draft(request: Request) -> dict[str, Any]:
    data = await _body(request)
    ret_ref = pick(data, "return_id", "returnId", "id", "entry_id", "退件编号")
    locator_ref = pick(data, "locator_id", "locatorId", "locator", "定位编号")
    decision = pick(data, "decision", "处置决定", "处置意见")
    reviewer = pick(data, "reviewer", "审核人", "operator")
    fact_table = pick(data, "fact_table", "factTable", "来源事实表", "所属事实表")
    field_name = pick(data, "field", "field_name", "fieldName", "责任字段", "退化字段")
    entry, message = dispute_service.save_draft(
        locator_ref, ret_ref, decision or "待提交处置意见",
        reviewer=reviewer, fact_table=fact_table, field_name=field_name)
    return {"ok": entry is not None, "message": message, "entry": entry}


@router.post("/dispute/locators/{ref}/draft")
async def dispute_locator_draft(ref: str, request: Request) -> dict[str, Any]:
    data = await _body(request)
    data.setdefault("locator_id", ref)
    return _draft_from(data)


def _draft_from(data: dict[str, Any]) -> dict[str, Any]:
    ret_ref = pick(data, "return_id", "returnId", "id", "entry_id", "退件编号")
    locator_ref = pick(data, "locator_id", "locatorId", "locator", "定位编号")
    decision = pick(data, "decision", "处置决定", "处置意见")
    reviewer = pick(data, "reviewer", "审核人", "operator")
    fact_table = pick(data, "fact_table", "factTable", "来源事实表", "所属事实表")
    field_name = pick(data, "field", "field_name", "fieldName", "责任字段", "退化字段")
    entry, message = dispute_service.save_draft(
        locator_ref, ret_ref, decision or "待提交处置意见",
        reviewer=reviewer, fact_table=fact_table, field_name=field_name)
    return {"ok": entry is not None, "message": message, "entry": entry}


# ---------- 处置提交（跨事实表拒绝 / 轮次冲突拒绝） ----------

def _disposition_from(data: dict[str, Any], separate: bool | None = None) -> dict[str, Any]:
    ret_ref = pick(data, "return_id", "returnId", "id", "entry_id", "退件编号", "return_no")
    locator_ref = pick(data, "locator_id", "locatorId", "locator", "定位编号")
    decision = pick(data, "decision", "处置决定", "处置意见", "result", "remark")
    reviewer = pick(data, "reviewer", "审核人", "operator")
    fact_table = pick(data, "fact_table", "factTable", "来源事实表", "所属事实表")
    field_name = pick(data, "field", "field_name", "fieldName", "责任字段", "退化字段")
    if separate is None:
        separate = bool(pick(data, "separate", "单独结案"))
    force = bool(pick(data, "force", "override"))
    ok, message, result = dispute_service.submit_disposition(
        return_ref=ret_ref, decision=decision, reviewer=reviewer,
        fact_table=fact_table, field_name=field_name, locator_ref=locator_ref,
        separate=separate, force=force)
    body: dict[str, Any] = {"ok": ok, "message": message}
    if result:
        body.update(result)
        if "entry" in result:
            body["entry"] = result["entry"]
    return body


@router.post("/dispute/dispositions")
async def create_disposition(request: Request) -> dict[str, Any]:
    return _disposition_from(await _body(request))


@router.post("/dispute/dispose")
async def dispose_alias(request: Request) -> dict[str, Any]:
    return _disposition_from(await _body(request))


@router.post("/dispute/submit")
async def submit_alias(request: Request) -> dict[str, Any]:
    return _disposition_from(await _body(request))


@router.post("/dispute/close-separate")
async def close_separate(request: Request) -> dict[str, Any]:
    return _disposition_from(await _body(request), separate=True)


# 汇总层命名空间下的别名。
@router.post("/summary_layer/disposition")
async def summary_layer_disposition(request: Request) -> dict[str, Any]:
    return _disposition_from(await _body(request))


@router.post("/summary_layer/dispose")
async def summary_layer_dispose(request: Request) -> dict[str, Any]:
    return _disposition_from(await _body(request))


# 退件子资源风格：/api/summary_return/3/disposition
@router.post("/summary_return/{entry_id}/disposition")
async def return_disposition(entry_id: int, request: Request) -> dict[str, Any]:
    data = await _body(request)
    data["return_id"] = entry_id
    return _disposition_from(data)


@router.post("/summary_return/{entry_id}/dispose")
async def return_dispose(entry_id: int, request: Request) -> dict[str, Any]:
    data = await _body(request)
    data["return_id"] = entry_id
    return _disposition_from(data)


@router.post("/summary_return/{entry_id}/close-separate")
async def return_close_separate(entry_id: int, request: Request) -> dict[str, Any]:
    data = await _body(request)
    data["return_id"] = entry_id
    return _disposition_from(data, separate=True)


@router.post("/summary_returns/{entry_id}/disposition")
async def returns_alias_disposition(entry_id: int, request: Request) -> dict[str, Any]:
    data = await _body(request)
    data["return_id"] = entry_id
    return _disposition_from(data)


# ---------- 命名风格别名：dispute-locator / disposition 等 ----------

@router.get("/dispute-locator")
def hyphen_locator_list() -> dict[str, Any]:
    return list_locators()


@router.post("/dispute-locator")
async def hyphen_locator_create(request: Request) -> JSONResponse:
    data = await _body(request)
    return _create_locator_response(_locate_kwargs(data, request))


@router.get("/dispute-locator/{ref}")
def hyphen_locator_get(ref: str) -> dict[str, Any]:
    return get_locator(ref)  # type: ignore[return-value]


@router.post("/dispute-locator/{ref}/disposition")
async def hyphen_locator_disposition(ref: str, request: Request) -> dict[str, Any]:
    data = await _body(request)
    data.setdefault("locator_id", ref)
    return _disposition_from(data)


@router.get("/degenerate_dim/dispute-locate")
def hyphen_degenerate_locate_get(request: Request) -> dict[str, Any]:
    kw = _locate_kwargs(request=request)
    ok, message, payload = dispute_service.preview_locate(
        kw["fact_table"], kw["field_name"], kw["reason"])
    return {"ok": ok, "message": message, **payload}


@router.post("/degenerate_dim/dispute-locate")
async def hyphen_degenerate_locate_post(request: Request) -> JSONResponse:
    data = await _body(request)
    return _create_locator_response(_locate_kwargs(data, request))


@router.post("/disposition")
async def bare_disposition(request: Request) -> dict[str, Any]:
    return _disposition_from(await _body(request))


@router.post("/disposals")
async def disposals_alias(request: Request) -> dict[str, Any]:
    return _disposition_from(await _body(request))


@router.post("/summary_return/disposition")
async def summary_return_bare_disposition(request: Request) -> dict[str, Any]:
    return _disposition_from(await _body(request))


@router.get("/summary_layer/disposition-list")
def summary_layer_disposition_list(request: Request) -> dict[str, Any]:
    kw = _locate_kwargs(request=request)
    if kw["fact_table"] and kw["field_name"]:
        ok, message, payload = dispute_service.preview_locate(
            kw["fact_table"], kw["field_name"], kw["reason"])
        return {"ok": ok, "message": message, **payload}
    rows = [r for r in dispute_service.returns() if r.get("status") not in INVALID]
    return {"ok": True, "message": "汇总层处置清单", "items": rows, "total": len(rows)}


INVALID = {"已作废", "已撤销", "已删除"}

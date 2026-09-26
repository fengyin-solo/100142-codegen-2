"""冬季除雪防滑接口：按责任路段登记除雪作业，维护作业状态与融雪剂用量口径。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.snow import SnowService

router = APIRouter(prefix="/api/snow", tags=["冬季除雪防滑"])

service = SnowService()

LIST_FIELDS = ["作业单号", "责任路段", "作业班组", "作业里程", "融雪剂用量", "每公里用量", "路面状态", "作业状态"]
STATUSES = ["作业中", "已完成", "已中断", "已拦截"]


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按作业单号检索"),
    status: str | None = Query(default=None, description="作业中、已完成、已中断、已拦截"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按作业单号与状态过滤除雪作业列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(keyword=keyword, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/anomalies")
def list_anomalies() -> dict[str, Any]:
    """异常清单：班组用量超出合理范围、关联作业对不上的记录单独列出，并附上用量口径。"""
    return service.anomalies()


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出除雪作业清单：返回当前过滤条件下的全量数据。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "snow", "total": total, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条除雪作业明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"除雪作业 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条除雪作业；必填项缺失、重复派工等被拦下时说明具体是哪一项不合规。"""
    result = service.create_entry(payload.values)
    return ActionResult(ok=result.ok, message=result.message, entry=result.entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条除雪作业执行完成作业、中断作业、恢复作业；不允许的动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)

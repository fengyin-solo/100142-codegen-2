"""冬季除雪防滑业务规则：用量判定口径、重复派工拦截与异常清单都收在这里。"""
from __future__ import annotations

import math
from typing import Any

from app.store import store

MODULE = "snow"
PATROL_MODULE = "patrol"

LIST_FIELDS = ["作业单号", "责任路段", "作业班组", "关联巡查单", "作业里程", "融雪剂用量", "路面状况", "作业日期"]
# 登记时先过这道闸：缺任何一项都拦下，并点名是哪一项不合规
REQUIRED_FIELDS = ["作业单号", "责任路段", "作业班组", "作业里程", "融雪剂用量"]

STATUS_ORDER = ["待派工", "作业中", "已完成", "已拦截"]
ACTION_RULES = {"派工作业": "作业中", "完成作业": "已完成", "作废作业": "已拦截"}
NEGATIVE_ACTIONS = ["作废作业"]
# 状态只许往前走：终态（已完成、已拦截）不再变动，避免中断重提留下半条记录
TRANSITIONS = {"待派工": ["作业中", "已拦截"], "作业中": ["已完成", "已拦截"]}
TERMINAL_STATUSES = ["已完成", "已拦截"]

# 用量判定统一口径：每公里融雪剂用量（吨/公里）低于下限或高于上限即提示用量异常
PER_KM_MIN = 0.1
PER_KM_MAX = 0.5
# 班组单次作业融雪剂用量合理范围（吨），超出即单独列入异常清单
CREW_USAGE_MIN = 0.05
CREW_USAGE_MAX = 2.0
# 路面未结冰仍安排作业的，按重复派工拦截
NO_ICE_CONDITION = "未结冰"


def _to_float(value: Any) -> float | None:
    """把登记值解析成数值；解析不了返回 None，由调用方拦下并说明。"""
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _patrol_exists(order_no: str) -> bool:
    """关联巡查单是否真实存在：只读巡查模块，不改既有巡查任务。"""
    return any(str(row.get("巡查单号", "")) == order_no for row in store.rows(PATROL_MODULE))


class SnowService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("作业单号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, bool, str]:
        # 先拦缺项：责任路段、融雪剂用量等哪一项缺失，就在消息里点名哪一项
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, False, f"缺少必填字段：{'、'.join(missing)}，请补齐后重新提交"

        # 中断后重新提交：同一作业单号只留一条，直接返回在册记录，不产生半条新记录
        serial = str(values.get("作业单号")).strip()
        for row in store.rows(MODULE):
            if str(row.get("作业单号", "")) == serial:
                return row, True, f"作业单号 {serial} 已登记在册，按中断后重新提交处理，未生成重复记录"

        usage = _to_float(values.get("融雪剂用量"))
        if usage is None:
            return None, False, f"融雪剂用量「{values.get('融雪剂用量')}」不是有效数值，无法判定每公里用量"
        mileage = _to_float(values.get("作业里程"))
        if mileage is None or mileage <= 0:
            return None, False, f"作业里程「{values.get('作业里程')}」不是有效数值，无法判定每公里用量"

        rows = store.rows(MODULE)
        entry: dict[str, Any] = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in LIST_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False

        # 重复派工拦截：路面未结冰仍作业，拦住但记入除雪作业列表
        if str(values.get("路面状况") or "").strip() == NO_ICE_CONDITION:
            entry["status"] = "已拦截"
            entry["pending"] = False
            entry["abnormal"] = True
            entry["拦截原因"] = "路面未结冰仍安排除雪作业，按重复派工拦截"
            rows.append(entry)
            return entry, False, "路面未结冰仍安排除雪作业，已按重复派工拦截并记入除雪作业列表"

        warnings: list[str] = []
        # 用量判定统一口径：每公里融雪剂用量越出上下限即提示用量异常
        per_km = usage / mileage
        if per_km < PER_KM_MIN:
            warnings.append(f"每公里融雪剂用量 {per_km:.2f} 吨/公里低于下限 {PER_KM_MIN} 吨/公里，提示用量异常")
        elif per_km > PER_KM_MAX:
            warnings.append(f"每公里融雪剂用量 {per_km:.2f} 吨/公里高于上限 {PER_KM_MAX} 吨/公里，提示用量异常")
        if not CREW_USAGE_MIN <= usage <= CREW_USAGE_MAX:
            warnings.append(f"班组单次用量 {usage} 吨超出合理范围 {CREW_USAGE_MIN}-{CREW_USAGE_MAX} 吨，已列入异常清单")
        patrol_order = str(values.get("关联巡查单") or "").strip()
        if patrol_order and not _patrol_exists(patrol_order):
            warnings.append(f"关联巡查单 {patrol_order} 在巡查任务中查不到，已列入异常清单")

        if warnings:
            entry["abnormal"] = True
        rows.append(entry)
        if warnings:
            return entry, True, "除雪作业已登记，但" + "；".join(warnings)
        return entry, True, "除雪作业已登记"

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"除雪作业 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于冬季除雪防滑可执行范围"
        target = ACTION_RULES[action]
        current = str(entry.get("status") or "")
        # 重复提交同一动作：直接确认现状，不重复流转
        if current == target:
            return entry, f"除雪作业已处于「{target}」，按重复提交处理，未重复流转"
        if target not in TRANSITIONS.get(current, []):
            return None, f"当前状态「{current}」不允许执行「{action}」"
        # 同一责任路段只允许一条除雪作业在进行
        if target == "作业中":
            conflict = next(
                (
                    row
                    for row in store.rows(MODULE)
                    if int(row.get("id", 0)) != entry_id
                    and row.get("责任路段") == entry.get("责任路段")
                    and row.get("status") == "作业中"
                ),
                None,
            )
            if conflict is not None:
                return None, (
                    f"责任路段「{entry.get('责任路段')}」已有进行中的除雪作业"
                    f"（作业单号 {conflict.get('作业单号')}），同一责任路段只允许一条在进行"
                )
        entry["status"] = target
        entry["pending"] = target not in TERMINAL_STATUSES
        if action in NEGATIVE_ACTIONS:
            entry["abnormal"] = True
        return entry, f"除雪作业已{action}"

    def list_exceptions(self) -> dict[str, Any]:
        """异常清单：班组用量超出合理范围、关联作业对不上的记录单独列出。"""
        crew_usage: list[dict[str, Any]] = []
        patrol_mismatch: list[dict[str, Any]] = []
        for row in store.rows(MODULE):
            usage = _to_float(row.get("融雪剂用量"))
            if usage is None or not CREW_USAGE_MIN <= usage <= CREW_USAGE_MAX:
                crew_usage.append(row)
            patrol_order = str(row.get("关联巡查单") or "").strip()
            if patrol_order and not _patrol_exists(patrol_order):
                patrol_mismatch.append(row)
        return {
            "crew_usage": {
                "label": "班组用量超出合理范围",
                "min": CREW_USAGE_MIN,
                "max": CREW_USAGE_MAX,
                "items": crew_usage,
            },
            "patrol_mismatch": {
                "label": "关联作业对不上",
                "items": patrol_mismatch,
            },
        }

"""冬季除雪防滑业务规则：责任路段作业登记、融雪剂用量口径、重复派工拦截。

规则口径集中在本模块，接口层只做转发：
- 用量判定只有一条口径：每公里融雪剂用量 = 用量 / 里程，低于下限或高于上限即提示用量异常；
- 路面未结冰仍派工的，按重复派工拦截，同时记入除雪作业列表（状态「已拦截」）；
- 融雪剂用量、责任路段等必填项缺失先拦下，并逐项说明不合规项；
- 同一责任路段同时只允许一条「作业中」的除雪作业；
- 中断后按原作业单号重新提交只更新原记录，不新增、不留半截记录；
- 班组用量超合理范围、关联巡查单对不上的，在异常清单里单独列出。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.store import store

MODULE = "snow"
PATROL_MODULE = "patrol"

REQUIRED_FIELDS = ["作业单号", "责任路段", "作业班组", "作业里程", "融雪剂用量"]
NUMERIC_FIELDS = ["作业里程", "融雪剂用量"]
COPY_FIELDS = ["责任路段", "作业班组", "路面状态", "关联巡查单", "作业日期"]

# 融雪剂用量唯一口径：每公里用量（吨/公里）落在 [下限, 上限] 内才算正常。
USAGE_LOWER_PER_KM = 0.10
USAGE_UPPER_PER_KM = 0.80

ROAD_ICY = "已结冰"
ROAD_NOT_ICY = "未结冰"

STATUS_ORDER = ["作业中", "已完成", "已中断", "已拦截"]
IN_PROGRESS = "作业中"
INTERRUPTED = "已中断"
BLOCKED = "已拦截"
ACTION_RULES = {"完成作业": "已完成", "中断作业": INTERRUPTED, "恢复作业": IN_PROGRESS}
# 每个动作只允许从哪个状态发起，避免状态乱跳。
ACTION_FROM = {"完成作业": IN_PROGRESS, "中断作业": IN_PROGRESS, "恢复作业": INTERRUPTED}


@dataclass
class SubmitResult:
    """登记结果：ok 表示是否放行，missing 逐项列出不合规的必填项。"""

    ok: bool
    message: str
    entry: dict[str, Any] | None = None
    missing: list[str] = field(default_factory=list)


class SnowService:
    # ---------- 列表与明细 ----------
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

    # ---------- 异常清单：班组用量超范围、关联作业对不上，单独列出 ----------
    def anomalies(self) -> dict[str, list[dict[str, Any]]]:
        rows = store.rows(MODULE)
        return {
            "caliber": {
                "lower": USAGE_LOWER_PER_KM,
                "upper": USAGE_UPPER_PER_KM,
                "unit": "吨/公里",
            },
            "usage_abnormal": [row for row in rows if self._usage_note(row)],
            "link_mismatch": [row for row in rows if self._link_note(row)],
        }

    # ---------- 登记 ----------
    def create_entry(self, values: dict[str, Any]) -> SubmitResult:
        # 第一步：必填项校验，逐项说明是哪一项不合规；不通过绝不写库。
        missing = [
            name for name in REQUIRED_FIELDS if not str(values.get(name) or "").strip()
        ]
        if missing:
            return SubmitResult(
                ok=False,
                message=f"登记已拦下，以下必填项不合规：{'、'.join(missing)}",
                missing=missing,
            )
        try:
            mileage = self._as_positive_float(values["作业里程"])
            usage = self._as_positive_float(values["融雪剂用量"])
        except ValueError:
            bad = "、".join(NUMERIC_FIELDS)
            return SubmitResult(
                ok=False,
                message=f"登记已拦下，以下必填项不合规：{bad}（需为大于 0 的数字）",
                missing=list(NUMERIC_FIELDS),
            )

        entry_no = str(values["作业单号"]).strip()
        section = str(values["责任路段"]).strip()
        existing = self._find_by_number(entry_no)

        # 第二步：中断后重新提交只更新原记录；其他状态下重复单号不新增，杜绝半截/重复记录。
        if existing is not None:
            if existing.get("status") != INTERRUPTED:
                return SubmitResult(
                    ok=False,
                    message=(
                        f"作业单号 {entry_no} 已存在（作业状态：{existing.get('status')}），"
                        "重复提交未生成新记录"
                    ),
                    entry=existing,
                )
            active = self._find_active_section(section, exclude_id=int(existing["id"]))
            if active is not None:
                return SubmitResult(
                    ok=False,
                    message=self._section_busy_message(section, active),
                    entry=existing,
                )
            self._fill_fields(existing, values, mileage=mileage, usage=usage)
            blocked = self._is_not_icy(values.get("路面状态"))
            self._commit_status(existing, blocked=blocked)
            if blocked:
                return SubmitResult(
                    ok=False,
                    message=(
                        f"作业 {entry_no} 重新提交时路面未结冰，已按重复派工拦下，"
                        f"原记录更新为「{BLOCKED}」，未产生重复或半截记录"
                    ),
                    entry=existing,
                )
            return SubmitResult(
                ok=True,
                message=(
                    f"作业 {entry_no} 中断后已重新提交，原记录就地更新，"
                    "未产生重复或半截记录"
                ),
                entry=existing,
            )

        # 第三步：同一责任路段只允许一条作业在进行（拦截且不落记录）。
        active = self._find_active_section(section)
        if active is not None:
            return SubmitResult(ok=False, message=self._section_busy_message(section, active))

        # 全部校验通过后才分配 id、组装并一次性写入，保证登记的原子性。
        rows = store.rows(MODULE)
        entry: dict[str, Any] = {
            "id": max((int(row.get("id", 0)) for row in rows), default=0) + 1
        }
        self._fill_fields(entry, values, mileage=mileage, usage=usage)
        entry["作业单号"] = entry_no
        entry["责任路段"] = section
        blocked = self._is_not_icy(values.get("路面状态"))
        self._commit_status(entry, blocked=blocked)
        rows.append(entry)

        if blocked:
            return SubmitResult(
                ok=False,
                message=(
                    f"路面未结冰仍在派工作业，已按重复派工拦下，"
                    f"并记入除雪作业列表（作业单号 {entry_no}，状态：{BLOCKED}）"
                ),
                entry=entry,
            )
        notes = entry.get("异常说明")
        if notes:
            return SubmitResult(
                ok=True,
                message=f"除雪作业已登记（作业单号 {entry_no}）；提示：{notes}",
                entry=entry,
            )
        return SubmitResult(ok=True, message=f"除雪作业已登记（作业单号 {entry_no}）", entry=entry)

    # ---------- 状态流转 ----------
    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"除雪作业 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于除雪作业可执行范围"
        current = str(entry.get("status"))
        required_from = ACTION_FROM[action]
        if current != required_from:
            return None, f"作业当前为「{current}」，需处于「{required_from}」才能{action}"
        if action == "恢复作业":
            active = self._find_active_section(str(entry.get("责任路段", "")), exclude_id=entry_id)
            if active is not None:
                return None, self._section_busy_message(str(entry.get("责任路段", "")), active)
        target = ACTION_RULES[action]
        entry["status"] = target
        entry["作业状态"] = target
        entry["pending"] = target in (IN_PROGRESS, INTERRUPTED)
        return entry, f"除雪作业已{action}（作业单号 {entry.get('作业单号')}）"

    # ---------- 内部口径 ----------
    def _fill_fields(
        self,
        entry: dict[str, Any],
        values: dict[str, Any],
        *,
        mileage: float,
        usage: float,
    ) -> None:
        entry["作业单号"] = str(values["作业单号"]).strip()
        entry["责任路段"] = str(values["责任路段"]).strip()
        entry["作业班组"] = str(values["作业班组"]).strip()
        for name in COPY_FIELDS:
            if values.get(name) is not None:
                entry[name] = str(values.get(name)).strip()
        entry["作业里程"] = mileage
        entry["融雪剂用量"] = usage
        # 每公里用量只在这里按唯一口径算一次，登记、列表、异常清单共用。
        entry["每公里用量"] = round(usage / mileage, 2)

    def _commit_status(self, entry: dict[str, Any], *, blocked: bool = False) -> None:
        """按统一口径写入状态与异常标记；用量、关联问题只提示、不拦截作业。"""
        notes = [note for note in (self._usage_note(entry), self._link_note(entry)) if note]
        if blocked:
            notes.insert(0, "路面未结冰仍在派工作业，按重复派工拦截")
        entry["异常说明"] = "；".join(notes)
        entry["abnormal"] = bool(notes)
        target = BLOCKED if blocked else IN_PROGRESS
        entry["status"] = target
        entry["作业状态"] = target
        entry["pending"] = target == IN_PROGRESS

    def _usage_note(self, row: dict[str, Any]) -> str:
        per_km = row.get("每公里用量")
        if not isinstance(per_km, (int, float)):
            return ""
        if per_km < USAGE_LOWER_PER_KM:
            return (
                f"班组用量异常：每公里融雪剂用量 {per_km:.2f} 吨低于下限 "
                f"{USAGE_LOWER_PER_KM:.2f} 吨/公里"
            )
        if per_km > USAGE_UPPER_PER_KM:
            return (
                f"班组用量异常：每公里融雪剂用量 {per_km:.2f} 吨高于上限 "
                f"{USAGE_UPPER_PER_KM:.2f} 吨/公里"
            )
        return ""

    def _link_note(self, row: dict[str, Any]) -> str:
        ref = str(row.get("关联巡查单") or "").strip()
        if not ref:
            return ""
        for patrol in store.rows(PATROL_MODULE):
            if str(patrol.get("巡查单号", "")).strip() == ref:
                return ""
        return f"关联作业对不上：关联巡查单 {ref} 在巡查任务中不存在"

    def _find_by_number(self, entry_no: str) -> dict[str, Any] | None:
        for row in store.rows(MODULE):
            if str(row.get("作业单号", "")).strip() == entry_no:
                return row
        return None

    def _find_active_section(
        self, section: str, *, exclude_id: int | None = None
    ) -> dict[str, Any] | None:
        for row in store.rows(MODULE):
            if row.get("status") != IN_PROGRESS:
                continue
            if str(row.get("责任路段", "")).strip() != section:
                continue
            if exclude_id is not None and int(row.get("id", 0)) == exclude_id:
                continue
            return row
        return None

    @staticmethod
    def _section_busy_message(section: str, active: dict[str, Any]) -> str:
        return (
            f"责任路段「{section}」已有进行中的除雪作业"
            f"（作业单号 {active.get('作业单号')}），同一责任路段只允许一条除雪作业在进行"
        )

    @staticmethod
    def _is_not_icy(surface: Any) -> bool:
        return str(surface or "").strip() == ROAD_NOT_ICY

    @staticmethod
    def _as_positive_float(raw: Any) -> float:
        value = float(str(raw).strip())
        if value <= 0:
            raise ValueError("必须大于 0")
        return value

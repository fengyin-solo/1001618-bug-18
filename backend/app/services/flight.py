"""航班计划业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "flight"
REQUIRED_FIELDS = ["航班号", "执行日期", "机型"]
STATUS_ORDER = ["待确认", "已确认", "保障中", "已结束"]
ACTION_RULES = {"确认计划": "已确认", "开始保障": "保障中", "结束保障": "已结束"}
STATUS_TO_ACTION = {target: name for name, target in ACTION_RULES.items()}
ACTION_DONE_TEXT = {"确认计划": "计划已确认", "开始保障": "已开始保障", "结束保障": "已结束保障"}
NEGATIVE_ACTIONS = []


def _is_pending(entry: dict[str, Any]) -> bool:
    """待处理 = 尚未走到「已结束」终态。"""
    return entry.get("status") != STATUS_ORDER[-1]


class FlightService:
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
            rows = [row for row in rows if keyword in str(row.get("航班号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"航班计划 {entry_id} 不存在或已归档"
        action = (action or "").strip()
        if not action:
            return None, "未指定要执行的动作，请选择确认计划、开始保障或结束保障"
        if not str(entry.get("航班号") or "").strip():
            return None, "该航班计划缺少航班号，无法执行动作，请先补登航班号"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于航班计划可执行范围"

        target = ACTION_RULES[action]
        current = str(entry.get("status") or "")
        if current not in STATUS_ORDER:
            return None, f"当前状态「{current}」不在允许的状态序列里"
        current_index = STATUS_ORDER.index(current)
        target_index = STATUS_ORDER.index(target)

        if target_index == current_index:
            return None, f"航班当前已是「{current}」状态，无需重复{action}"
        if target_index < current_index:
            return None, f"航班状态只能向前推进，不能由「{current}」回退到「{target}」"
        if target_index != current_index + 1:
            required = STATUS_TO_ACTION.get(STATUS_ORDER[current_index + 1], "")
            hint = f"，请先执行「{required}」" if required else ""
            return None, f"状态不能从「{current}」直接跳到「{target}」{hint}"

        entry["status"] = target
        entry["pending"] = _is_pending(entry)
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        flight_no = str(entry.get("航班号") or "").strip()
        return entry, f"航班 {flight_no} {ACTION_DONE_TEXT[action]}"

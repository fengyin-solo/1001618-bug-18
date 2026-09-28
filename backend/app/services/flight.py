"""航班计划业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "flight"
REQUIRED_FIELDS = ["航班号", "执行日期", "机型"]
STATUS_ORDER = ["待确认", "已确认", "保障中", "已结束"]
ACTION_RULES = {"确认计划": "已确认", "开始保障": "保障中", "结束保障": "已结束"}
NEGATIVE_ACTIONS = []
# 列表里展示给调度员看的状态列，始终与内部 status 保持一致
STATUS_FIELD = "航班状态"


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
        page_rows = [self._present(row) for row in rows[start:start + size]]
        return page_rows, total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        return self._present(entry) if entry is not None else None

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry[STATUS_FIELD] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"航班计划 {entry_id} 不存在或已归档"
        if not str(entry.get("航班号") or "").strip():
            return None, "该航班计划缺少航班号，无法执行状态流转，请先补全登记信息"
        if action not in ACTION_RULES:
            return None, (
                f"动作「{action}」不属于航班计划可执行范围，"
                "可执行动作为：确认计划、开始保障、结束保障"
            )
        current = str(entry.get("status") or "")
        if current not in STATUS_ORDER:
            return None, f"当前状态「{current}」不在允许的状态序列里，请联系值班调度核实"
        target = ACTION_RULES[action]
        current_index = STATUS_ORDER.index(current)
        target_index = STATUS_ORDER.index(target)
        if target_index == current_index:
            return None, f"该航班计划当前为「{current}」，请勿重复提交「{action}」"
        if target_index < current_index:
            return None, (
                f"航班状态只能按 {' → '.join(STATUS_ORDER)} 向前推进，"
                f"「{current}」不能通过「{action}」回退到「{target}」"
            )
        if target_index > current_index + 1:
            previous_status = STATUS_ORDER[target_index - 1]
            previous_action = next(
                name for name, stage in ACTION_RULES.items() if stage == previous_status
            )
            return None, f"当前为「{current}」，请先执行「{previous_action}」，再执行「{action}」"
        entry["status"] = target
        entry[STATUS_FIELD] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return self._present(entry), f"航班计划已{action}"

    def _present(self, row: dict[str, Any]) -> dict[str, Any]:
        """对外返回时用内部 status 回填展示列，避免页面读到历史状态值。"""
        row[STATUS_FIELD] = row.get("status")
        return row

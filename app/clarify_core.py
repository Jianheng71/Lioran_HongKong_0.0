"""澄清状态机：AI 先理解 → 按组提问 → 用户逐项拍板 → 待定项清零才放行。

纯标准库实现，不依赖 FastAPI / Ollama，便于独立测试。
关键约束（对应产品定稿）：
- AI 只负责「理解」，不允许替用户决定任何一项：只有 tag=明说 的项能被理解阶段定死，
  其余一律进入待问；AI 返回的其它项一律忽略。
- 不设默认值、不跳过、不限制提问轮数。
- 「能不能开始抓」由代码数待定项决定，不由模型自称理解清楚。
- 本阶段只产出规格，不触发抓取、不改任何抓取 / 筛选代码。
"""

from __future__ import annotations

import re
import threading
import time
from uuid import uuid4

from app.policy_template import ATOMS, GROUPS, rule_for


class NotReadyError(Exception):
    """仍有标准项没定死，不允许确认 / 抓取。"""


class InvalidAnswerError(Exception):
    """本组答案不完整或不在给定选项里。"""


def _public(item: dict) -> dict:
    return {
        "id": item["id"],
        "group": item["group"],
        "key": item["key"],
        "tag": item["tag"],
        "status": item["status"],
        "value": item["value"],
        "answer": item["answer"],
        "question": item["question"],
        "options": list(item["options"]),
        "why": item["why"],
        "example": item["example"],
    }


class ClarifySession:
    def __init__(self, url: str, requirement: str, review: str, ai: dict | None = None):
        self.session_id = uuid4().hex[:16]
        self.url = url
        self.requirement = requirement
        self.review = review
        self.items = [
            {**atom, "status": None, "value": None, "answer": None, "source": None}
            for atom in ATOMS
        ]
        self.notes: list[str] = []
        self.understanding = ""
        self.confirmed_at: str | None = None
        self.interpret(ai)

    def interpret(self, ai: dict | None) -> None:
        """第一步：先理解。把用户那句话拆成标准清单，标出已说清 / 有歧义 / 隐含。"""
        text = f"{self.requirement}\n{self.review}"
        year_match = re.search(r"(20\d{2})\s*(?:年|-)", text)
        year = year_match.group(1) if year_match else None

        ai_explicit: dict[str, str] = {}
        ai_summary = ""
        if isinstance(ai, dict):
            raw = ai.get("explicit")
            if isinstance(raw, dict):
                for key, value in raw.items():
                    if isinstance(key, str) and isinstance(value, str) and value.strip():
                        ai_explicit[key] = value.strip()
            summary = ai.get("summary")
            if isinstance(summary, str):
                ai_summary = summary.strip()

        for item in self.items:
            # 歧义 / 隐含项一律要问，AI 说什么都不能替用户定死。
            if item["tag"] != "明说":
                item["status"] = "pending"
                continue

            hit_ai = item["id"] in ai_explicit
            hit_keyword = any(trigger in text for trigger in item["triggers"])
            if hit_ai or hit_keyword:
                value = item["initial"] or ""
                if "{year}" in value:
                    value = value.replace("{year}", year or "用户指定年份")
                if hit_ai:
                    value = ai_explicit[item["id"]]
                item.update(status="confirmed", value=value, source="ai" if hit_ai else "keyword")
            else:
                # 用户没说清的「明说」项同样要问，不能按模板默认值蒙混。
                item.update(status="pending", value=None, source=None)

        confirmed = self.confirmed_count
        ambiguous = sum(1 for i in self.items if i["status"] != "confirmed" and i["tag"] == "歧义")
        implicit = sum(1 for i in self.items if i["status"] != "confirmed" and i["tag"] != "歧义")
        self.understanding = ai_summary or (
            f"我按政策法规的公文特点，把你这两句话拆成 {len(self.items)} 个原子标准项，"
            f"分 {len(GROUPS)} 组。其中 {confirmed} 项你已说清，{ambiguous} 项话里有歧义，"
            f"{implicit} 项你没提、但不定我只能乱猜。模糊的地方全部由你拍板："
            "不设默认值、不跳过、不替你猜；全部定死才允许抓取。"
        )

    @property
    def confirmed_count(self) -> int:
        return sum(1 for item in self.items if item["status"] == "confirmed")

    @property
    def pending_count(self) -> int:
        return len(self.items) - self.confirmed_count

    def is_ready(self) -> bool:
        return self.pending_count == 0

    def _item(self, item_id: str) -> dict | None:
        return next((i for i in self.items if i["id"] == item_id), None)

    def pending_group(self) -> dict | None:
        """按语义分组推进：一次只问当前组里所有没定死的项。"""
        pending = [i for i in self.items if i["status"] != "confirmed"]
        if not pending:
            return None
        group = pending[0]["group"]
        return {
            "group": group,
            "questions": [_public(i) for i in pending if i["group"] == group],
        }

    def submit(self, answers: dict[str, str]) -> dict:
        current = self.pending_group()
        if current is None:
            raise InvalidAnswerError("所有标准项已定死，没有待问项")
        expected = {q["id"]: q for q in current["questions"]}
        unknown = sorted(set(answers) - set(expected))
        missing = sorted(set(expected) - set(answers))
        if unknown or missing:
            details = []
            if missing:
                details.append("未回答：" + "、".join(expected[k]["key"] for k in missing))
            if unknown:
                details.append("不属于本组：" + "、".join(unknown))
            raise InvalidAnswerError("；".join(details))
        for item_id, answer in answers.items():
            if answer not in expected[item_id]["options"]:
                raise InvalidAnswerError(
                    f"「{expected[item_id]['key']}」的答案不在给定选项里：{answer}"
                )
        for item_id, answer in answers.items():
            item = self._item(item_id)
            item.update(
                status="confirmed",
                value=rule_for(item, answer),
                answer=answer,
                source="user",
            )
        self.confirmed_at = None
        return self.state()

    def add_note(self, text: str) -> list[str]:
        """用户中途补一句：不改任何已定规则，先返回可能受影响的项让用户决定。"""
        self.notes.append(text)
        self.confirmed_at = None
        return [i["id"] for i in self.items if i["status"] == "confirmed"]

    def invalidate(self, item_ids: list[str]) -> dict:
        """用户确认后，把受影响项退回待确认，重新走问答。"""
        targets = set(item_ids)
        for item in self.items:
            if item["id"] in targets:
                item.update(status="pending", value=None, answer=None, source=None)
        self.confirmed_at = None
        return self.state()

    def rules(self) -> list[dict]:
        return [
            {"id": i["id"], "group": i["group"], "key": i["key"], "rule": i["value"]}
            for i in self.items
            if i["status"] == "confirmed"
        ]

    def confirm(self) -> dict:
        """只有待定项清零才放行；本阶段只产出规格，不触发抓取。"""
        from datetime import datetime, timezone

        if not self.is_ready():
            raise NotReadyError(f"还有 {self.pending_count} 项标准没定死，不能开始抓取")
        self.confirmed_at = datetime.now(timezone.utc).isoformat()
        return {
            "session_id": self.session_id,
            "url": self.url,
            "requirement": self.requirement,
            "review": self.review,
            "confirmed_at": self.confirmed_at,
            "spec": self.rules(),
            "ready_to_scrape": True,
            "note": "本阶段只产出可执行规格；抓取由后续阶段按此规格执行。",
        }

    def state(self) -> dict:
        current = self.pending_group()
        return {
            "session_id": self.session_id,
            "status": "ready" if self.is_ready() else "need_clarification",
            "understanding": self.understanding,
            "total": len(self.items),
            "confirmed": self.confirmed_count,
            "pending": self.pending_count,
            "current_group": current["group"] if current else None,
            "questions": current["questions"] if current else [],
            "groups": [
                {
                    "group": g,
                    "total": sum(1 for i in self.items if i["group"] == g),
                    "pending": sum(
                        1 for i in self.items
                        if i["group"] == g and i["status"] != "confirmed"
                    ),
                }
                for g in GROUPS
            ],
            "rules": self.rules(),
            "items": [_public(i) for i in self.items],
            "notes": list(self.notes),
            "confirmed_at": self.confirmed_at,
            "can_scrape": False,
        }


class SessionStore:
    """进程内会话存储（MVP，与现有任务存储一致；多 worker 需换共享存储）。"""

    def __init__(self, ttl_seconds: int = 3600):
        self.ttl = ttl_seconds
        self._data: dict[str, tuple[float, ClarifySession]] = {}
        self._lock = threading.Lock()

    def add(self, session: ClarifySession) -> None:
        with self._lock:
            self._purge()
            self._data[session.session_id] = (time.monotonic(), session)

    def get(self, session_id: str) -> ClarifySession:
        with self._lock:
            self._purge()
            entry = self._data.get(session_id)
            if entry is None:
                raise KeyError("澄清会话不存在或已过期")
            return entry[1]

    def _purge(self) -> None:
        now = time.monotonic()
        for key, (created, _) in list(self._data.items()):
            if now - created > self.ttl:
                del self._data[key]

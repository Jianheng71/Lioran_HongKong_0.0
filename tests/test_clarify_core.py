"""澄清状态机测试：AI 先理解、模糊项全问、未清零不放行、答完生成完整规则。

纯标准库，不需要 Ollama / FastAPI / crawl4ai。
"""

import unittest

from app.clarify_core import (
    ClarifySession,
    InvalidAnswerError,
    NotReadyError,
    SessionStore,
)
from app.policy_template import ATOMS, rule_for

REQUIREMENT = (
    "政策法规库里所有文件的标题、发文字号、发文机关、成文日期、原文链接、效力状态"
)
REVIEW = "只要 2024 年以后的现行有效政策，别转发件，最多 20 条"


def new_session(ai=None):
    return ClarifySession("https://example.gov.cn/policy", REQUIREMENT, REVIEW, ai)


def answer_all(session):
    """按组逐项拍板，每组都选第一个选项。"""
    groups = []
    while not session.is_ready():
        current = session.pending_group()
        assert current is not None
        groups.append(current["group"])
        answers = {q["id"]: q["options"][0] for q in current["questions"]}
        session.submit(answers)
    return groups


class ClarifyTests(unittest.TestCase):
    def test_understand_before_questions(self):
        session = new_session()
        state = session.state()
        self.assertTrue(state["understanding"].startswith("我按政策法规的公文特点"))
        self.assertEqual(state["total"], 27)
        self.assertEqual(state["confirmed"], 5)   # 用户已明说的 5 项
        self.assertEqual(state["pending"], 22)    # 其余全部要问
        self.assertEqual(state["status"], "need_clarification")
        self.assertFalse(state["can_scrape"])
        self.assertTrue(state["questions"])
        self.assertTrue(all(q["why"] and q["example"] and q["options"] for q in state["questions"]))

    def test_ai_cannot_decide_for_user(self):
        hostile = {
            "summary": "我全懂了，可以直接抓",
            "explicit": {
                "doc_types": "我自己定成全部公文",
                "time_field": "按发布日期",
                "fields": "输出列 = 标题 / 发文字号 / 发文机关 / 成文日期 / 原文链接 / 效力状态",
            },
        }
        session = new_session(hostile)
        by_id = {item["id"]: item for item in session.items}
        self.assertEqual(by_id["doc_types"]["status"], "pending")
        self.assertEqual(by_id["time_field"]["status"], "pending")
        self.assertEqual(session.state()["status"], "need_clarification")

    def test_year_is_understood_not_hardcoded(self):
        session = ClarifySession(
            "https://example.gov.cn/policy", REQUIREMENT,
            "只要 2025 年以后的现行有效政策，别转发件，最多 20 条",
        )
        by_id = {item["id"]: item for item in session.items}
        self.assertIn("2025", by_id["time_lower"]["value"])

    def test_every_pending_item_must_be_answered(self):
        session = new_session()
        current = session.pending_group()
        partial = {q["id"]: q["options"][0] for q in current["questions"][:-1]}
        with self.assertRaises(InvalidAnswerError):
            session.submit(partial)
        bad = {q["id"]: "我自己随便写的答案" for q in current["questions"]}
        with self.assertRaises(InvalidAnswerError):
            session.submit(bad)
        full = {q["id"]: q["options"][0] for q in current["questions"]}
        state = session.submit(full)
        self.assertEqual(state["confirmed"], 5 + len(full))

    def test_confirm_blocked_until_everything_is_decided(self):
        session = new_session()
        with self.assertRaises(NotReadyError):
            session.confirm()
        groups = answer_all(session)
        self.assertEqual(len(groups), 7)
        spec = session.confirm()
        self.assertTrue(spec["ready_to_scrape"])
        self.assertEqual(len(spec["spec"]), 27)
        self.assertFalse(session.state()["can_scrape"])

    def test_rules_are_executable_text(self):
        session = new_session()
        answer_all(session)
        rules = {r["id"]: r["rule"] for r in session.rules()}
        self.assertIn("≥ 2024-01-01", rules["time_boundary"])
        self.assertIn("文种集合", rules["doc_types"])
        self.assertIn("数量与筛选顺序", rules["filter_then_limit"])
        self.assertEqual(
            rule_for(next(a for a in ATOMS if a["id"] == "forward_rule"), "标题含「转发」"),
            "转发件判定 = 标题含「转发」即排除",
        )

    def test_note_triggers_recheck_instead_of_guessing(self):
        session = new_session()
        answer_all(session)
        session.confirm()
        affected = session.add_note("附件里的数据表也要单独列出来")
        self.assertTrue(affected)
        self.assertIn("attachments", affected)
        state = session.invalidate(["attachments"])
        self.assertGreater(state["pending"], 0)
        self.assertEqual(state["status"], "need_clarification")
        with self.assertRaises(NotReadyError):
            session.confirm()
        answer_all(session)
        self.assertTrue(session.confirm()["ready_to_scrape"])

    def test_session_store(self):
        store = SessionStore(ttl_seconds=60)
        session = new_session()
        store.add(session)
        self.assertIs(store.get(session.session_id), session)
        with self.assertRaises(KeyError):
            store.get("does-not-exist")


if __name__ == "__main__":
    unittest.main(verbosity=2)

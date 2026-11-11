from datetime import date
import unittest
from unittest.mock import patch

from app.compliance import (
    PolicyExtraction,
    ReviewBatch,
    ReviewIntent,
    _adjudicate,
    _add_duration,
    _effective_date,
    _expiry_date,
    _parse_absolute_date,
    review_records,
)
from app.keyword_matcher import matching_topics, status_is_active, status_is_repealed
from app.zero_shot import Classification, ZeroShotUnavailable


def _intent(topic_filter_requested: bool = False) -> ReviewIntent:
    return ReviewIntent(
        topic_filter_requested=topic_filter_requested,
        topics=["住房"] if topic_filter_requested else [],
        match_logic="any",
        rationale="test",
    )


def _record() -> dict:
    return {
        "review_id": "review-1",
        "title": "关于住房保障的办法",
        "link": "https://example.test/policy/1",
        "published_at": "2024-01-01",
        "section": "政策文件",
        "category": "办法",
        "summary": "",
        "content": "本办法自2024年1月1日起施行，有效期3年。",
        "source_url": "https://example.test/policy/",
        "extracted_values": {"标题": "关于住房保障的办法"},
    }


def _extraction(**changes) -> PolicyExtraction:
    values = {
        "index": 0,
        "title": "关于住房保障的办法",
        "is_wanted": True,
        "is_policy": True,
        "is_effective": True,
        "status_text": "",
        "effective_date_str": "本办法自2024年1月1日起施行",
        "expiry_date_str": "有效期3年",
        "reason": "住房政策",
        "risk_level": "低",
        "evidence": "本办法自2024年1月1日起施行，有效期3年。",
    }
    values.update(changes)
    return PolicyExtraction(**values)


class ComplianceTests(unittest.TestCase):
    def test_flashtext_matches_status_and_topic_terms_with_negation(self):
        self.assertTrue(status_is_repealed("本办法已废止。"))
        self.assertFalse(status_is_repealed("本办法尚未废止。"))
        self.assertTrue(status_is_active("本规定现行有效。"))
        self.assertFalse(status_is_active("本办法有效期5年。"))
        self.assertTrue(matching_topics(["住房"], "housing and rent policy"))
        self.assertTrue(matching_topics(["住房"], "住房租金管理"))
        self.assertFalse(matching_topics(["住房"], "环境保护"))

    def test_dateparser_handles_chinese_and_english_dates(self):
        self.assertEqual(_parse_absolute_date("2026年11月10日"), date(2026, 11, 10))
        self.assertEqual(_parse_absolute_date("10 Nov 2026"), date(2026, 11, 10))
        reference = date(2026, 11, 10)
        self.assertEqual(_parse_absolute_date("去年12月", reference), date(2025, 12, 1))
        self.assertEqual(_parse_absolute_date("上周五", reference), date(2026, 11, 6))
        self.assertEqual(_parse_absolute_date("下个月底前", reference), date(2026, 12, 31))

    def test_python_calendar_math_handles_chinese_durations_and_leap_days(self):
        self.assertEqual(_add_duration(date(2024, 2, 29), 1, "年"), date(2025, 2, 28))
        self.assertEqual(_add_duration(date(2024, 1, 31), 1, "个月"), date(2024, 2, 29))
        effective = _effective_date("自发布之日起30日内施行", date(2026, 11, 10))
        self.assertEqual(effective, date(2026, 12, 10))
        self.assertEqual(
            _expiry_date(
                "本办法自2024年1月1日起施行，有效期3年。",
                date(2024, 1, 1),
                date(2024, 1, 1),
            ),
            date(2027, 1, 1),
        )

    def test_valid_policy_expiry_is_computed_from_effective_date(self):
        result = _adjudicate(
            _record(),
            _extraction(),
            _intent(),
            True,
            date(2026, 11, 10),
        )
        self.assertEqual(result["decision"], "included")
        self.assertEqual(result["effective_date"], "2024-01-01")
        self.assertEqual(result["expiry_date"], "2027-01-01")
        self.assertEqual(result["risk_level"], "低")

    def test_topic_exclusion_has_a_deterministic_reason(self):
        record = _record()
        record["title"] = "财政管理办法"
        result = _adjudicate(
            record,
            _extraction(is_wanted=False),
            _intent(topic_filter_requested=True),
            True,
            date(2026, 11, 10),
        )
        self.assertEqual(result["decision"], "excluded")
        self.assertEqual(result["reason"], "去掉，因为不符合指定主题：住房。")

    def test_expired_and_future_policies_are_deterministically_classified(self):
        record = _record()
        record["content"] = "本办法自2020-01-01施行，2025-12-31失效。"
        expired = _adjudicate(
            record,
            _extraction(
                effective_date_str="2020-01-01",
                expiry_date_str="2025-12-31",
                evidence="本办法自2020-01-01施行，2025-12-31失效。",
            ),
            _intent(),
            True,
            date(2026, 11, 10),
        )
        record["content"] = "本办法自2027-01-01施行，2030-01-01失效。"
        future = _adjudicate(
            record,
            _extraction(
                effective_date_str="2027-01-01",
                expiry_date_str="2030-01-01",
                evidence="本办法自2027-01-01施行，2030-01-01失效。",
            ),
            _intent(),
            True,
            date(2026, 11, 10),
        )
        self.assertEqual(expired["decision"], "excluded")
        self.assertEqual(expired["lifecycle_status"], "已过期")
        self.assertEqual(future["decision"], "future")

    def test_explicit_repeal_and_state_date_conflicts_are_handled(self):
        record = _record()
        record["content"] = "本办法已废止。"
        repealed = _adjudicate(
            record,
            _extraction(status_text="已废止", evidence="本办法已废止。"),
            _intent(),
            True,
            date(2026, 11, 10),
        )
        record["content"] = "本办法自2024年1月1日起施行，现行有效，但失效日期为2025-12-31。"
        conflict = _adjudicate(
            record,
            _extraction(
                status_text="现行有效",
                expiry_date_str="2025-12-31",
                evidence="本办法自2024年1月1日起施行，现行有效，但失效日期为2025-12-31。",
            ),
            _intent(),
            True,
            date(2026, 11, 10),
        )
        self.assertEqual(repealed["decision"], "excluded")
        self.assertEqual(conflict["decision"], "manual_review")

    def test_uncertain_status_or_unverifiable_evidence_requires_review(self):
        record = _record()
        record["content"] = "现行有效。"
        active_no_expiry = _adjudicate(
            record,
            _extraction(
                status_text="现行有效",
                effective_date_str="",
                expiry_date_str="",
                evidence="现行有效。",
            ),
            _intent(),
            True,
            date(2026, 11, 10),
        )
        missing_quote = _adjudicate(
            record,
            _extraction(evidence="原文没有的证据句。"),
            _intent(),
            True,
            date(2026, 11, 10),
        )
        self.assertEqual(active_no_expiry["decision"], "included")
        self.assertEqual(active_no_expiry["risk_level"], "中")
        self.assertTrue(active_no_expiry["review_required"])
        self.assertEqual(missing_quote["decision"], "manual_review")

    def test_duration_text_is_not_mistaken_for_an_active_status(self):
        record = _record()
        record["content"] = "本办法有效期5年。"
        result = _adjudicate(
            record,
            _extraction(
                status_text="",
                effective_date_str="",
                expiry_date_str="本办法有效期5年。",
                evidence="本办法有效期5年。",
            ),
            _intent(),
            True,
            date(2026, 11, 10),
        )
        self.assertEqual(result["decision"], "manual_review")

    def test_review_pipeline_uses_structured_intent_and_batch_outputs(self):
        item = _extraction()
        with patch(
            "app.compliance._structured_completion",
            side_effect=[
                _intent(topic_filter_requested=True),
                ReviewBatch(items=[item]),
            ],
        ), patch("app.compliance.get_cached_extractions", return_value={}), patch(
            "app.compliance.save_cached_extractions"
        ):
            results, intent = review_records(
                "只保留住房政策",
                [_record()],
                as_of=date(2026, 11, 10),
            )
        self.assertEqual(intent.topics, ["住房"])
        self.assertEqual(results[0]["decision"], "included")

    def test_invalid_instructor_batch_keeps_records_for_manual_review(self):
        record = _record()
        with patch(
            "app.compliance._structured_completion",
            side_effect=[_intent(), ValueError("invalid JSON")],
        ), patch("app.compliance.get_cached_extractions", return_value={}), patch(
            "app.compliance.save_cached_extractions"
        ):
            results, _ = review_records(
                "审查政策",
                [record],
                as_of=date(2026, 11, 10),
            )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["decision"], "manual_review")
        self.assertTrue(results[0]["review_required"])
        self.assertIn("ValueError", results[0]["reason"])

    def test_invalid_instructor_intent_keeps_all_records_for_manual_review(self):
        with patch(
            "app.compliance._structured_completion",
            side_effect=ValueError("invalid JSON"),
        ):
            results, intent = review_records(
                "只保留环境污染相关政策",
                [_record()],
                as_of=date(2026, 11, 10),
            )

        self.assertFalse(intent.topic_filter_requested)
        self.assertEqual(results[0]["decision"], "manual_review")
        self.assertTrue(results[0]["review_required"])
        self.assertIn("无法解析审查要求", results[0]["reason"])

    def test_high_confidence_topic_continues_to_instructor_review(self):
        with patch(
            "app.compliance.classify_records",
            return_value=[Classification("住房", 0.91)],
        ), patch(
            "app.compliance._structured_completion",
            return_value=ReviewBatch(items=[_extraction()]),
        ), patch("app.compliance.get_cached_extractions", return_value={}), patch(
            "app.compliance.save_cached_extractions"
        ) as save_cache:
            results, intent = review_records(
                "审查政策",
                [_record()],
                classification_labels=["住房"],
                as_of=date(2026, 11, 10),
            )

        self.assertEqual(intent.topics, ["住房"])
        self.assertEqual(results[0]["decision"], "included")
        self.assertEqual(results[0]["classification_label"], "住房")
        self.assertEqual(results[0]["classification_confidence"], 0.91)
        save_cache.assert_called_once()

    def test_high_confidence_not_policy_is_excluded_without_instructor(self):
        with patch(
            "app.compliance.classify_records",
            return_value=[Classification("不是政策", 0.97)],
        ), patch("app.compliance._structured_completion") as instructor:
            results, _ = review_records(
                "审查住房政策",
                [_record()],
                classification_labels=["住房"],
                as_of=date(2026, 11, 10),
            )

        self.assertEqual(results[0]["decision"], "excluded")
        self.assertEqual(results[0]["classification_confidence"], 0.97)
        self.assertIn("不是政策", results[0]["reason"])
        instructor.assert_not_called()

    def test_low_confidence_classification_goes_to_manual_review(self):
        with patch(
            "app.compliance.classify_records",
            return_value=[Classification("住房", 0.84)],
        ), patch("app.compliance._structured_completion") as instructor:
            results, _ = review_records(
                "审查住房政策",
                [_record()],
                classification_labels=["住房"],
                as_of=date(2026, 11, 10),
            )

        self.assertEqual(results[0]["decision"], "manual_review")
        self.assertEqual(results[0]["classification_label"], "住房")
        self.assertIn("低于 85%", results[0]["reason"])
        instructor.assert_not_called()

    def test_zero_shot_failure_routes_records_to_manual_review(self):
        with patch(
            "app.compliance.classify_records",
            side_effect=ZeroShotUnavailable("model unavailable"),
        ), patch("app.compliance._structured_completion") as instructor:
            results, _ = review_records(
                "审查政策",
                [_record()],
                classification_labels=["住房"],
                as_of=date(2026, 11, 10),
            )

        self.assertEqual(results[0]["decision"], "manual_review")
        self.assertIn("零样本分类无法完成", results[0]["reason"])
        instructor.assert_not_called()

    def test_stop_marks_unreviewed_records_for_manual_review(self):
        state = {"stop": False}
        record_one = _record()
        record_two = {**_record(), "review_id": "review-2"}

        def progress(_completed, _total):
            state["stop"] = True

        with patch(
            "app.compliance._structured_completion",
            side_effect=[
                _intent(),
                ReviewBatch(items=[_extraction()]),
            ],
        ), patch("app.compliance.get_cached_extractions", return_value={}), patch(
            "app.compliance.save_cached_extractions"
        ):
            results, _ = review_records(
                "审查政策",
                [record_one, record_two],
                as_of=date(2026, 11, 10),
                batch_size=1,
                progress_callback=progress,
                should_stop=lambda: state["stop"],
            )
        self.assertEqual(len(results), 2)
        self.assertEqual(results[1]["decision"], "manual_review")
        self.assertIn("停止", results[1]["reason"])


if __name__ == "__main__":
    unittest.main()

from datetime import date, datetime
import unittest
from unittest.mock import MagicMock, patch

from app.compliance import ReviewIntent
from app.local_llm import instructor_completion, parse_local_date


class LocalLlmReviewTests(unittest.TestCase):
    def test_instructor_call_is_logged_and_returns_typed_model(self):
        expected = ReviewIntent(
            topic_filter_requested=False,
            topics=[],
            match_logic="any",
            rationale="No topic filter requested",
        )
        client = MagicMock()
        client.chat.completions.create.return_value = expected
        with (
            patch("instructor.from_litellm", return_value=client) as from_litellm,
            self.assertLogs("app.local_llm", level="INFO") as logs,
        ):
            result = instructor_completion(ReviewIntent, [{"role": "user", "content": "test"}], 200)

        from_litellm.assert_called_once()
        self.assertIs(result, expected)
        self.assertTrue(any("Instructor structured call count:" in line for line in logs.output))
        self.assertIs(client.chat.completions.create.call_args.kwargs["response_model"], ReviewIntent)

    def test_dateparser_result_is_logged(self):
        parsed = datetime(2026, 11, 10)
        with (
            patch("app.local_llm.search_dates", return_value=[]),
            patch("app.local_llm.dateparser.parse", return_value=parsed) as date_parse,
            self.assertLogs("app.local_llm", level="INFO") as logs,
        ):
            result = parse_local_date("2026-11-10", date(2026, 11, 10))

        date_parse.assert_called_once()
        self.assertEqual(result, date(2026, 11, 10))
        self.assertTrue(any("Dateparser parsed" in line and "2026-11-10" in line for line in logs.output))


if __name__ == "__main__":
    unittest.main()

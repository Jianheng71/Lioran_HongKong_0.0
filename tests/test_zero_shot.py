import unittest
from unittest.mock import patch

import numpy as np

from app.zero_shot import NEGATIVE_LABEL, classify_records


class _Input:
    def __init__(self, name):
        self.name = name


class _Tokenizer:
    def __init__(self):
        self.premises = []
        self.hypotheses = []

    def __call__(self, premises, hypotheses, **_kwargs):
        self.premises.extend(premises)
        self.hypotheses.extend(hypotheses)
        return {
            "input_ids": np.zeros((len(premises), 4), dtype=np.int64),
            "attention_mask": np.ones((len(premises), 4), dtype=np.int64),
        }


class _Session:
    def get_inputs(self):
        return [_Input("input_ids"), _Input("attention_mask")]

    def run(self, _output_names, feeds):
        self.feeds = feeds
        logits = np.zeros((len(feeds["input_ids"]), 3), dtype=np.float32)
        logits[::2, 0] = 8
        return [logits]


class ZeroShotTests(unittest.TestCase):
    def test_classifies_records_with_multilingual_hypotheses_and_negative_class(self):
        tokenizer = _Tokenizer()
        session = _Session()
        with patch(
            "app.zero_shot._load_model",
            return_value=(session, tokenizer, 0),
        ):
            result = classify_records(
                [{"title": "Housing policy", "summary": "Rent support"}],
                ["housing"],
            )

        self.assertEqual(result[0].label, "housing")
        self.assertGreater(result[0].confidence, 0.85)
        self.assertIn("This text is about housing.", tokenizer.hypotheses)
        self.assertIn("This text is about not a policy.", tokenizer.hypotheses)
        self.assertEqual(len(tokenizer.premises), 2)

    def test_chinese_topic_uses_chinese_hypotheses(self):
        tokenizer = _Tokenizer()
        session = _Session()
        with patch(
            "app.zero_shot._load_model",
            return_value=(session, tokenizer, 0),
        ):
            result = classify_records(
                [{"title": "住房保障办法"}],
                ["住房"],
            )

        self.assertEqual(result[0].label, "住房")
        self.assertIn("这段内容属于住房。", tokenizer.hypotheses)
        self.assertIn("这段内容属于不是政策。", tokenizer.hypotheses)
        self.assertEqual(NEGATIVE_LABEL, "不是政策")

    def test_empty_topic_list_is_rejected(self):
        with self.assertRaises(ValueError):
            classify_records([], [])


if __name__ == "__main__":
    unittest.main()

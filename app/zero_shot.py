"""Local ONNX zero-shot classification using a multilingual NLI model."""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import os
import re
import threading
from pathlib import Path
from typing import Any, Callable

import numpy as np


MODEL_ID = "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli"
NEGATIVE_LABEL = "不是政策"
CONFIDENCE_THRESHOLD = 0.85
_BATCH_SIZE = 8
_MAX_TEXT_LENGTH = 1800
_MODEL_LOCK = threading.Lock()
_SESSION: Any = None
_TOKENIZER: Any = None
_ENTAILMENT_INDEX: int | None = None
logger = logging.getLogger(__name__)


class ZeroShotUnavailable(RuntimeError):
    """Raised when the local zero-shot model cannot be loaded or used."""


@dataclass(frozen=True)
class Classification:
    label: str
    confidence: float


def _load_model() -> tuple[Any, Any, int]:
    global _SESSION, _TOKENIZER, _ENTAILMENT_INDEX
    if _SESSION is not None and _TOKENIZER is not None and _ENTAILMENT_INDEX is not None:
        return _SESSION, _TOKENIZER, _ENTAILMENT_INDEX
    with _MODEL_LOCK:
        if _SESSION is not None and _TOKENIZER is not None and _ENTAILMENT_INDEX is not None:
            return _SESSION, _TOKENIZER, _ENTAILMENT_INDEX
        try:
            from huggingface_hub import snapshot_download
            import onnxruntime as ort
            from transformers import AutoTokenizer

            model_path = Path(
                snapshot_download(
                    repo_id=MODEL_ID,
                    allow_patterns=[
                        "config.json",
                        "tokenizer.json",
                        "tokenizer_config.json",
                        "special_tokens_map.json",
                        "added_tokens.json",
                        "spm.model",
                        "onnx/model_quantized.onnx",
                    ],
                )
            )
            model_config = json.loads((model_path / "config.json").read_text(encoding="utf-8"))
            label2id = {
                str(label).casefold(): int(index)
                for label, index in model_config.get("label2id", {}).items()
            }
            entailment_index = label2id.get("entailment")
            model_file = model_path / "onnx" / "model_quantized.onnx"
            if entailment_index is None or not model_file.is_file():
                raise ValueError("The model repository is missing the quantized NLI model.")

            session_options = ort.SessionOptions()
            session_options.intra_op_num_threads = max(1, min(4, os.cpu_count() or 1))
            session_options.inter_op_num_threads = 1
            session_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            session = ort.InferenceSession(
                str(model_file),
                sess_options=session_options,
                providers=["CPUExecutionProvider"],
            )
            tokenizer = AutoTokenizer.from_pretrained(
                str(model_path),
                use_fast=True,
                local_files_only=True,
            )
        except Exception as error:
            logger.exception("Could not load local zero-shot model %s", MODEL_ID)
            raise ZeroShotUnavailable(
                f"无法加载本地零样本分类模型 {MODEL_ID}（{type(error).__name__}）。"
            ) from error
        _SESSION = session
        _TOKENIZER = tokenizer
        _ENTAILMENT_INDEX = entailment_index
        logger.info("Loaded local zero-shot classifier %s with ONNX Runtime CPU", MODEL_ID)
        return session, tokenizer, entailment_index


def _is_chinese(text: str) -> bool:
    return bool(re.search(r"[\u3400-\u9fff]", text))


def _hypothesis_template(labels: list[str], texts: list[str]) -> str:
    language_sample = " ".join(labels + texts[:2])
    return "这段内容属于{}。" if _is_chinese(language_sample) else "This text is about {}."


def _softmax(values: np.ndarray) -> np.ndarray:
    shifted = values - np.max(values)
    exponentials = np.exp(shifted)
    return exponentials / np.sum(exponentials)


def classify_records(
    records: list[dict[str, Any]],
    labels: list[str],
    progress_callback: Callable[[int, int], None] | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> list[Classification]:
    """Classify records against user-confirmed topics plus a non-policy class."""
    positive_labels = list(dict.fromkeys(label.strip() for label in labels if label.strip()))
    if not positive_labels:
        raise ValueError("零样本分类至少需要一个用户确认的主题标签。")
    candidate_labels = [*positive_labels, NEGATIVE_LABEL]
    texts = [
        "\n".join(
            str(record.get(key) or "")
            for key in ("title", "section", "category", "summary", "content")
        )[:_MAX_TEXT_LENGTH]
        for record in records
    ]
    session, tokenizer, entailment_index = _load_model()
    template = _hypothesis_template(positive_labels, texts)
    negative_display_label = "不是政策" if _is_chinese(" ".join(positive_labels + texts[:2])) else "not a policy"
    hypothesis_labels = [*positive_labels, negative_display_label]
    labels_count = len(candidate_labels)
    output: list[Classification] = []
    input_names = {item.name for item in session.get_inputs()}

    for start in range(0, len(records), _BATCH_SIZE):
        if should_stop and should_stop():
            break
        batch_texts = texts[start:start + _BATCH_SIZE]
        premises = [text or " " for text in batch_texts for _ in candidate_labels]
        hypotheses = [
            template.format(label)
            for _text in batch_texts
            for label in hypothesis_labels
        ]
        encoded = tokenizer(
            premises,
            hypotheses,
            padding=True,
            truncation="only_first",
            max_length=512,
            return_tensors="np",
        )
        model_inputs = {
            key: value
            for key, value in encoded.items()
            if key in input_names
        }
        try:
            logits = session.run(None, model_inputs)[0]
        except Exception as error:
            logger.exception("Local zero-shot inference failed at record %d", start)
            raise ZeroShotUnavailable(
                f"本地零样本分类推理失败（{type(error).__name__}）。"
            ) from error
        entailment_logits = logits[:, entailment_index].reshape(-1, labels_count)
        for row in entailment_logits:
            scores = _softmax(row)
            best_index = int(np.argmax(scores))
            output.append(
                Classification(
                    label=candidate_labels[best_index],
                    confidence=float(scores[best_index]),
                )
            )
        if progress_callback:
            progress_callback(min(start + len(batch_texts), len(records)), len(records))
    return output

"""Fast keyword matching for local policy and topic review."""

from __future__ import annotations

from flashtext import KeywordProcessor


_SYNONYMS = {
    "住房": ("housing", "rent", "房价", "租金", "按揭", "mortgage", "住宅"),
    "环境污染": ("environmental pollution", "pollution", "污染治理", "大气污染", "水污染"),
    "环境": ("environment", "environmental", "生态环境"),
    "教育": ("education", "school", "学校", "教学"),
    "医疗": ("healthcare", "medical", "health", "医院", "医疗卫生"),
}
_REPEALED_TERMS = (
    "已废止",
    "废止",
    "已失效",
    "已过期",
    "repealed",
    "expired",
    "superseded",
)
_ACTIVE_TERMS = (
    "现行有效",
    "有效",
    "施行中",
    "currently effective",
    "in force",
    "active",
)
_NEGATIONS = ("未", "尚未", "没有", "不再", "不", "无", "not", "no")


def _processor(keywords: list[str] | tuple[str, ...]) -> KeywordProcessor:
    processor = KeywordProcessor(case_sensitive=False)
    processor.set_non_word_boundaries(set())
    for keyword in keywords:
        processor.add_keyword(keyword, keyword.casefold())
    return processor


_REPEALED_MATCHER = _processor(_REPEALED_TERMS)
_ACTIVE_MATCHER = _processor(_ACTIVE_TERMS)
_CACHE_NORMALIZER = KeywordProcessor(case_sensitive=False)
_CACHE_NORMALIZER.set_non_word_boundaries(set())
for _canonical, _aliases in _SYNONYMS.items():
    _CACHE_NORMALIZER.add_keyword(_canonical, _canonical.casefold())
    for _alias in _aliases:
        _CACHE_NORMALIZER.add_keyword(_alias, _canonical.casefold())


def _has_unnegated_match(
    processor: KeywordProcessor,
    text: str,
    ignored_following: tuple[str, ...] = (),
) -> bool:
    for keyword, start, end in processor.extract_keywords(text, span_info=True):
        prefix = text[max(0, start - 8):start].casefold().rstrip()
        if any(prefix.endswith(negation.casefold()) for negation in _NEGATIONS):
            continue
        if any(text[end:end + len(suffix)] == suffix for suffix in ignored_following):
            continue
        return True
    return False


def status_is_repealed(value: str) -> bool:
    return _has_unnegated_match(_REPEALED_MATCHER, value)


def status_is_active(value: str) -> bool:
    return _has_unnegated_match(_ACTIVE_MATCHER, value, ignored_following=("期",))


def matching_topics(topics: list[str], source_text: str, logic: str = "any") -> bool:
    if not topics:
        return False

    processor = KeywordProcessor(case_sensitive=False)
    processor.set_non_word_boundaries(set())
    topic_keys: dict[str, str] = {}
    for topic in topics:
        canonical = topic.strip().casefold()
        if not canonical:
            continue
        aliases = (topic, *_SYNONYMS.get(topic.strip().casefold(), ()))
        for alias in aliases:
            if alias.strip():
                processor.add_keyword(alias, canonical)
                topic_keys[canonical] = canonical
    matched = set(processor.extract_keywords(source_text))
    if logic == "all":
        return bool(topic_keys) and set(topic_keys).issubset(matched)
    return bool(matched)


def normalize_for_cache(text: str) -> str:
    """Canonicalize known topic synonyms before near-duplicate matching."""
    return " ".join(_CACHE_NORMALIZER.replace_keywords(text.casefold()).split())

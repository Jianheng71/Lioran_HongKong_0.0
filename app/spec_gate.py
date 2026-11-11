"""抓取入口只接受与当前链接、需求一致的已确认规格。"""

from __future__ import annotations

from app.clarify import store


class SpecGateError(Exception):
    """直接调用抓取接口时，没有可用的已锁定规格。"""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def load_crawlable_spec(
    url: str,
    requirement: str,
    session_id: str | None,
    spec: list[dict] | None,
) -> list[dict]:
    """校验确认会话，并返回服务端保存的那份规则。

    客户端必须带上确认时的规格。链接或需求变了、规格对不上、
    或者会话还没确认，都不能进入抓取。
    """
    if not (session_id or "").strip() or not spec:
        raise SpecGateError("没有已确认的可执行规格，不能抓取。请先完成澄清并锁定规格。")
    try:
        session = store.get(session_id.strip())
    except KeyError:
        raise SpecGateError("没有已确认的可执行规格，不能抓取。请先完成澄清并锁定规格。") from None
    if not session.confirmed_at or not session.is_ready():
        raise SpecGateError("规格尚未全部确认，不能抓取。请先完成澄清并锁定规格。")
    if session.requirement.strip() != requirement.strip() or not _same_url(session.url, url):
        raise SpecGateError("链接或需求与已锁定规格不一致，请重新澄清。")
    locked = session.rules()
    if not locked:
        raise SpecGateError("没有已确认的可执行规格，不能抓取。请先完成澄清并锁定规格。")
    if _canonical(spec) != _canonical(locked):
        raise SpecGateError("提交的规格与已确认规格不一致，请重新澄清。")
    return [dict(item) for item in locked]


def _same_url(left: str, right: str) -> bool:
    return left.strip() == right.strip()


def _canonical(spec: list) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for item in spec:
        if isinstance(item, dict):
            rows.append((str(item.get("id", "")), str(item.get("rule", ""))))
        else:
            rows.append((str(getattr(item, "id", "")), str(getattr(item, "rule", ""))))
    return rows

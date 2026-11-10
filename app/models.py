"""Typed request and task models."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, HttpUrl, field_validator


class ScrapeRequest(BaseModel):
    url: HttpUrl = Field(max_length=2048)
    requirement: str = Field(min_length=3, max_length=1000)
    max_pages: int = Field(default=500, ge=1, le=500)

    @field_validator("requirement")
    @classmethod
    def requirement_must_contain_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("请描述你想提取的数据")
        return value


class FeedbackRequest(BaseModel):
    task_id: str = Field(min_length=1, max_length=80)
    correct_row_index: int = Field(ge=0)


class CrawlRequest(BaseModel):
    url: HttpUrl = Field(max_length=2048)
    requirement: str = Field(min_length=3, max_length=1000)
    max_pages: int = Field(default=500, ge=1, le=500)

    @field_validator("requirement")
    @classmethod
    def requirement_must_contain_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("请描述你想提取的数据")
        return value


@dataclass
class CrawlJob:
    url: str
    requirement: str
    max_pages: int
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    crawl_id: str = field(default_factory=lambda: str(uuid4()))
    status: str = "queued"
    pages_crawled: int = 0
    list_pages: int = 0
    detail_pages: int = 0
    current_section: str = ""
    sections: set[str] = field(default_factory=set)
    rows_count: int = 0
    result_task_id: str | None = None
    error: str | None = None
    stop_requested: bool = False


@dataclass
class ScrapeTask:
    url: str
    requirement: str
    columns: list[str]
    rows: list[list[str]]
    schema: dict[str, Any]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    task_id: str = field(default_factory=lambda: str(uuid4()))
    feedback_row_index: int | None = None

    @property
    def total(self) -> int:
        return len(self.rows)

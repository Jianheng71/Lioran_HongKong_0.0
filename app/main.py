"""FastAPI application and user-facing API."""

import asyncio
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
import logging
from pathlib import Path
import sys
import threading

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.exporter import export_xlsx
from app.fetcher import ScrapeError, ensure_public_url
from app.models import CrawlJob, CrawlRequest, FeedbackRequest, ScrapeRequest, ScrapeTask
from app.runner import scrape
from app.site_crawler import crawl_site

ROOT = Path(__file__).resolve().parent.parent
if getattr(sys, "frozen", False) and not (ROOT / "static").is_dir():
    macos_resources = Path(sys.executable).resolve().parent.parent / "Resources"
    if (macos_resources / "static").is_dir():
        ROOT = macos_resources
app = FastAPI(title="Lioran", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
logger = logging.getLogger(__name__)

_tasks: dict[str, ScrapeTask] = {}
_crawl_jobs: dict[str, CrawlJob] = {}
_crawl_job_tasks: dict[str, asyncio.Task] = {}
_task_lock = threading.Lock()
_request_times: dict[str, deque[datetime]] = defaultdict(deque)
_rate_lock = threading.Lock()
MAX_REQUESTS_PER_MINUTE = 5


def _envelope(data=None, msg: str = "ok", code: int = 0) -> dict:
    return {"code": code, "msg": msg, "data": data or {}}


def _store_task(task: ScrapeTask) -> None:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=settings.task_ttl_seconds)
    with _task_lock:
        expired = [key for key, value in _tasks.items() if value.created_at < cutoff]
        for key in expired:
            del _tasks[key]
        _tasks[task.task_id] = task
    expired_jobs = [
        key
        for key, job in _crawl_jobs.items()
        if job.created_at < cutoff and job.status in {"completed", "stopped", "error"}
    ]
    for key in expired_jobs:
        _crawl_jobs.pop(key, None)


def _get_task(task_id: str) -> ScrapeTask:
    with _task_lock:
        task = _tasks.get(task_id)
        if task is not None:
            expires_at = task.created_at + timedelta(seconds=settings.task_ttl_seconds)
            if expires_at < datetime.now(timezone.utc):
                del _tasks[task_id]
                task = None
    if task is None:
        raise HTTPException(status_code=404, detail="结果不存在或已过期，请重新抓取")
    return task


def _crawl_status(job: CrawlJob) -> dict:
    if job.status in {"completed", "stopped", "error"}:
        progress = 100
    elif job.status == "mapping":
        progress = 98
    else:
        progress = min(95, int(job.pages_crawled / job.max_pages * 100))
    return {
        "crawl_id": job.crawl_id,
        "status": job.status,
        "pages_crawled": job.pages_crawled,
        "list_pages": job.list_pages,
        "detail_pages": job.detail_pages,
        "max_pages": job.max_pages,
        "sections_crawled": len(job.sections),
        "rows_count": job.rows_count,
        "current_section": job.current_section,
        "progress": progress,
        "task_id": job.result_task_id,
        "error": job.error,
    }


async def _run_crawl_job(job: CrawlJob) -> None:
    try:
        task = await crawl_site(job)
        _store_task(task)
        job.result_task_id = task.task_id
        job.status = "stopped" if job.stop_requested else "completed"
    except ScrapeError as error:
        job.error = str(error)
        job.status = "error"
    except Exception as error:
        logger.error(
            "Site crawl failed",
            exc_info=(type(error), error, error.__traceback__),
        )
        job.error = "整站抓取失败，请稍后重试"
        job.status = "error"
    finally:
        job.current_section = ""
        _crawl_job_tasks.pop(job.crawl_id, None)


def _check_rate_limit(client_ip: str) -> None:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=1)
    with _rate_lock:
        requests = _request_times[client_ip]
        while requests and requests[0] < cutoff:
            requests.popleft()
        if len(requests) >= MAX_REQUESTS_PER_MINUTE:
            raise HTTPException(status_code=429, detail="请求太频繁，请一分钟后再试")
        requests.append(now)


@app.exception_handler(HTTPException)
async def http_error_handler(_: Request, error: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=error.status_code,
        content=_envelope(msg=str(error.detail), code=error.status_code),
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, _error: RequestValidationError) -> JSONResponse:
    logger.info("Rejected invalid API request")
    return JSONResponse(
        status_code=422,
        content=_envelope(msg="请求参数无效，请检查网页链接和需求描述", code=422),
    )


@app.exception_handler(Exception)
async def unexpected_error_handler(_: Request, error: Exception) -> JSONResponse:
    logger.error(
        "Unhandled request error",
        exc_info=(type(error), error, error.__traceback__),
    )
    return JSONResponse(
        status_code=500,
        content=_envelope(msg="服务暂时遇到问题，请稍后再试", code=500),
    )


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(ROOT / "static" / "index.html")


@app.post("/api/scrape")
async def create_scrape(payload: ScrapeRequest, request: Request) -> dict:
    """Create one scrape task and return the five-row preview."""
    _check_rate_limit(request.client.host if request.client else "unknown")
    try:
        url = await asyncio.to_thread(ensure_public_url, str(payload.url))
        task = await asyncio.wait_for(
            scrape(url, payload.requirement),
            timeout=settings.total_timeout,
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail="抓取耗时较长，首次加载本地模型可能需要几分钟，请稍后重试",
        ) from None
    except ScrapeError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    _store_task(task)
    return _envelope(
        {
            "task_id": task.task_id,
            "status": "completed",
            "columns": task.columns,
            "preview_rows": task.rows[:5],
            "total": task.total,
            "schema": task.schema,
        }
    )


@app.post("/api/crawl")
async def create_crawl(payload: CrawlRequest, request: Request) -> dict:
    """Start a bounded background crawl and return its progress identifier."""
    _check_rate_limit(request.client.host if request.client else "unknown")
    try:
        url = await asyncio.to_thread(ensure_public_url, str(payload.url))
    except ScrapeError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    job = CrawlJob(
        url=url,
        requirement=payload.requirement,
        max_pages=payload.max_pages,
    )
    _crawl_jobs[job.crawl_id] = job
    _crawl_job_tasks[job.crawl_id] = asyncio.create_task(_run_crawl_job(job))
    return _envelope(_crawl_status(job))


@app.get("/api/crawl/{crawl_id}")
async def crawl_status(crawl_id: str) -> dict:
    job = _crawl_jobs.get(crawl_id)
    if job is None:
        raise HTTPException(status_code=404, detail="抓取任务不存在或已过期")
    return _envelope(_crawl_status(job))


@app.post("/api/crawl/{crawl_id}/stop")
async def stop_crawl(crawl_id: str) -> dict:
    job = _crawl_jobs.get(crawl_id)
    if job is None:
        raise HTTPException(status_code=404, detail="抓取任务不存在或已过期")
    if job.status not in {"completed", "stopped", "error"}:
        job.stop_requested = True
        job.status = "stopping"
    return _envelope(_crawl_status(job), msg="已请求停止抓取")


@app.get("/api/preview")
async def preview(task_id: str) -> dict:
    """Return a task's first five rows."""
    task = _get_task(task_id)
    return _envelope(
        {
            "task_id": task.task_id,
            "columns": task.columns,
            "rows": task.rows[:5],
            "total": task.total,
            "schema": task.schema,
        }
    )


@app.get("/api/download")
async def download(task_id: str):
    """Stream a completed task as an Excel workbook."""
    task = _get_task(task_id)
    file_stream = export_xlsx(task)
    filename = f"lioran-{task.task_id[:8]}.xlsx"
    return StreamingResponse(
        file_stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/feedback")
async def feedback(payload: FeedbackRequest, request: Request) -> dict:
    """Re-run schema generation with the selected correct row as feedback."""
    _check_rate_limit(request.client.host if request.client else "unknown")
    task = _get_task(payload.task_id)
    if payload.correct_row_index >= task.total:
        raise HTTPException(status_code=422, detail="所选行不存在，请重新选择")
    try:
        updated = await asyncio.wait_for(
            scrape(task.url, task.requirement, payload.correct_row_index),
            timeout=settings.total_timeout,
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail="抓取耗时较长，首次加载本地模型可能需要几分钟，请稍后重试",
        ) from None
    except ScrapeError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    _store_task(updated)
    return _envelope(
        {
            "task_id": updated.task_id,
            "columns": updated.columns,
            "preview_rows": updated.rows[:5],
            "total": updated.total,
            "schema": updated.schema,
        },
        msg="已根据你点选的正确行重新识别页面",
    )


@app.get("/health")
async def health() -> dict:
    return _envelope({"status": "ok"})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)

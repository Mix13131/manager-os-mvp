from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from . import db, llm_service, services
from .schemas import (
    CaptureRequest,
    CaptureResponse,
    CommitmentRequest,
    CommitmentUpdateRequest,
    DailyResetRequest,
    LLMStatusResponse,
    WeeklyReviewResponse,
)


BASE_DIR = Path(__file__).resolve().parent.parent
app = FastAPI(title="Manager OS MVP", version="0.1.0")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.on_event("startup")
def on_startup() -> None:
    db.init_db()


@app.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    context = {
        "request": request,
        "entries": services.list_recent_entries(),
        "patterns": services.get_patterns(),
        "llm_status": llm_service.status(),
    }
    return templates.TemplateResponse("index.html", context)


@app.post("/api/capture", response_model=CaptureResponse)
def capture(payload: CaptureRequest) -> CaptureResponse:
    saved = services.save_capture(payload.text, payload.source)
    return CaptureResponse(**saved)


@app.get("/api/patterns")
def patterns() -> dict[str, object]:
    return {"items": services.get_patterns()}


@app.post("/api/rituals/daily-reset")
def daily_reset(payload: DailyResetRequest) -> dict[str, object]:
    result = services.run_daily_reset(
        impact_focus=payload.impact_focus,
        operational_risk=payload.operational_risk,
        managerial_action=payload.managerial_action,
    )
    return result.model_dump()


@app.post("/api/weekly-review")
def weekly_review() -> WeeklyReviewResponse:
    return WeeklyReviewResponse(**services.run_weekly_review())


@app.get("/api/llm-status", response_model=LLMStatusResponse)
def llm_status() -> LLMStatusResponse:
    return LLMStatusResponse(**llm_service.status())


@app.get("/api/entries")
def entries() -> dict[str, object]:
    return {"items": services.list_recent_entries(limit=20)}


@app.post("/api/commitments")
def create_commitment(payload: CommitmentRequest) -> dict[str, object]:
    commitment_id = db.insert_and_return_id(
        """
        INSERT INTO commitments (text, due_date, created_at)
        VALUES (?, ?, ?)
        """,
        (payload.text, payload.due_date, services.now_iso()),
    )
    return {"id": commitment_id, "status": "open"}


@app.patch("/api/commitments/{commitment_id}")
def update_commitment(commitment_id: int, payload: CommitmentUpdateRequest) -> dict[str, object]:
    existing = db.fetch_one("SELECT * FROM commitments WHERE id = ?", (commitment_id,))
    if not existing:
        raise HTTPException(status_code=404, detail="Commitment not found")

    broken_count = existing["broken_count"] + 1 if payload.status == "broken" else existing["broken_count"]
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE commitments SET status = ?, broken_count = ? WHERE id = ?",
        (payload.status, broken_count, commitment_id),
    )
    conn.commit()
    conn.close()
    return {"id": commitment_id, "status": payload.status, "broken_count": broken_count}

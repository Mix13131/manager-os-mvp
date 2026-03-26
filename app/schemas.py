from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


EntryType = Literal["task", "problem", "anxiety", "plan", "reflection"]
Contour = Literal["operational", "managerial", "architectural"]
RoleVerdict = Literal["executor", "manager", "mixed"]
Distortion = Literal[
    "rescuer_mode",
    "hypercontrol",
    "delegation_avoidance",
    "false_urgency",
    "boundary_failure",
    "not_detected",
]
RecommendedAction = Literal["do", "delegate", "delay", "delete", "process", "discuss"]


class CaptureRequest(BaseModel):
    text: str = Field(min_length=3, max_length=4000)
    source: str = Field(default="web", max_length=50)


class AnalysisResult(BaseModel):
    entry_type: EntryType
    contour: Contour
    role_verdict: RoleVerdict
    distortion: Distortion
    recommended_action: RecommendedAction
    strict_action: str
    reasoning: str


class CaptureResponse(BaseModel):
    entry_id: int
    analysis: AnalysisResult


class DailyResetRequest(BaseModel):
    impact_focus: str = Field(min_length=3, max_length=1000)
    operational_risk: str = Field(min_length=3, max_length=1000)
    managerial_action: str = Field(min_length=3, max_length=1000)


class DailyResetResponse(BaseModel):
    score: int
    role_risk: str
    distortion: str
    hard_boundary: str
    must_do_today: str


class WeeklyReviewResponse(BaseModel):
    week_start: str
    management_ratio: float
    delegation_score: float
    rescue_events: int
    top_pattern: str
    next_week_rule: str
    summary: str
    entries_reviewed: int


class LLMStatusResponse(BaseModel):
    enabled: bool
    provider: str
    model: str
    mode: str


class CommitmentRequest(BaseModel):
    text: str = Field(min_length=3, max_length=500)
    due_date: Optional[str] = None
    definition_of_done: Optional[str] = None


class CommitmentResponse(BaseModel):
    id: int
    text: str
    due_date: str
    definition_of_done: str
    status: str
    quality_comment: str


class CommitmentUpdateRequest(BaseModel):
    status: Literal["open", "done", "broken"]

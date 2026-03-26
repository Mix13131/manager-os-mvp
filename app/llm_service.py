from __future__ import annotations

import json
from typing import Any

from .config import settings
from .prompts import (
    INTAKE_INSTRUCTIONS,
    INTAKE_USER_TEMPLATE,
    WEEKLY_REVIEW_INSTRUCTIONS,
    WEEKLY_REVIEW_USER_TEMPLATE,
)
from .schemas import AnalysisResult, WeeklyReviewResponse

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None


ANALYSIS_SCHEMA: dict[str, Any] = {
    "name": "manager_os_analysis",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "entry_type": {
                "type": "string",
                "enum": ["task", "problem", "anxiety", "plan", "reflection"],
            },
            "contour": {
                "type": "string",
                "enum": ["operational", "managerial", "architectural"],
            },
            "role_verdict": {
                "type": "string",
                "enum": ["executor", "manager", "mixed"],
            },
            "distortion": {
                "type": "string",
                "enum": [
                    "rescuer_mode",
                    "hypercontrol",
                    "delegation_avoidance",
                    "false_urgency",
                    "boundary_failure",
                    "not_detected",
                ],
            },
            "recommended_action": {
                "type": "string",
                "enum": ["do", "delegate", "delay", "delete", "process", "discuss"],
            },
            "strict_action": {"type": "string"},
            "reasoning": {"type": "string"},
        },
        "required": [
            "entry_type",
            "contour",
            "role_verdict",
            "distortion",
            "recommended_action",
            "strict_action",
            "reasoning",
        ],
        "additionalProperties": False,
    },
}

WEEKLY_SCHEMA: dict[str, Any] = {
    "name": "manager_os_weekly_review",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "management_ratio": {"type": "number"},
            "delegation_score": {"type": "number"},
            "rescue_events": {"type": "integer"},
            "top_pattern": {"type": "string"},
            "next_week_rule": {"type": "string"},
            "summary": {"type": "string"},
        },
        "required": [
            "management_ratio",
            "delegation_score",
            "rescue_events",
            "top_pattern",
            "next_week_rule",
            "summary",
        ],
        "additionalProperties": False,
    },
}


def is_configured() -> bool:
    return settings.llm_enabled and OpenAI is not None


def status() -> dict[str, Any]:
    return {
        "enabled": is_configured(),
        "provider": "openai" if settings.openai_api_key else "fallback",
        "model": settings.openai_model,
        "mode": settings.app_mode,
    }


def _client() -> OpenAI:
    if OpenAI is None:
        raise RuntimeError("openai package is not installed")
    return OpenAI(api_key=settings.openai_api_key)


def _parse_json_output(response: Any) -> dict[str, Any]:
    output_text = getattr(response, "output_text", "") or ""
    return json.loads(output_text)


def analyze_entry(entry_text: str) -> AnalysisResult:
    if not is_configured():
        raise RuntimeError("LLM is not configured")

    client = _client()
    request_kwargs = {
        "model": settings.openai_model,
        "input": INTAKE_USER_TEMPLATE.format(entry_text=entry_text),
        "instructions": INTAKE_INSTRUCTIONS,
        "text": {
            "format": {
                "type": "json_schema",
                "name": ANALYSIS_SCHEMA["name"],
                "strict": True,
                "schema": ANALYSIS_SCHEMA["schema"],
            }
        },
    }
    if settings.openai_model.startswith("gpt-5"):
        request_kwargs["reasoning"] = {"effort": settings.openai_reasoning_effort}
    response = client.responses.create(**request_kwargs)
    payload = _parse_json_output(response)
    return AnalysisResult(**payload)


def weekly_review(entries_blob: str, week_start: str, entries_reviewed: int) -> WeeklyReviewResponse:
    if not is_configured():
        raise RuntimeError("LLM is not configured")

    client = _client()
    request_kwargs = {
        "model": settings.openai_model,
        "input": WEEKLY_REVIEW_USER_TEMPLATE.format(entries_blob=entries_blob),
        "instructions": WEEKLY_REVIEW_INSTRUCTIONS,
        "text": {
            "format": {
                "type": "json_schema",
                "name": WEEKLY_SCHEMA["name"],
                "strict": True,
                "schema": WEEKLY_SCHEMA["schema"],
            }
        },
    }
    if settings.openai_model.startswith("gpt-5"):
        request_kwargs["reasoning"] = {"effort": settings.openai_reasoning_effort}
    response = client.responses.create(**request_kwargs)
    payload = _parse_json_output(response)
    payload["week_start"] = week_start
    payload["entries_reviewed"] = entries_reviewed
    payload["management_ratio"] = round(float(payload["management_ratio"]), 2)
    payload["delegation_score"] = round(float(payload["delegation_score"]), 2)
    payload["rescue_events"] = int(payload["rescue_events"])
    return WeeklyReviewResponse(**payload)

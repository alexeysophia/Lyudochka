import json
import re

from data.models import AIResponse


def parse_ai_response(raw_text: str) -> AIResponse:
    """Parse raw AI response text into a structured AIResponse."""
    text = raw_text.strip()

    # Strip markdown code fences if present
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()

    # Attempt 1: parse the whole text as JSON
    try:
        data = json.loads(text)
        return _build_response(data)
    except json.JSONDecodeError:
        pass

    # Attempt 2: extract the first {...} block
    json_match = re.search(r"\{.*\}", text, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group())
            return _build_response(data)
        except json.JSONDecodeError:
            pass

    # Fallback: treat entire response as task text
    return AIResponse(
        status="ready",
        task_title="Задача",
        task_text=raw_text,
        jira_params={},
    )


def _build_response(data: dict) -> AIResponse:
    status = data.get("status", "")

    if status == "ready":
        return AIResponse(
            status="ready",
            task_title=data.get("task_title", ""),
            task_text=data.get("task_text", ""),
            jira_params=data.get("jira_params", {}),
        )

    if status == "need_clarification":
        return AIResponse(
            status="need_clarification",
            questions=data.get("questions", []),
        )

    # Unknown status — surface as ready with raw dump
    return AIResponse(
        status="ready",
        task_title=data.get("task_title", "Задача"),
        task_text=data.get("task_text", str(data)),
        jira_params=data.get("jira_params", {}),
    )

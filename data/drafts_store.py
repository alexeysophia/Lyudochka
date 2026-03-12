import json
import logging
import os
from pathlib import Path

from core.jira_markup import markdown_to_jira
from data.models import AIResponse, Draft

log = logging.getLogger(__name__)


def _drafts_dir() -> Path:
    base = Path(os.environ["APPDATA"]) / "Lyudochka" / "drafts"
    base.mkdir(parents=True, exist_ok=True)
    return base


def save_draft(draft: Draft) -> None:
    path = _drafts_dir() / f"{draft.id}.json"
    ai_response_data = None
    if draft.ai_response is not None:
        ai_response_data = {
            "status": draft.ai_response.status,
            "task_text": draft.ai_response.task_text,
            "task_title": draft.ai_response.task_title,
            "jira_params": draft.ai_response.jira_params,
            "questions": draft.ai_response.questions,
            "jira_issue_key": draft.ai_response.jira_issue_key,
        }
    data = {
        "id": draft.id,
        "created_at": draft.created_at,
        "team_name": draft.team_name,
        "user_input": draft.user_input,
        "stage": draft.stage,
        "questions": draft.questions,
        "answers": draft.answers,
        "ai_response": ai_response_data,
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_all_drafts() -> list[Draft]:
    result: list[Draft] = []
    for path in _drafts_dir().glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            ai_response: AIResponse | None = None
            if data.get("ai_response"):
                ar = data["ai_response"]
                ai_response = AIResponse(
                    status=ar["status"],
                    task_text=ar.get("task_text", ""),
                    task_title=ar.get("task_title", ""),
                    jira_params=ar.get("jira_params", {}),
                    questions=ar.get("questions", []),
                    jira_issue_key=ar.get("jira_issue_key", ""),
                )
            result.append(
                Draft(
                    id=data["id"],
                    created_at=data["created_at"],
                    team_name=data["team_name"],
                    user_input=data["user_input"],
                    stage=data["stage"],
                    questions=data.get("questions", []),
                    answers=data.get("answers", []),
                    ai_response=ai_response,
                )
            )
        except Exception:
            pass
    result.sort(key=lambda d: d.created_at, reverse=True)
    return result


def migrate_drafts_to_jira_markup() -> None:
    """One-time migration: convert Markdown task_text to Jira wiki markup in all drafts."""
    _MD_PATTERNS = ("**", "## ", "---")
    converted = 0
    for path in _drafts_dir().glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            ar = data.get("ai_response")
            if not ar:
                continue
            text = ar.get("task_text", "")
            if not text or not any(p in text for p in _MD_PATTERNS):
                continue
            ar["task_text"] = markdown_to_jira(text)
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            converted += 1
        except Exception as exc:
            log.warning("migrate_drafts: skipped %s: %s", path.name, exc)
    if converted:
        log.info("migrate_drafts_to_jira_markup: converted %d draft(s)", converted)


def delete_draft(draft_id: str) -> None:
    path = _drafts_dir() / f"{draft_id}.json"
    if path.exists():
        path.unlink()

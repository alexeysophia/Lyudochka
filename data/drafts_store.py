import json
import os
from pathlib import Path

from data.models import AIResponse, Draft


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
    for path in sorted(
        _drafts_dir().glob("*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    ):
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
    return result


def delete_draft(draft_id: str) -> None:
    path = _drafts_dir() / f"{draft_id}.json"
    if path.exists():
        path.unlink()

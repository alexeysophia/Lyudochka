import json
import os
from pathlib import Path

from data.models import Team


def _teams_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        base = Path(appdata)
    else:
        base = Path.home() / "AppData" / "Roaming"
    directory = base / "Lyudochka" / "teams"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _safe_filename(name: str) -> str:
    """Convert a team name to a safe filename."""
    safe = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in name)
    return safe.strip("_") or "team"


def load_all_teams() -> list[Team]:
    teams_dir = _teams_dir()
    teams: list[Team] = []
    for json_file in sorted(teams_dir.glob("*.json")):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            teams.append(
                Team(
                    name=data["name"],
                    jira_project=data["jira_project"],
                    default_task_type=data["default_task_type"],
                    rules=data["rules"],
                    team_lead=data.get("team_lead", ""),
                    context=data.get("context", ""),
                    extra_jira_fields=data.get("extra_jira_fields", {}),
                    default_task_type_id=data.get("default_task_type_id", ""),
                    jira_fields_meta=data.get("jira_fields_meta", []),
                    jira_issue_types_meta=data.get("jira_issue_types_meta", []),
                )
            )
        except (json.JSONDecodeError, KeyError, OSError):
            continue
    return teams


def save_team(team: Team) -> None:
    teams_dir = _teams_dir()
    filename = _safe_filename(team.name) + ".json"
    path = teams_dir / filename
    data = {
        "name": team.name,
        "jira_project": team.jira_project,
        "default_task_type": team.default_task_type,
        "default_task_type_id": team.default_task_type_id,
        "rules": team.rules,
        "team_lead": team.team_lead,
        "context": team.context,
        "extra_jira_fields": team.extra_jira_fields,
        "jira_fields_meta": team.jira_fields_meta,
        "jira_issue_types_meta": team.jira_issue_types_meta,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def is_name_taken(name: str, exclude_name: str = "") -> bool:
    """Return True if another team already uses this name (case-insensitive)."""
    needle = name.strip().lower()
    exclude = exclude_name.strip().lower()
    return any(
        t.name.strip().lower() == needle and t.name.strip().lower() != exclude
        for t in load_all_teams()
    )


def is_lead_taken(team_lead: str, exclude_name: str = "") -> bool:
    """Return True if another team already has this team lead (case-insensitive)."""
    needle = team_lead.strip().lower()
    exclude = exclude_name.strip().lower()
    return any(
        t.team_lead.strip().lower() == needle and t.name.strip().lower() != exclude
        for t in load_all_teams()
    )


def delete_team(team_name: str) -> None:
    teams_dir = _teams_dir()
    filename = _safe_filename(team_name) + ".json"
    path = teams_dir / filename
    if path.exists():
        path.unlink()

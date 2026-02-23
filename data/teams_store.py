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
                    dod_template=data["dod_template"],
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
        "rules": team.rules,
        "dod_template": team.dod_template,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def delete_team(team_name: str) -> None:
    teams_dir = _teams_dir()
    filename = _safe_filename(team_name) + ".json"
    path = teams_dir / filename
    if path.exists():
        path.unlink()

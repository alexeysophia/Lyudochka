import json
import logging
import os
from pathlib import Path

from data.models import Term

log = logging.getLogger(__name__)


def _terms_path() -> Path:
    appdata = os.environ.get("APPDATA")
    base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
    directory = base / "Lyudochka"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / "terms.json"


def load_terms() -> list[Term]:
    path = _terms_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return [Term(name=t["name"], description=t["description"]) for t in data]
    except Exception:
        return []


def save_terms(terms: list[Term]) -> None:
    path = _terms_path()
    data = [{"name": t.name, "description": t.description} for t in terms]
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

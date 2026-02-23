import json
import os
from pathlib import Path

from data.models import Settings


def _app_data_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        base = Path(appdata)
    else:
        base = Path.home() / "AppData" / "Roaming"
    directory = base / "Lyudochka"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _settings_path() -> Path:
    return _app_data_dir() / "settings.json"


def load_settings() -> Settings:
    path = _settings_path()
    if not path.exists():
        return Settings()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return Settings(
            default_llm=data.get("default_llm", "anthropic"),
            anthropic_api_key=data.get("anthropic_api_key", ""),
            gemini_api_key=data.get("gemini_api_key", ""),
        )
    except (json.JSONDecodeError, OSError):
        return Settings()


def save_settings(settings: Settings) -> None:
    path = _settings_path()
    data = {
        "default_llm": settings.default_llm,
        "anthropic_api_key": settings.anthropic_api_key,
        "gemini_api_key": settings.gemini_api_key,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

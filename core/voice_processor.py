"""Voice-to-task processing: sends recorded audio to Gemini and extracts team + description."""
import json
import re
from pathlib import Path

from google import genai
from google.genai import types

from data.models import Team, VoiceResult

_PROMPT_TEMPLATE = """\
Ты помощник, который анализирует аудиозаписи рабочих разговоров на русском языке.

Доступные команды:
{teams_list}

Задача:
1. Определи, о какой команде идёт речь (по названию команды или имени/фамилии руководителя). \
Верни ТОЧНОЕ название команды из списка выше, или null, если не удалось однозначно определить.
2. Сформулируй краткое описание задачи, которую нужно создать, на основе разговора. \
Пиши от третьего лица, как будто описываешь задачу для Jira.

Верни ТОЛЬКО JSON без markdown-блоков и комментариев:
{{"team_name": "<точное название из списка или null>", "description": "<описание задачи>"}}"""


async def process_voice(
    audio_path: Path,
    teams: list[Team],
    gemini_api_key: str,
) -> VoiceResult:
    """Send recorded audio to Gemini and extract team name + task description."""
    teams_list = "\n".join(
        f"- Название: {t.name}, Руководитель: {t.team_lead}" for t in teams
    )
    prompt = _PROMPT_TEMPLATE.format(teams_list=teams_list)

    audio_bytes = audio_path.read_bytes()

    client = genai.Client(api_key=gemini_api_key)
    response = await client.aio.models.generate_content(
        model="gemini-2.0-flash",
        contents=[
            types.Part.from_bytes(data=audio_bytes, mime_type="audio/wav"),
            prompt,
        ],
    )
    raw = response.text.strip()

    return _parse_response(raw, teams)


def _parse_response(raw: str, teams: list[Team]) -> VoiceResult:
    """Parse Gemini JSON response and validate team name against known teams."""
    # Strip markdown code fences if Gemini added them anyway
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        # Fallback: return raw text as description, team unknown
        return VoiceResult(description=raw, team_name=None)

    description: str = str(data.get("description", "")).strip()
    team_name_raw: str | None = data.get("team_name")

    if not team_name_raw or team_name_raw.lower() == "null":
        return VoiceResult(description=description, team_name=None)

    # Match against known teams (exact name or team lead mention)
    needle = team_name_raw.strip().lower()
    matched: str | None = None
    for t in teams:
        if t.name.lower() == needle or t.team_lead.lower() == needle:
            matched = t.name
            break

    return VoiceResult(description=description, team_name=matched)

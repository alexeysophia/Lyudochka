from data.models import AIResponse, Settings, Team
from core.anthropic_client import call_anthropic
from core.gemini_client import call_gemini
from core.prompt_builder import build_system_prompt, build_user_message
from core.response_parser import parse_ai_response


async def generate(
    team: Team,
    user_input: str,
    answers: list[tuple[str, str]] | None,
    settings: Settings,
) -> AIResponse:
    """Route AI call to Anthropic or Gemini and return a parsed AIResponse."""
    system_prompt = build_system_prompt(team)
    user_message = build_user_message(user_input, answers)

    if settings.default_llm == "gemini":
        if not settings.gemini_api_key:
            raise ValueError(
                "Google Gemini API key не настроен.\nПерейдите в раздел «Настройки» и введите ключ."
            )
        raw_text = await call_gemini(system_prompt, user_message, settings.gemini_api_key)
    else:
        if not settings.anthropic_api_key:
            raise ValueError(
                "Anthropic API key не настроен.\nПерейдите в раздел «Настройки» и введите ключ."
            )
        raw_text = await call_anthropic(system_prompt, user_message, settings.anthropic_api_key)

    return parse_ai_response(raw_text)

from google import genai
from google.genai import types


async def call_gemini(
    system_prompt: str,
    user_message: str,
    api_key: str,
    model: str = "gemini-2.5-flash",
) -> str:
    """Call Google Gemini API asynchronously and return the raw response text."""
    client = genai.Client(api_key=api_key)
    try:
        response = await client.aio.models.generate_content(
            model=model,
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
            ),
        )
        return response.text
    except Exception as e:
        msg = str(e)
        low = msg.lower()
        tname = type(e).__name__
        if "403" in msg or "permission" in low or "forbidden" in low or "api_key" in low:
            raise ValueError("Gemini API: нет доступа (403) — проверьте API-ключ")
        elif "401" in msg or "unauthenticated" in low:
            raise ValueError("Gemini API: неверный ключ (401)")
        elif "500" in msg or "internal" in low:
            raise ValueError("Gemini API: внутренняя ошибка сервера (500)")
        elif "503" in msg or "unavailable" in low:
            raise ValueError("Gemini API: сервис временно недоступен (503)")
        elif "timeout" in low or "Timeout" in tname or "DeadlineExceeded" in tname:
            raise ValueError("Gemini API: превышено время ожидания")
        elif "connect" in low or "Connection" in tname or "Network" in tname:
            raise ValueError("Не удалось подключиться к Gemini API")
        elif "quota" in low or "429" in msg or "resource_exhausted" in low:
            raise ValueError("Gemini API: превышен лимит запросов (429)")
        raise ValueError(f"Gemini API: {e}")

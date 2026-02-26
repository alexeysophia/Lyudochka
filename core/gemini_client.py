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
    response = await client.aio.models.generate_content(
        model=model,
        contents=user_message,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
        ),
    )
    return response.text

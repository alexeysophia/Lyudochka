import asyncio

import google.generativeai as genai


async def call_gemini(
    system_prompt: str,
    user_message: str,
    api_key: str,
    model: str = "gemini-1.5-flash",
) -> str:
    """Call Google Gemini API asynchronously and return the raw response text."""

    def _sync_call() -> str:
        genai.configure(api_key=api_key)
        model_instance = genai.GenerativeModel(
            model_name=model,
            system_instruction=system_prompt,
        )
        response = model_instance.generate_content(user_message)
        return response.text

    return await asyncio.to_thread(_sync_call)

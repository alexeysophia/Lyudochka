import anthropic


async def call_anthropic(
    system_prompt: str,
    user_message: str,
    api_key: str,
    model: str = "claude-sonnet-4-6",
) -> str:
    """Call Anthropic API asynchronously and return the raw response text."""
    client = anthropic.AsyncAnthropic(api_key=api_key)
    message = await client.messages.create(
        model=model,
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    return message.content[0].text

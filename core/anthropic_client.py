import anthropic


async def call_anthropic(
    system_prompt: str,
    user_message: str,
    api_key: str,
    model: str = "claude-sonnet-4-6",
) -> str:
    """Call Anthropic API asynchronously and return the raw response text."""
    client = anthropic.AsyncAnthropic(api_key=api_key)
    try:
        message = await client.messages.create(
            model=model,
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        return message.content[0].text
    except anthropic.APITimeoutError:
        raise ValueError("Anthropic API: превышено время ожидания")
    except anthropic.APIConnectionError:
        raise ValueError("Не удалось подключиться к Anthropic API")
    except anthropic.AuthenticationError:
        raise ValueError("Anthropic API: неверный ключ (ошибка авторизации)")
    except anthropic.PermissionDeniedError:
        raise ValueError("Anthropic API: нет доступа (403)")
    except anthropic.RateLimitError:
        raise ValueError("Anthropic API: превышен лимит запросов")
    except anthropic.InternalServerError:
        raise ValueError("Anthropic API: внутренняя ошибка сервера (500)")
    except anthropic.APIStatusError as e:
        raise ValueError(f"Anthropic API ошибка {e.status_code}: {e.message}")

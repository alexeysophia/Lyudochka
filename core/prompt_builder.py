from data.models import Team

_SYSTEM_PROMPT_TEMPLATE = """\
Ты — эксперт по составлению задач в Jira. Твоя задача — помочь оформить задачу для команды "{team_name}" строго по их правилам.

## Правила команды:
{rules}

## Руководитель команды:
{team_lead}

## Проект Jira: {jira_project}
## Тип задачи по умолчанию: {default_task_type}

## Инструкции:
1. Проанализируй запрос пользователя.
2. Если информации достаточно — сформулируй задачу по правилам команды.
3. Если информации недостаточно — задай уточняющие вопросы (не более 3-х).
4. ВСЕГДА отвечай ТОЛЬКО валидным JSON без какого-либо текста вне JSON.

Если информации достаточно:
{{
  "status": "ready",
  "task_title": "Краткое название задачи",
  "task_text": "Полное описание задачи в формате Markdown",
  "jira_params": {{
    "project": "{jira_project}",
    "type": "Story/Bug/Task",
    "priority": "High/Medium/Low",
    "labels": []
  }}
}}

Если нужна дополнительная информация:
{{
  "status": "need_clarification",
  "questions": ["Вопрос 1?", "Вопрос 2?"]
}}

Отвечай на русском языке. Не добавляй никакого текста вне JSON-объекта.\
"""


def build_system_prompt(team: Team) -> str:
    """Assemble the system prompt from team rules."""
    return _SYSTEM_PROMPT_TEMPLATE.format(
        team_name=team.name,
        rules=team.rules or "(правила не заданы)",
        team_lead=team.team_lead or "(не указан)",
        jira_project=team.jira_project,
        default_task_type=team.default_task_type,
    )


def build_user_message(
    user_input: str,
    answers: list[tuple[str, str]] | None = None,
) -> str:
    """Build the user message, optionally appending Q&A from clarification round."""
    message = f"Запрос на создание задачи:\n{user_input}"

    if answers:
        message += "\n\n## Ответы на уточняющие вопросы:\n"
        for question, answer in answers:
            message += f"\nВопрос: {question}\nОтвет: {answer}\n"

    return message

from data.models import Team

_SYSTEM_PROMPT_TEMPLATE = """\
Ты — эксперт по составлению задач в Jira. Твоя задача — помочь оформить задачу для команды "{team_name}" строго по их правилам.

## Контекст команды:
{context}

## Правила команды:
{rules}

## Руководитель команды:
{team_lead}

## Проект Jira: {jira_project}
## Тип задачи по умолчанию: {default_task_type}

## Инструкции:
1. Проанализируй запрос пользователя.
2. Если информации достаточно — сформулируй задачу по правилам команды.
3. Если информации недостаточно — задай только те уточняющие вопросы, ответы на которые действительно необходимы для составления задачи по правилам команды. Задавай ровно столько вопросов, сколько нужно — не больше 7. Если данных достаточно — сразу возвращай готовую задачу.
4. ВСЕГДА отвечай ТОЛЬКО валидным JSON без какого-либо текста вне JSON.

Если информации достаточно:
{{
  "status": "ready",
  "task_title": "Краткое название задачи",
  "task_text": "Полное описание задачи в формате Jira wiki markup",
  "jira_params": {{
    "project": "{jira_project}",
    "type": "Story/Bug/Task",
    "labels": []
  }}
}}

Если нужна дополнительная информация:
{{
  "status": "need_clarification",
  "questions": ["Вопрос 1?", "Вопрос 2?"]
}}

Форматирование task_text — только Jira wiki markup:
- Жирный: *текст* (одна звёздочка)
- Курсив: _текст_
- Заголовок: h2. Текст
- Список: * пункт
- Код: {{код}}
- НЕ использовать: **двойные звёздочки**, ## решётки, --- горизонтальные линии, Markdown-разметку.

Отвечай на русском языке. Не добавляй никакого текста вне JSON-объекта.\
"""


def build_system_prompt(team: Team) -> str:
    """Assemble the system prompt from team rules."""
    return _SYSTEM_PROMPT_TEMPLATE.format(
        team_name=team.name,
        context=team.context or "(не указан)",
        rules=team.rules or "(правила не заданы)",
        team_lead=team.team_lead or "(не указан)",
        jira_project=team.jira_project,
        default_task_type=team.default_task_type,
    )


def build_user_message(
    user_input: str,
    answers: list[tuple[str, str]] | None = None,
    force_complete: bool = False,
) -> str:
    """Build the user message, optionally appending Q&A from clarification round."""
    message = f"Запрос на создание задачи:\n{user_input}"

    if answers:
        message += "\n\n## Ответы на уточняющие вопросы:\n"
        for question, answer in answers:
            message += f"\nВопрос: {question}\nОтвет: {answer}\n"

    if force_complete:
        message += (
            "\n\n## ВАЖНО: Пользователь пропустил уточнение.\n"
            "Сформируй задачу НЕМЕДЛЕННО — не задавай вопросов.\n"
            "Для всех недостающих данных используй значение «Нет данных»."
        )

    return message

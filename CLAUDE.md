# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**Lyudochka** — десктопное приложение для Windows 11, автоматизирующее создание задач в On-Prem Jira для разных команд.

Пользователь вводит суть задачи и выбирает команду. Приложение применяет правила конкретной команды (шаблоны, DoD), отправляет запрос в LLM для переформатирования текста. Если ИИ не хватает данных — возвращает уточняющие вопросы в UI. Результат: готовый текст задачи, название проекта и параметры для Jira.

GitHub: https://github.com/alexeysophia/Lyudochka

## Tech Stack

- **Python 3.11+**
- **UI**: Flet ≥0.80 (desktop mode)
- **LLM**: Anthropic (`anthropic` library) и Google Gemini (`google-genai`)
- **ЗАПРЕЩЕНО**: использовать OpenAI и библиотеку `openai`
- **HTTP**: `httpx` для Jira REST API

## Running

```bash
python main.py
```

## Project Structure

```
main.py                      # Entry point: ft.run(main), window setup, icon build
ui/app.py                    # AppShell: NavigationRail + 4 screens
ui/screens/main_screen.py    # Task creation flow (voice + text input, generation, questions)
ui/screens/drafts_screen.py  # Saved drafts list (restore/delete, team filter)
ui/screens/teams_screen.py   # Team list (add/edit/delete)
ui/screens/team_editor.py    # AlertDialog form for create/edit team
ui/screens/settings_screen.py # API keys, LLM selector, Jira config
ui/components/result_card.py  # Ready task display + Jira creation button
ui/components/questions_form.py # Clarifying questions + answer fields
ui/snack.py                  # error_snack(page, message) helper; clipboard via subprocess clip
core/ai_router.py            # generate() → routes to Anthropic or Gemini
core/anthropic_client.py     # async call_anthropic()
core/gemini_client.py        # async call_gemini() (uses asyncio.to_thread)
core/prompt_builder.py       # build_system_prompt(team), build_user_message(input, answers)
core/response_parser.py      # parse_ai_response(raw_text) → AIResponse
core/jira_client.py          # async create_jira_issue(), get_project_meta(), get_insight_objects()
core/audio_recorder.py       # AudioRecorder: start/stop/cancel → WAV via sounddevice
core/voice_processor.py      # async process_voice() → VoiceResult via Gemini
core/logger.py               # setup_logging() — call once at startup; logs to %APPDATA%\Lyudochka\lyudochka.log
data/models.py               # Team, Settings, AIResponse, VoiceResult, Draft dataclasses
data/settings_store.py       # load/save %APPDATA%\Lyudochka\settings.json
data/teams_store.py          # load/save/delete %APPDATA%\Lyudochka\teams\{name}.json
data/drafts_store.py         # save/load/delete %APPDATA%\Lyudochka\drafts\{id}.json
```

## Data Storage

Все пользовательские данные хранятся **исключительно** в `%APPDATA%\Lyudochka`. Никаких данных в папке установки.

## Code Rules

- **Type hints обязательны** для всех функций и методов.
- **Все вызовы к API нейросетей — асинхронные** (`async def`).
- **AI-модуль возвращает структурированный JSON**:
  - Ready: `{"status":"ready","task_title":"...","task_text":"...","jira_params":{...}}`
  - Needs info: `{"status":"need_clarification","questions":["..."]}`

## Flet 0.80 API (critical — differs from older docs)

- `ft.run(fn)` — not `ft.app(target=fn)`
- `Dropdown(on_select=)` — not `on_change`
- SnackBar: `snack = ft.SnackBar(..., open=True); page.overlay.append(snack); page.update()` — use `ui/snack.py:error_snack()` for errors
- Dialogs: `page.show_dialog(dlg)` / `page.pop_dialog()` — not `dlg.open = True`
- Clipboard: `ft.Clipboard` service via `page.overlay` — or use `subprocess clip` (see `ui/snack.py`)
- Buttons (OutlinedButton, ElevatedButton, TextButton): no `text=` kwarg — text is first positional arg; update via `btn.content = "новый текст"`
- `ft.Colors.SURFACE_CONTAINER` — not `SURFACE_VARIANT` (doesn't exist)
- `control.focus()` is async — use `page.run_task(control.focus)` from sync callbacks
- Async event handlers: `async def` handlers work; use `page.run_task(coro, *args)` from sync callbacks
- Navigation: `e.data` is a string in `NavigationRail.on_change` — cast with `int(e.data)`
- Drag events: position via `e.global_position.y` (not `e.global_y`)

## Key Patterns

**Team uniqueness** (in `data/teams_store.py`):
- `is_name_taken(name, exclude_name="")` / `is_lead_taken(lead, exclude_name="")` — used in `team_editor.py`

**Team model** (full `data/models.py`):
```python
Team(name, jira_project, default_task_type, rules, team_lead,
     context="",                  # products/responsibilities shown to AI
     extra_jira_fields={},        # saved custom field values e.g. {"customfield_123": "value"}
     default_task_type_id="",     # numeric issue type ID; used instead of name when set
     jira_fields_meta=[],         # [{id, name, multi, allowed_values, insight}] from createmeta
     jira_issue_types_meta=[])    # [{id, name}] from createmeta
```

**`jira_params` dict** (from AI JSON + used in `result_card.py`):
```python
{"project": "KEY", "type": "Story", "type_id": "10003",
 "labels": ["tag1"], "extra_fields": {"customfield_123": "value"}}
```

**Voice input** always uses Gemini (Anthropic doesn't support audio). Shows error if no `gemini_api_key`.

**Draft model stages**: `"input"` | `"clarification"` | `"ready"`

**Skip clarification**: `build_user_message(..., force_complete=True)` adds an instruction forcing the AI to return a ready task immediately without asking questions; triggered by the skip checkbox in `main_screen.py`.

**Jira issue type**: prefer `issue_type_id` (numeric) over `issue_type` (name) to avoid locale rejection by Jira Server.

**Epic**: `customfield_15501` is set to `summary` automatically for Epic type.

**Jira field normalization** (`jira_client._normalize_field`): converts JQL-style names to REST API names (e.g. `fixversion` → `fixVersions`), `cf[12345]` shorthand → `customfield_12345`, wraps string values in `{"name": "..."}` or `[{"name": "..."}]` based on field type; already-JSON values are passed as-is.

**Insight/Assets fields**: `get_insight_objects(jira_url, token, field_name, field_id="")` fetches objects for a field. When `field_id` is provided, first calls `GET /rest/insight/1.0/config/field/{field_id}` to get `objectTypeIds` and queries by `objectTypeId = {id}` (avoids cross-schema collisions). Falls back to `objectType = "<derived_name>"` IQL where name is derived from field display name (strips parenthetical suffix). Returns `[{"id": objectKey, "name": label}]`.

**TeamEditor Jira meta**: calls `get_project_meta(jira_url, token, project_key)` on demand to populate issue type dropdown and extra-fields UI (dropdowns, multi-select chips, Insight pickers). Meta is saved back to `Team.jira_fields_meta` / `Team.jira_issue_types_meta`.

**ResultCard edit mode**: clicking the edit icon (pencil) switches task description from `ft.Markdown` display to a `ft.TextField` with a Markdown formatting toolbar (bold/italic/code/underline/strikethrough/list buttons). Saves with check icon; `_task_text` holds the mutable value used for Jira creation.

**Logging**: call `setup_logging()` from `core.logger` once in `main.py` before `ft.run()`. Use `logging.getLogger(__name__)` in every module. Log is cleared on each startup. Root logger = WARNING; `core`/`ui`/`data`/`__main__` loggers = DEBUG.

## Build & Distribution

1. Сборка в EXE: `PyInstaller --noconsole`
2. Упаковка в инсталлятор: Inno Setup (`.iss`-скрипт)

Инсталлятор должен поддерживать установку с нуля и обновление поверх старой версии без затрагивания `%APPDATA%\Lyudochka`.

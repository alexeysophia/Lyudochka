# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**Lyudochka** — десктопное приложение для Windows 11, автоматизирующее создание задач в On-Prem Jira для разных команд.

Пользователь вводит суть задачи и выбирает команду. Приложение применяет правила конкретной команды (шаблоны, DoD), отправляет запрос в LLM для переформатирования текста. Если ИИ не хватает данных — возвращает уточняющие вопросы в UI. Результат: готовый текст задачи, название проекта и параметры для Jira.

GitHub: https://github.com/alexeysophia/Lyudochka

## Tech Stack

- **Python 3.11+**
- **UI**: Flet (desktop mode)
- **LLM**: Anthropic (`anthropic` library) и Google Gemini (официальное API)
- **ЗАПРЕЩЕНО**: использовать OpenAI и библиотеку `openai`

## Project Structure

```
main.py        # точка входа, инициализация Flet-приложения
ui/            # компоненты интерфейса (экраны, формы, диалоги)
core/          # бизнес-логика: AI-маршрутизация, промпт-инжиниринг, форматирование под Jira
data/          # слой персистентности: чтение/запись JSON-конфигов из AppData
```

## Data Storage

Все пользовательские данные (API-ключи, URL Jira, JSON-правила команд) хранятся **исключительно** в `%APPDATA%\Lyudochka`. Никаких данных в папке установки (Program Files).

## Code Rules

- **Type hints обязательны** для всех функций и методов.
- **Все вызовы к API нейросетей — асинхронные** (`async def`), чтобы UI не зависал.
- **AI-модуль возвращает структурированный JSON**: UI по нему различает готовый текст задачи и встречные уточняющие вопросы.

## Build & Distribution

1. Сборка в EXE: `PyInstaller --noconsole`
2. Упаковка в инсталлятор: Inno Setup (`.iss`-скрипт)

Инсталлятор должен поддерживать установку с нуля и обновление поверх старой версии без затрагивания `%APPDATA%\Lyudochka`.

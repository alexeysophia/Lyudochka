import flet as ft

from data.models import Settings
from data.settings_store import load_settings, save_settings


class SettingsScreen:
    def __init__(self, page: ft.Page) -> None:
        self.page = page

    def build(self) -> ft.Control:
        settings = load_settings()

        llm_dropdown = ft.Dropdown(
            label="LLM по умолчанию",
            value=settings.default_llm,
            options=[
                ft.dropdown.Option("anthropic", "Anthropic (Claude)"),
                ft.dropdown.Option("gemini", "Google Gemini"),
            ],
            width=320,
        )

        anthropic_key = ft.TextField(
            label="Anthropic API Key",
            value=settings.anthropic_api_key,
            password=True,
            can_reveal_password=True,
            width=520,
        )

        gemini_key = ft.TextField(
            label="Google Gemini API Key",
            value=settings.gemini_api_key,
            password=True,
            can_reveal_password=True,
            width=520,
        )

        status_text = ft.Text("", color=ft.Colors.GREEN)

        def save_clicked(e: ft.ControlEvent) -> None:
            new_settings = Settings(
                default_llm=llm_dropdown.value or "anthropic",
                anthropic_api_key=anthropic_key.value or "",
                gemini_api_key=gemini_key.value or "",
            )
            save_settings(new_settings)
            status_text.value = "✓ Настройки сохранены"
            status_text.color = ft.Colors.GREEN
            self.page.update()

        save_btn = ft.ElevatedButton(
            "Сохранить",
            icon=ft.Icons.SAVE,
            on_click=save_clicked,
        )

        return ft.Container(
            padding=30,
            content=ft.Column(
                controls=[
                    ft.Text("Настройки", size=24, weight=ft.FontWeight.BOLD),
                    ft.Divider(),
                    ft.Text("LLM-провайдер", size=15, weight=ft.FontWeight.W_500),
                    llm_dropdown,
                    ft.Container(height=8),
                    ft.Text("API-ключи", size=15, weight=ft.FontWeight.W_500),
                    anthropic_key,
                    gemini_key,
                    ft.Container(height=8),
                    save_btn,
                    status_text,
                ],
                spacing=12,
            ),
        )

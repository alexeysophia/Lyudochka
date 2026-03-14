import asyncio
import logging
import os

import flet as ft

from core.logger import setup_logging

log = logging.getLogger(__name__)

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_ICON_PATH = os.path.join(_BASE_DIR, "icons", "app.ico")
_ICON128_PATH = os.path.join(_BASE_DIR, "icons", "icon128.png")


def before_main(page: ft.Page) -> None:
    """Called before the window is shown — configure size/position here."""
    page.window.width = 400
    page.window.height = 220
    page.window.resizable = False
    page.window.maximizable = False
    page.window.minimizable = False
    page.window.title_bar_hidden = True
    page.window.icon = _ICON_PATH


async def main(page: ft.Page) -> None:
    page.title = "Людочка"
    page.theme_mode = ft.ThemeMode.SYSTEM

    page.controls.append(
        ft.Container(
            expand=True,
            alignment=ft.Alignment(0, 0),
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Image(src=_ICON128_PATH, width=56, height=56),
                            ft.Column(
                                controls=[
                                    ft.Text(
                                        "Людочка",
                                        size=26,
                                        weight=ft.FontWeight.BOLD,
                                    ),
                                    ft.Text(
                                        "Помощник заведения задач",
                                        size=12,
                                        color=ft.Colors.GREY_600,
                                    ),
                                ],
                                spacing=2,
                                alignment=ft.MainAxisAlignment.CENTER,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=16,
                    ),
                    ft.ProgressBar(width=260),
                    ft.Text("Загрузка...", size=12, color=ft.Colors.GREY_500),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=14,
            ),
        )
    )

    # Center the hidden window before making it visible — no flash
    await page.window.center()
    page.window.visible = True
    page.update()

    page.run_task(_init_app, page)


async def _init_app(page: ft.Page) -> None:
    from data.drafts_store import cleanup_old_drafts, migrate_drafts_to_jira_markup
    from data.settings_store import load_settings
    from data.teams_store import migrate_teams_to_jira_markup
    from ui.app import AppShell

    await asyncio.to_thread(migrate_drafts_to_jira_markup)
    await asyncio.to_thread(migrate_teams_to_jira_markup)
    settings = await asyncio.to_thread(load_settings)
    await asyncio.to_thread(cleanup_old_drafts, settings.draft_retention_days)

    shell = AppShell(page)

    page.controls.clear()
    page.controls.append(shell.build())
    page.window.alignment = None
    page.window.left = 0
    page.window.top = 0
    page.window.title_bar_hidden = False
    page.window.minimizable = True
    page.window.maximizable = True
    page.window.resizable = True
    page.window.min_width = 800
    page.window.min_height = 580
    page.window.width = 1000
    page.window.height = 700
    page.update()


if __name__ == "__main__":
    setup_logging()
    ft.run(main, before_main=before_main, view=ft.AppView.FLET_APP_HIDDEN)

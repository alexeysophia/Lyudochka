import logging
import os

import flet as ft

from core.logger import setup_logging
from data.drafts_store import cleanup_old_drafts, migrate_drafts_to_jira_markup
from data.settings_store import load_settings
from data.teams_store import migrate_teams_to_jira_markup
from ui.app import AppShell

log = logging.getLogger(__name__)

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def main(page: ft.Page) -> None:
    page.title = "Людочка — твой помощник заведения задач"
    page.theme_mode = ft.ThemeMode.SYSTEM
    page.window.width = 1000
    page.window.height = 700
    page.window.min_width = 800
    page.window.min_height = 580
    page.window.icon = os.path.join(_BASE_DIR, "icons", "app.ico")

    shell = AppShell(page)
    page.add(shell.build())


if __name__ == "__main__":
    setup_logging()
    migrate_drafts_to_jira_markup()
    migrate_teams_to_jira_markup()
    cleanup_old_drafts(load_settings().draft_retention_days)
    ft.run(main)

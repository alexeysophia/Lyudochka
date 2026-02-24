import flet as ft

from data.models import Draft
from ui.screens.drafts_screen import DraftsScreen
from ui.screens.main_screen import MainScreen
from ui.screens.settings_screen import SettingsScreen
from ui.screens.teams_screen import TeamsScreen


class AppShell:
    """Top-level shell: NavigationRail + screen content area."""

    def __init__(self, page: ft.Page) -> None:
        self.page = page

        self._main_screen = MainScreen(page)
        self._drafts_screen = DraftsScreen(page, on_restore=self._on_restore_draft)
        self._teams_screen = TeamsScreen(page, on_change=self._on_teams_changed)
        self._settings_screen = SettingsScreen(page)

        self._screens: list = [
            self._main_screen,      # 0 — Создать задачу
            self._drafts_screen,    # 1 — Черновики
            self._teams_screen,     # 2 — Команды
            self._settings_screen,  # 3 — Настройки
        ]

        self._nav_rail = ft.NavigationRail(
            selected_index=0,
            label_type=ft.NavigationRailLabelType.ALL,
            min_width=80,
            min_extended_width=180,
            destinations=[
                ft.NavigationRailDestination(
                    icon=ft.Icons.TASK_ALT_OUTLINED,
                    selected_icon=ft.Icons.TASK_ALT,
                    label="Создать задачу",
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.BOOKMARK_BORDER,
                    selected_icon=ft.Icons.BOOKMARK,
                    label="Черновики",
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.GROUPS_OUTLINED,
                    selected_icon=ft.Icons.GROUPS,
                    label="Команды",
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.SETTINGS_OUTLINED,
                    selected_icon=ft.Icons.SETTINGS,
                    label="Настройки",
                ),
            ],
            on_change=self._on_nav_change,
        )

        self._content_area = ft.Container(
            content=self._main_screen.build(),
            expand=True,
        )

    def build(self) -> ft.Control:
        return ft.Row(
            controls=[
                self._nav_rail,
                ft.VerticalDivider(width=1),
                self._content_area,
            ],
            expand=True,
        )

    def _on_nav_change(self, e: ft.ControlEvent) -> None:
        idx = int(e.data)
        self._content_area.content = self._screens[idx].build()
        self.page.update()

    def _on_teams_changed(self) -> None:
        """Called when teams are added, edited, or deleted."""
        self._main_screen.refresh_teams()

    def _on_restore_draft(self, draft: Draft) -> None:
        """Navigate to main screen and restore draft state."""
        self._nav_rail.selected_index = 0
        self._content_area.content = self._main_screen.build()
        self._main_screen.restore_draft(draft)
        self.page.update()

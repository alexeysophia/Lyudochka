import flet as ft

from data.models import Draft
from ui.screens.bulk_edit_screen import BulkEditScreen
from ui.screens.docs_screen import DocsScreen
from ui.screens.drafts_screen import DraftsScreen
from ui.screens.links_screen import LinksScreen
from ui.screens.main_screen import MainScreen
from ui.screens.settings_screen import SettingsScreen
from ui.screens.teams_screen import TeamsScreen
from ui.screens.terms_screen import TermsScreen


class AppShell:
    """Top-level shell: NavigationRail + screen content area."""

    def __init__(self, page: ft.Page) -> None:
        self.page = page

        self._main_screen = MainScreen(page)
        self._drafts_screen = DraftsScreen(page, on_restore=self._on_restore_draft)
        self._teams_screen = TeamsScreen(page, on_change=self._on_teams_changed)
        self._terms_screen = TermsScreen(page)
        self._links_screen = LinksScreen(page)
        self._bulk_edit_screen = BulkEditScreen(page)
        self._settings_screen = SettingsScreen(page)
        self._docs_screen = DocsScreen(page)

        self._screens: list = [
            self._main_screen,        # 0 — Создать задачу
            self._drafts_screen,      # 1 — Сохраненные
            self._teams_screen,       # 2 — Команды
            self._terms_screen,       # 3 — Термины
            self._links_screen,       # 4 — Связи
            self._bulk_edit_screen,   # 5 — Массовое изменение
            self._settings_screen,    # 6 — Настройки
            self._docs_screen,        # 7 — Документация
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
                    label="Сохраненные",
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.GROUPS_OUTLINED,
                    selected_icon=ft.Icons.GROUPS,
                    label="Команды",
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.MENU_BOOK_OUTLINED,
                    selected_icon=ft.Icons.MENU_BOOK,
                    label="Термины",
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.LINK_OUTLINED,
                    selected_icon=ft.Icons.LINK,
                    label="Связи",
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.EDIT_NOTE_OUTLINED,
                    selected_icon=ft.Icons.EDIT_NOTE,
                    label="Изменение",
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.SETTINGS_OUTLINED,
                    selected_icon=ft.Icons.SETTINGS,
                    label="Настройки",
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.HELP_OUTLINE,
                    selected_icon=ft.Icons.HELP,
                    label="Документация",
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
            vertical_alignment=ft.CrossAxisAlignment.START,
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

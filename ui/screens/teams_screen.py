from typing import Callable

import flet as ft

from data.models import Team
from data.teams_store import delete_team, load_all_teams
from ui.screens.team_editor import TeamEditor


class TeamsScreen:
    def __init__(self, page: ft.Page, on_change: Callable[[], None] | None = None) -> None:
        self.page = page
        self.on_change = on_change
        self._container: ft.Container | None = None

    def build(self) -> ft.Control:
        self._container = ft.Container(
            padding=30,
            content=self._build_content(),
            expand=True,
        )
        return self._container

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_content(self) -> ft.Control:
        teams = load_all_teams()

        def add_team_clicked(e: ft.ControlEvent) -> None:
            self._open_editor(None)

        header = ft.Row(
            controls=[
                ft.Text("Команды", size=24, weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                ft.ElevatedButton(
                    "Добавить команду",
                    icon=ft.Icons.ADD,
                    on_click=add_team_clicked,
                ),
            ],
        )

        if not teams:
            body: ft.Control = ft.Container(
                padding=ft.padding.symmetric(vertical=40),
                content=ft.Column(
                    controls=[
                        ft.Icon(ft.Icons.GROUPS_OUTLINED, size=48, color=ft.Colors.GREY_400),
                        ft.Text(
                            "Нет команд. Добавьте первую команду.",
                            color=ft.Colors.GREY_600,
                            italic=True,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=8,
                ),
            )
        else:
            body = ft.Column(
                controls=[self._build_team_card(t) for t in teams],
                spacing=8,
            )

        return ft.Column(
            controls=[header, ft.Divider(), body],
            spacing=12,
            expand=True,
        )

    def _build_team_card(self, team: Team) -> ft.Control:
        def edit_clicked(e: ft.ControlEvent, t: Team = team) -> None:
            self._open_editor(t)

        def delete_clicked(e: ft.ControlEvent, t: Team = team) -> None:
            dlg_ref: list[ft.AlertDialog] = []

            def confirm(ev: ft.ControlEvent) -> None:
                delete_team(t.name)
                dlg_ref[0].open = False
                self.page.update()
                if self.on_change:
                    self.on_change()
                self._refresh()

            def cancel(ev: ft.ControlEvent) -> None:
                dlg_ref[0].open = False
                self.page.update()

            dlg = ft.AlertDialog(
                modal=True,
                title=ft.Text("Удалить команду?"),
                content=ft.Text(f'Вы уверены, что хотите удалить команду «{t.name}»?'),
                actions=[
                    ft.TextButton("Отмена", on_click=cancel),
                    ft.TextButton("Удалить", on_click=confirm),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            dlg_ref.append(dlg)
            self.page.overlay.append(dlg)
            dlg.open = True
            self.page.update()

        return ft.Card(
            content=ft.Container(
                padding=16,
                content=ft.Row(
                    controls=[
                        ft.Column(
                            controls=[
                                ft.Text(team.name, size=15, weight=ft.FontWeight.W_500),
                                ft.Text(
                                    f"Проект: {team.jira_project}  ·  Тип: {team.default_task_type}",
                                    size=12,
                                    color=ft.Colors.GREY_600,
                                ),
                            ],
                            expand=True,
                            spacing=4,
                        ),
                        ft.IconButton(
                            ft.Icons.EDIT_OUTLINED,
                            tooltip="Редактировать",
                            on_click=edit_clicked,
                        ),
                        ft.IconButton(
                            ft.Icons.DELETE_OUTLINED,
                            tooltip="Удалить",
                            on_click=delete_clicked,
                        ),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ),
        )

    def _open_editor(self, team: Team | None) -> None:
        TeamEditor(page=self.page, team=team, on_save=self._on_team_saved).show()

    def _on_team_saved(self) -> None:
        if self.on_change:
            self.on_change()
        self._refresh()

    def _refresh(self) -> None:
        if self._container is not None:
            self._container.content = self._build_content()
            self.page.update()

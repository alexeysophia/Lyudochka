from typing import Callable

import flet as ft

from data.models import Team
from data.teams_store import delete_team, save_team


class TeamEditor:
    """Dialog form for creating or editing a team."""

    def __init__(
        self,
        page: ft.Page,
        team: Team | None,
        on_save: Callable[[], None],
    ) -> None:
        self.page = page
        self.team = team
        self.on_save = on_save

    def show(self) -> None:
        is_edit = self.team is not None

        name_field = ft.TextField(
            label="Название команды *",
            value=self.team.name if self.team else "",
            hint_text="например: Backend Team",
        )
        project_field = ft.TextField(
            label="Ключ проекта Jira *",
            value=self.team.jira_project if self.team else "",
            hint_text="например: BACKEND",
        )
        task_type_dropdown = ft.Dropdown(
            label="Тип задачи по умолчанию",
            value=self.team.default_task_type if self.team else "Story",
            options=[
                ft.dropdown.Option("Story"),
                ft.dropdown.Option("Bug"),
                ft.dropdown.Option("Task"),
                ft.dropdown.Option("Epic"),
                ft.dropdown.Option("Sub-task"),
            ],
        )
        rules_field = ft.TextField(
            label="Правила команды",
            value=self.team.rules if self.team else "",
            multiline=True,
            min_lines=4,
            max_lines=8,
            hint_text="Опишите правила написания задач для этой команды...",
        )
        team_lead_field = ft.TextField(
            label="Руководитель команды",
            value=self.team.team_lead if self.team else "",
            hint_text="например: Иван Иванов",
        )
        error_text = ft.Text("", color=ft.Colors.RED_400)

        def save_clicked(e: ft.ControlEvent) -> None:
            new_name = (name_field.value or "").strip()
            new_project = (project_field.value or "").strip()

            if not new_name:
                error_text.value = "Введите название команды"
                error_text.update()
                return
            if not new_project:
                error_text.value = "Введите ключ проекта Jira"
                error_text.update()
                return

            # If renaming an existing team, remove the old file first
            if is_edit and self.team and self.team.name != new_name:
                delete_team(self.team.name)

            new_team = Team(
                name=new_name,
                jira_project=new_project.upper(),
                default_task_type=task_type_dropdown.value or "Story",
                rules=rules_field.value or "",
                team_lead=team_lead_field.value or "",
            )
            save_team(new_team)
            self.page.pop_dialog()
            self.on_save()

        def cancel_clicked(e: ft.ControlEvent) -> None:
            self.page.pop_dialog()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Редактировать команду" if is_edit else "Добавить команду"),
            content=ft.Container(
                width=560,
                content=ft.Column(
                    controls=[
                        name_field,
                        project_field,
                        task_type_dropdown,
                        rules_field,
                        team_lead_field,
                        error_text,
                    ],
                    spacing=12,
                    scroll=ft.ScrollMode.AUTO,
                ),
            ),
            actions=[
                ft.TextButton("Отмена", on_click=cancel_clicked),
                ft.ElevatedButton("Сохранить", on_click=save_clicked),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.show_dialog(dlg)

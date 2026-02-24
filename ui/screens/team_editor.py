from typing import Callable

import flet as ft

from data.models import Team
from data.teams_store import delete_team, save_team

_LINE_HEIGHT_PX = 24  # approximate pixel height per text line


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
        team_lead_field = ft.TextField(
            label="Руководитель команды",
            value=self.team.team_lead if self.team else "",
            hint_text="например: Иван Иванов",
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

        # --- Rules field: full-width, scrollable, resizable, with formatting toolbar ---
        _drag_start_y: list[float] = [0.0]
        _drag_start_lines: list[int] = [6]
        _saved_sel: list[int] = [0, 0]  # [start, end] saved on blur

        rules_field = ft.TextField(
            label="Правила команды",
            value=self.team.rules if self.team else "",
            multiline=True,
            min_lines=6,
            max_lines=6,
            hint_text="Опишите правила написания задач для этой команды...",
        )

        def on_rules_blur(e: ft.ControlEvent) -> None:
            try:
                sel = rules_field.selection
                if sel is not None and sel.base_offset is not None:
                    start = min(sel.base_offset, sel.extent_offset or sel.base_offset)
                    end = max(sel.base_offset, sel.extent_offset or sel.base_offset)
                    _saved_sel[0], _saved_sel[1] = start, end
            except Exception:
                pass

        rules_field.on_blur = on_rules_blur

        def apply_format(prefix: str, suffix: str) -> None:
            value = rules_field.value or ""
            start, end = _saved_sel[0], _saved_sel[1]
            start = min(start, len(value))
            end = min(end, len(value))
            rules_field.value = value[:start] + prefix + value[start:end] + suffix + value[end:]
            new_pos = start + len(prefix) + (end - start) + len(suffix)
            _saved_sel[0] = _saved_sel[1] = new_pos
            rules_field.update()
            rules_field.focus()

        def on_drag_start(e: ft.DragStartEvent) -> None:
            _drag_start_y[0] = e.global_y
            _drag_start_lines[0] = rules_field.max_lines or 6

        def on_drag_update(e: ft.DragUpdateEvent) -> None:
            delta = e.global_y - _drag_start_y[0]
            new_lines = max(3, _drag_start_lines[0] + int(delta / _LINE_HEIGHT_PX))
            rules_field.min_lines = new_lines
            rules_field.max_lines = new_lines
            rules_field.update()

        formatting_toolbar = ft.Row(
            controls=[
                ft.IconButton(
                    icon=ft.Icons.FORMAT_BOLD,
                    tooltip="Жирный (**текст**)",
                    on_click=lambda e: apply_format("**", "**"),
                    icon_size=18,
                    style=ft.ButtonStyle(padding=ft.padding.all(4)),
                ),
                ft.IconButton(
                    icon=ft.Icons.FORMAT_ITALIC,
                    tooltip="Курсив (*текст*)",
                    on_click=lambda e: apply_format("*", "*"),
                    icon_size=18,
                    style=ft.ButtonStyle(padding=ft.padding.all(4)),
                ),
                ft.IconButton(
                    icon=ft.Icons.CODE,
                    tooltip="Код (`текст`)",
                    on_click=lambda e: apply_format("`", "`"),
                    icon_size=18,
                    style=ft.ButtonStyle(padding=ft.padding.all(4)),
                ),
                ft.IconButton(
                    icon=ft.Icons.FORMAT_LIST_BULLETED,
                    tooltip="Список (- пункт)",
                    on_click=lambda e: apply_format("\n- ", ""),
                    icon_size=18,
                    style=ft.ButtonStyle(padding=ft.padding.all(4)),
                ),
                ft.PopupMenuButton(
                    icon=ft.Icons.FORMAT_COLOR_TEXT,
                    tooltip="Цвет текста",
                    items=[
                        ft.PopupMenuItem(
                            content=ft.Text("🔴 Красный"),
                            on_click=lambda e: apply_format('<span style="color:red">', "</span>"),
                        ),
                        ft.PopupMenuItem(
                            content=ft.Text("🔵 Синий"),
                            on_click=lambda e: apply_format('<span style="color:blue">', "</span>"),
                        ),
                        ft.PopupMenuItem(
                            content=ft.Text("🟢 Зелёный"),
                            on_click=lambda e: apply_format('<span style="color:green">', "</span>"),
                        ),
                        ft.PopupMenuItem(
                            content=ft.Text("🟠 Оранжевый"),
                            on_click=lambda e: apply_format('<span style="color:orange">', "</span>"),
                        ),
                    ],
                ),
                ft.VerticalDivider(width=12),
                ft.Text("Markdown", size=11, color=ft.Colors.GREY_500, italic=True),
            ],
            spacing=0,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        resize_handle = ft.GestureDetector(
            on_vertical_drag_start=on_drag_start,
            on_vertical_drag_update=on_drag_update,
            mouse_cursor=ft.MouseCursor.RESIZE_UP_DOWN,
            content=ft.Container(
                height=14,
                alignment=ft.alignment.center,
                content=ft.Icon(ft.Icons.DRAG_HANDLE, size=14, color=ft.Colors.GREY_400),
                bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE),
                border_radius=ft.BorderRadius(0, 0, 4, 4),
            ),
        )

        rules_section = ft.Column(
            controls=[
                formatting_toolbar,
                rules_field,
                resize_handle,
            ],
            spacing=0,
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
                        team_lead_field,
                        project_field,
                        task_type_dropdown,
                        rules_section,
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

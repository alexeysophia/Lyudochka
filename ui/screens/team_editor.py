from typing import Callable

import flet as ft

from data.models import Team
from data.teams_store import delete_team, save_team

_DIALOG_W = 560
_DIALOG_CONTENT_H = 520  # fixed height; content scrolls inside


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

        _field_padding = ft.padding.only(left=12, top=20, right=12, bottom=12)

        name_field = ft.TextField(
            label="Название команды *",
            value=self.team.name if self.team else "",
            hint_text="например: Backend Team",
            expand=True,
            content_padding=_field_padding,
        )
        team_lead_field = ft.TextField(
            label="Руководитель команды *",
            value=self.team.team_lead if self.team else "",
            hint_text="например: Иван Иванов",
            expand=True,
            content_padding=_field_padding,
        )
        project_field = ft.TextField(
            label="Ключ проекта Jira *",
            value=self.team.jira_project if self.team else "",
            hint_text="например: BACKEND",
            expand=True,
            content_padding=_field_padding,
        )
        task_type_dropdown = ft.Dropdown(
            label="Тип задачи",
            value=self.team.default_task_type if self.team else "Epic",
            expand=True,
            options=[
                ft.dropdown.Option("Story"),
                ft.dropdown.Option("Bug"),
                ft.dropdown.Option("Task"),
                ft.dropdown.Option("Epic"),
                ft.dropdown.Option("Sub-task"),
            ],
        )

        # --- Rules field: auto-grows with content, dialog scrolls ---
        _saved_sel: list[int] = [0, 0]

        rules_field = ft.TextField(
            label="Правила команды",
            value=self.team.rules if self.team else "",
            multiline=True,
            min_lines=10,
            align_label_with_hint=True,
            hint_text="Опишите правила написания задач для этой команды...",
        )

        def on_rules_blur(e: ft.ControlEvent) -> None:
            try:
                sel = rules_field.selection
                if sel is not None and sel.base_offset is not None:
                    _saved_sel[0] = min(sel.base_offset, sel.extent_offset or sel.base_offset)
                    _saved_sel[1] = max(sel.base_offset, sel.extent_offset or sel.base_offset)
            except Exception:
                pass

        rules_field.on_blur = on_rules_blur

        def apply_format(prefix: str, suffix: str) -> None:
            value = rules_field.value or ""
            try:
                sel = rules_field.selection
                if sel is not None and sel.base_offset is not None:
                    _saved_sel[0] = min(sel.base_offset, sel.extent_offset or sel.base_offset)
                    _saved_sel[1] = max(sel.base_offset, sel.extent_offset or sel.base_offset)
            except Exception:
                pass
            start = min(_saved_sel[0], len(value))
            end = min(_saved_sel[1], len(value))
            rules_field.value = (
                value[:start] + prefix + value[start:end] + suffix + value[end:]
            )
            _saved_sel[0] = _saved_sel[1] = start + len(prefix) + (end - start) + len(suffix)
            rules_field.update()
            self.page.run_task(rules_field.focus)

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
                            on_click=lambda e: apply_format(
                                '<span style="color:red">', "</span>"
                            ),
                        ),
                        ft.PopupMenuItem(
                            content=ft.Text("🔵 Синий"),
                            on_click=lambda e: apply_format(
                                '<span style="color:blue">', "</span>"
                            ),
                        ),
                        ft.PopupMenuItem(
                            content=ft.Text("🟢 Зелёный"),
                            on_click=lambda e: apply_format(
                                '<span style="color:green">', "</span>"
                            ),
                        ),
                        ft.PopupMenuItem(
                            content=ft.Text("🟠 Оранжевый"),
                            on_click=lambda e: apply_format(
                                '<span style="color:orange">', "</span>"
                            ),
                        ),
                    ],
                ),
                ft.VerticalDivider(width=12),
                ft.Text("Markdown", size=11, color=ft.Colors.GREY_500, italic=True),
            ],
            spacing=0,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        error_text = ft.Text("", color=ft.Colors.RED_400)

        # Keyboard shortcuts: Ctrl+B → bold, Ctrl+I → italic
        prev_keyboard_handler = self.page.on_keyboard_event

        def on_keyboard(e: ft.KeyboardEvent) -> None:
            if e.ctrl and e.key.lower() == "b":
                apply_format("**", "**")
            elif e.ctrl and e.key.lower() == "i":
                apply_format("*", "*")

        self.page.on_keyboard_event = on_keyboard

        def _restore_keyboard() -> None:
            self.page.on_keyboard_event = prev_keyboard_handler

        def save_clicked(e: ft.ControlEvent) -> None:
            new_name = (name_field.value or "").strip()
            new_project = (project_field.value or "").strip()

            if not new_name:
                error_text.value = "Введите название команды"
                error_text.update()
                return
            if not (team_lead_field.value or "").strip():
                error_text.value = "Введите руководителя команды"
                error_text.update()
                return
            if not new_project:
                error_text.value = "Введите ключ проекта Jira"
                error_text.update()
                return

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
            _restore_keyboard()
            self.page.pop_dialog()
            self.on_save()

        def cancel_clicked(e: ft.ControlEvent) -> None:
            _restore_keyboard()
            self.page.pop_dialog()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Редактировать команду" if is_edit else "Добавить команду"),
            content_padding=ft.padding.only(left=24, right=24, top=16, bottom=24),
            content=ft.Container(
                width=_DIALOG_W,
                height=_DIALOG_CONTENT_H,
                clip_behavior=ft.ClipBehavior.NONE,
                content=ft.Column(
                    controls=[
                        ft.Container(
                            padding=ft.padding.only(top=12),
                            clip_behavior=ft.ClipBehavior.NONE,
                            content=ft.Row(
                                controls=[name_field, team_lead_field],
                                spacing=12,
                            ),
                        ),
                        ft.Row(
                            controls=[project_field, task_type_dropdown],
                            spacing=12,
                        ),
                        formatting_toolbar,
                        rules_field,
                        error_text,
                    ],
                    spacing=12,
                    scroll=ft.ScrollMode.AUTO,
                    horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                ),
            ),
            actions=[
                ft.TextButton("Отмена", on_click=cancel_clicked),
                ft.ElevatedButton("Сохранить", on_click=save_clicked),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.show_dialog(dlg)

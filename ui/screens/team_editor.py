import asyncio
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

        # --- Rules state ---
        _rules_text: list[str] = [self.team.rules if self.team else ""]
        # Start in edit mode if no rules yet, otherwise show rendered view
        _rules_edit_mode: list[bool] = [not bool(_rules_text[0])]
        _saved_sel: list[int] = [0, 0]
        _rules_field: list[ft.TextField | None] = [None]

        # --- Formatting helpers ---

        def on_selection_change(e: ft.TextSelectionChangeEvent) -> None:
            if e.selection.base_offset is not None:
                _saved_sel[0] = min(
                    e.selection.base_offset,
                    e.selection.extent_offset or e.selection.base_offset,
                )
                _saved_sel[1] = max(
                    e.selection.base_offset,
                    e.selection.extent_offset or e.selection.base_offset,
                )

        def apply_format(prefix: str, suffix: str) -> None:
            field = _rules_field[0]
            if field is None:
                return
            value = field.value or ""
            start = min(_saved_sel[0], len(value))
            end = min(_saved_sel[1], len(value))
            field.value = (
                value[:start] + prefix + value[start:end] + suffix + value[end:]
            )
            _saved_sel[0] = _saved_sel[1] = (
                start + len(prefix) + (end - start) + len(suffix)
            )
            field.update()
            self.page.run_task(field.focus)

        # --- Formatting toolbar (shown only in edit mode) ---

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
                    icon=ft.Icons.FORMAT_UNDERLINED,
                    tooltip="Подчёркнутый (<u>текст</u>)  Ctrl+U",
                    on_click=lambda e: apply_format("<u>", "</u>"),
                    icon_size=18,
                    style=ft.ButtonStyle(padding=ft.padding.all(4)),
                ),
                ft.IconButton(
                    icon=ft.Icons.FORMAT_STRIKETHROUGH,
                    tooltip="Зачёркнутый (~~текст~~)",
                    on_click=lambda e: apply_format("~~", "~~"),
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
                ft.VerticalDivider(width=12),
                ft.Text("Markdown", size=11, color=ft.Colors.GREY_500, italic=True),
            ],
            spacing=0,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        # --- Rules area builders ---

        def _build_rules_edit_content() -> ft.Control:
            field = ft.TextField(
                value=_rules_text[0],
                multiline=True,
                min_lines=10,
                align_label_with_hint=True,
                hint_text="Опишите правила написания задач для этой команды...",
            )
            field.on_selection_change = on_selection_change
            _rules_field[0] = field
            return ft.Column(
                controls=[formatting_toolbar, field],
                spacing=4,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            )

        def _build_rules_view_content() -> ft.Control:
            _rules_field[0] = None
            if _rules_text[0]:
                return ft.Container(
                    padding=12,
                    bgcolor=ft.Colors.SURFACE_CONTAINER,
                    border_radius=8,
                    content=ft.Markdown(
                        value=_rules_text[0],
                        selectable=True,
                        extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                        soft_line_break=True,
                        expand=True,
                    ),
                )
            return ft.Container(
                padding=12,
                bgcolor=ft.Colors.SURFACE_CONTAINER,
                border_radius=8,
                content=ft.Text(
                    "Правила не заданы. Нажмите «Редактировать», чтобы добавить.",
                    color=ft.Colors.GREY_500,
                    italic=True,
                    size=13,
                ),
            )

        _rules_area = ft.Container(
            content=(
                _build_rules_edit_content()
                if _rules_edit_mode[0]
                else _build_rules_view_content()
            ),
        )

        # --- Edit / Save button ---

        edit_rules_btn = ft.IconButton(
            icon=ft.Icons.EDIT_OUTLINED if not _rules_edit_mode[0] else ft.Icons.CHECK,
            tooltip="Редактировать" if not _rules_edit_mode[0] else "Сохранить изменения",
        )

        def toggle_rules_edit(e: ft.ControlEvent) -> None:
            if _rules_edit_mode[0]:
                if _rules_field[0] is not None:
                    _rules_text[0] = _rules_field[0].value or ""
                _rules_edit_mode[0] = False
                edit_rules_btn.icon = ft.Icons.EDIT_OUTLINED
                edit_rules_btn.tooltip = "Редактировать"
                _rules_area.content = _build_rules_view_content()
            else:
                _rules_edit_mode[0] = True
                edit_rules_btn.icon = ft.Icons.CHECK
                edit_rules_btn.tooltip = "Сохранить изменения"
                _rules_area.content = _build_rules_edit_content()
            _rules_area.update()
            edit_rules_btn.update()

        edit_rules_btn.on_click = toggle_rules_edit

        error_text = ft.Text("", color=ft.Colors.RED_400)

        # Keyboard shortcuts: Ctrl+B/I/U → format; Shift+End → smart select
        # Only active in edit mode
        prev_keyboard_handler = self.page.on_keyboard_event

        def on_keyboard(e: ft.KeyboardEvent) -> None:
            if not _rules_edit_mode[0]:
                return
            if e.ctrl and e.key.lower() == "b":
                apply_format("**", "**")
            elif e.ctrl and e.key.lower() == "i":
                apply_format("*", "*")
            elif e.ctrl and e.key.lower() == "u":
                apply_format("<u>", "</u>")
            elif e.shift and e.key == "End":
                field = _rules_field[0]
                if field is None:
                    return
                anchor = _saved_sel[0]
                value = field.value or ""

                async def _fix_shift_end() -> None:
                    line_end = anchor
                    while line_end < len(value) and value[line_end] != "\n":
                        line_end += 1
                    extent = line_end
                    while extent > anchor and value[extent - 1] in (" ", "\t"):
                        extent -= 1
                    await asyncio.sleep(0.05)
                    try:
                        await field.focus()
                        field.selection = ft.TextSelection(
                            base_offset=anchor,
                            extent_offset=extent,
                        )
                        field.update()
                    except Exception:
                        pass

                self.page.run_task(_fix_shift_end)

        self.page.on_keyboard_event = on_keyboard

        def _restore_keyboard() -> None:
            self.page.on_keyboard_event = prev_keyboard_handler

        def _get_current_rules() -> str:
            if _rules_edit_mode[0] and _rules_field[0] is not None:
                return _rules_field[0].value or ""
            return _rules_text[0]

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
                rules=_get_current_rules(),
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
                        ft.Row(
                            controls=[
                                ft.Text(
                                    "Правила команды",
                                    size=13,
                                    weight=ft.FontWeight.W_500,
                                ),
                                ft.Container(expand=True),
                                edit_rules_btn,
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        _rules_area,
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

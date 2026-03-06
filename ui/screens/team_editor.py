import asyncio
from typing import Callable

import flet as ft

from core.jira_client import get_project_meta
from data.models import Team
from data.settings_store import load_settings
from data.teams_store import delete_team, is_lead_taken, is_name_taken, save_team

_DIALOG_W = 560
_DIALOG_CONTENT_H = 620  # fixed height; content scrolls inside


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

        # --- Jira meta state (loaded on demand) ---
        _jira_issue_types: list[dict] = []  # [{id, name}]
        _jira_fields: list[dict] = []  # {id, name}
        # Map type name → numeric Jira ID; pre-seed from existing team data
        _type_id_map: dict[str, str] = {}
        if self.team and self.team.default_task_type_id:
            _type_id_map[self.team.default_task_type] = self.team.default_task_type_id

        fetch_btn = ft.IconButton(
            icon=ft.Icons.CLOUD_DOWNLOAD_OUTLINED,
            tooltip="Получить типы задач и поля из Jira",
        )
        fetch_loading = ft.ProgressRing(visible=False, width=16, height=16, stroke_width=2)
        fetch_status = ft.Text("", size=11, color=ft.Colors.GREY_600, expand=True)

        # --- Task type ---
        _PRESET_TYPES = {"Story", "Bug", "Task", "Epic", "Sub-task"}
        _current_type = self.team.default_task_type if self.team else "Epic"
        _is_custom = _current_type not in _PRESET_TYPES

        task_type_dropdown = ft.Dropdown(
            label="Тип задачи",
            value="Custom" if _is_custom else _current_type,
            expand=True,
            options=[
                ft.dropdown.Option("Story"),
                ft.dropdown.Option("Bug"),
                ft.dropdown.Option("Task"),
                ft.dropdown.Option("Epic"),
                ft.dropdown.Option("Sub-task"),
                ft.dropdown.Option("Custom", "Свой тип..."),
            ],
        )
        custom_type_field = ft.TextField(
            label="Свой тип задачи",
            value=_current_type if _is_custom else "",
            hint_text="например: Задача",
            expand=True,
            visible=_is_custom,
            content_padding=_field_padding,
        )

        def on_task_type_change(e: ft.ControlEvent) -> None:
            custom_type_field.visible = (task_type_dropdown.value == "Custom")
            custom_type_field.update()

        task_type_dropdown.on_select = on_task_type_change

        async def _do_fetch_meta() -> None:
            proj_key = (project_field.value or "").strip().upper()
            if not proj_key:
                fetch_status.value = "Введите ключ проекта"
                fetch_status.color = ft.Colors.RED_400
                fetch_status.update()
                return
            settings = load_settings()
            if not settings.jira_url or not settings.jira_token:
                fetch_status.value = "Настройте подключение к Jira в Настройках"
                fetch_status.color = ft.Colors.RED_400
                fetch_status.update()
                return
            fetch_btn.disabled = True
            fetch_loading.visible = True
            fetch_status.value = ""
            fetch_btn.update()
            fetch_loading.update()
            fetch_status.update()
            try:
                meta = await get_project_meta(settings.jira_url, settings.jira_token, proj_key)
            except Exception as exc:
                fetch_status.value = f"Ошибка: {exc}"
                fetch_status.color = ft.Colors.RED_400
                fetch_status.update()
                return
            finally:
                fetch_btn.disabled = False
                fetch_loading.visible = False
                fetch_btn.update()
                fetch_loading.update()

            _jira_issue_types.clear()
            _jira_issue_types.extend(meta["issue_types"])
            _jira_fields.clear()
            _jira_fields.extend(meta["fields"])
            # Populate type name → ID map
            for t in _jira_issue_types:
                _type_id_map[t["name"]] = t["id"]

            # Update issue type dropdown
            current_val = task_type_dropdown.value
            effective = (custom_type_field.value or "").strip() if current_val == "Custom" else current_val
            type_names = [t["name"] for t in _jira_issue_types]
            new_opts = [ft.dropdown.Option(t["name"]) for t in _jira_issue_types]
            new_opts.append(ft.dropdown.Option("Custom", "Свой тип..."))
            task_type_dropdown.options = new_opts
            if effective in type_names:
                task_type_dropdown.value = effective
                custom_type_field.visible = False
                custom_type_field.update()
            task_type_dropdown.update()

            # Rebuild extra-fields add-row and existing rows
            _add_field_row_container.content = _build_add_row()
            _add_field_row_container.update()
            _extra_fields_column.controls = _build_field_rows()
            _extra_fields_column.update()

            fetch_status.value = f"Получено: {len(_jira_issue_types)} типов, {len(_jira_fields)} полей"
            fetch_status.color = ft.Colors.GREEN_700
            fetch_status.update()

        fetch_btn.on_click = lambda e: self.page.run_task(_do_fetch_meta)

        context_field = ft.TextField(
            label="Контекст команды",
            value=self.team.context if self.team else "",
            hint_text="Опишите с какими продуктами работает команда и какие задачи выполняет...",
            multiline=True,
            min_lines=3,
            max_lines=6,
            align_label_with_hint=True,
            content_padding=_field_padding,
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

        # --- Extra Jira fields ---
        _extra_fields: dict[str, str] = dict(
            self.team.extra_jira_fields if self.team else {}
        )

        def _field_label(fid: str) -> str:
            for f in _jira_fields:
                if f["id"] == fid:
                    return f["name"]
            return fid

        def _build_field_rows() -> list[ft.Control]:
            rows: list[ft.Control] = []
            for fk, fv in list(_extra_fields.items()):
                def make_delete(k: str = fk) -> None:
                    def on_delete(e: ft.ControlEvent) -> None:
                        _extra_fields.pop(k, None)
                        _extra_fields_column.controls = _build_field_rows()
                        _extra_fields_column.update()
                    return on_delete
                label = _field_label(fk)
                rows.append(
                    ft.Row(
                        controls=[
                            ft.Text(label, size=13, weight=ft.FontWeight.W_500, expand=1),
                            ft.Text(fv, size=13, color=ft.Colors.GREY_700, expand=2),
                            ft.IconButton(
                                icon=ft.Icons.DELETE_OUTLINE,
                                icon_size=18,
                                tooltip="Удалить поле",
                                on_click=make_delete(),
                                style=ft.ButtonStyle(color=ft.Colors.RED_400),
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=4,
                    )
                )
            return rows

        _extra_fields_column = ft.Column(controls=_build_field_rows(), spacing=6)

        def _build_add_row() -> ft.Row:
            if _jira_fields:
                key_ctrl: ft.Control = ft.Dropdown(
                    options=[ft.dropdown.Option(f["id"], f["name"]) for f in _jira_fields],
                    hint_text="Выберите поле",
                    dense=True,
                    expand=2,
                )
            else:
                key_ctrl = ft.TextField(
                    hint_text="Поле (напр. priority, affectedVersion)",
                    dense=True,
                    expand=2,
                )
            val_field = ft.TextField(hint_text="Значение", dense=True, expand=3)

            def do_add(e: ft.ControlEvent) -> None:
                k = (key_ctrl.value or "").strip()
                v = (val_field.value or "").strip()
                if k:
                    _extra_fields[k] = v
                    _extra_fields_column.controls = _build_field_rows()
                    _extra_fields_column.update()
                    _add_field_row_container.content = _build_add_row()
                    _add_field_row_container.update()

            val_field.on_submit = do_add
            return ft.Row(
                controls=[
                    key_ctrl,
                    val_field,
                    ft.IconButton(icon=ft.Icons.ADD, tooltip="Добавить поле", on_click=do_add),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=4,
            )

        _add_field_row_container = ft.Container(content=_build_add_row())

        extra_jira_section = ft.Column(
            controls=[
                ft.Text("Дополнительные поля Jira", size=13, weight=ft.FontWeight.W_500),
                _extra_fields_column,
                _add_field_row_container,
            ],
            spacing=6,
        )

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
            new_lead = (team_lead_field.value or "").strip()
            new_project = (project_field.value or "").strip()
            original_name = self.team.name if self.team else ""

            if not new_name:
                error_text.value = "Введите название команды"
                error_text.update()
                return
            if not new_lead:
                error_text.value = "Введите руководителя команды"
                error_text.update()
                return
            if not new_project:
                error_text.value = "Введите ключ проекта Jira"
                error_text.update()
                return
            if is_name_taken(new_name, exclude_name=original_name):
                error_text.value = "Команда с таким названием уже существует"
                error_text.update()
                return
            if is_lead_taken(new_lead, exclude_name=original_name):
                error_text.value = "Этот руководитель уже назначен на другую команду"
                error_text.update()
                return

            if is_edit and self.team and self.team.name != new_name:
                delete_team(self.team.name)

            if task_type_dropdown.value == "Custom":
                chosen_type = (custom_type_field.value or "").strip()
                if not chosen_type:
                    error_text.value = "Введите свой тип задачи"
                    error_text.update()
                    return
            else:
                chosen_type = task_type_dropdown.value or "Story"

            new_team = Team(
                name=new_name,
                jira_project=new_project.upper(),
                default_task_type=chosen_type,
                default_task_type_id=_type_id_map.get(chosen_type, ""),
                rules=_get_current_rules(),
                team_lead=new_lead,
                context=context_field.value or "",
                extra_jira_fields=dict(_extra_fields),
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
                            controls=[
                                project_field,
                                fetch_btn,
                                fetch_loading,
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=4,
                        ),
                        ft.Row(
                            controls=[fetch_status],
                            spacing=4,
                        ),
                        ft.Row(
                            controls=[task_type_dropdown, custom_type_field],
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
                        context_field,
                        extra_jira_section,
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

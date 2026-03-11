import asyncio
import json
from typing import Callable

import flet as ft

from core.jira_client import get_insight_objects, get_project_meta
from data.models import Team
from data.settings_store import load_settings
from data.teams_store import delete_team, is_lead_taken, is_name_taken, save_team
from ui.snack import error_snack

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

        # --- Jira meta state (loaded on demand or pre-populated from saved team) ---
        _jira_issue_types: list[dict] = []
        _jira_fields: list[dict] = []
        _type_id_map: dict[str, str] = {}
        if self.team and self.team.default_task_type_id:
            _type_id_map[self.team.default_task_type] = self.team.default_task_type_id

        # Pre-populate from saved meta so user can work without re-fetching
        if self.team and self.team.jira_issue_types_meta:
            _jira_issue_types.extend(self.team.jira_issue_types_meta)
            for t in _jira_issue_types:
                _type_id_map[t["name"]] = t["id"]
        if self.team and self.team.jira_fields_meta:
            _jira_fields.extend(self.team.jira_fields_meta)

        has_meta = bool(_jira_fields)

        fetch_btn = ft.ElevatedButton(
            "Обновить поля из Jira" if has_meta else "Получить поля из Jira",
            icon=ft.Icons.CLOUD_SYNC if has_meta else ft.Icons.CLOUD_DOWNLOAD_OUTLINED,
            expand=True,
        )
        fetch_loading = ft.ProgressRing(visible=False, width=16, height=16, stroke_width=2)
        fetch_status = ft.Text("", size=11, color=ft.Colors.GREY_600, expand=True)

        # --- Task type ---
        _current_type = self.team.default_task_type if self.team else ""
        _initial_type_opts = (
            [ft.dropdown.Option(_current_type)] if _current_type and not _jira_issue_types else []
        )
        task_type_dropdown = ft.Dropdown(
            label="Тип задачи",
            value=_current_type or None,
            hint_text="Получите типы из Jira ↑",
            expand=True,
            options=(
                [ft.dropdown.Option(t["name"]) for t in _jira_issue_types]
                if _jira_issue_types else _initial_type_opts
            ),
            disabled=not bool(_jira_issue_types),
        )

        # --- Add-row state (tracks selected field + accumulated multi-values) ---
        _add_row_state: list[dict] = [{"field_id": None, "multi_ids": []}]

        # Forward declaration — assigned below after _build_add_row is defined
        _add_field_row_container: ft.Container

        async def _do_fetch_meta() -> None:
            proj_key = (project_field.value or "").strip().upper()
            if not proj_key:
                error_snack(self.page, "Введите ключ проекта Jira")
                return
            settings = load_settings()
            if not settings.jira_url or not settings.jira_token:
                error_snack(self.page, "Настройте подключение к Jira в Настройках")
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
                error_snack(self.page, str(exc))
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
            for t in _jira_issue_types:
                _type_id_map[t["name"]] = t["id"]

            # Update issue type dropdown
            current_val = task_type_dropdown.value
            type_names = [t["name"] for t in _jira_issue_types]
            task_type_dropdown.options = [ft.dropdown.Option(t["name"]) for t in _jira_issue_types]
            task_type_dropdown.disabled = False
            task_type_dropdown.value = current_val if current_val in type_names else None
            task_type_dropdown.update()

            # Rebuild add-row (now has field meta with allowed_values)
            _add_row_state[0] = {"field_id": None, "multi_ids": []}
            _add_field_row_container.content = _build_add_row()
            self.page.update()
            _extra_fields_column.controls = _build_field_rows()
            _extra_fields_column.update()

            # Update button to "Обновить"
            fetch_btn.content = "Обновить поля из Jira"
            fetch_btn.icon = ft.Icons.CLOUD_SYNC
            fetch_btn.update()

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
        _rules_edit_mode: list[bool] = [not bool(_rules_text[0])]
        _saved_sel: list[int] = [0, 0]
        _rules_field: list[ft.TextField | None] = [None]

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

        def _display_value(fid: str, raw: str) -> str:
            """Convert stored JSON value back to human-readable string."""
            fmeta = next((f for f in _jira_fields if f["id"] == fid), None)
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    names: list[str] = []
                    for item in parsed:
                        if isinstance(item, dict) and "id" in item:
                            vid = item["id"]
                            if fmeta and fmeta.get("allowed_values"):
                                name = next(
                                    (av["name"] for av in fmeta["allowed_values"] if av["id"] == vid),
                                    vid,
                                )
                            else:
                                name = vid
                            names.append(name)
                    return ", ".join(names) if names else raw
                elif isinstance(parsed, dict) and "id" in parsed:
                    vid = parsed["id"]
                    if fmeta and fmeta.get("allowed_values"):
                        return next(
                            (av["name"] for av in fmeta["allowed_values"] if av["id"] == vid),
                            vid,
                        )
                    return vid
            except (json.JSONDecodeError, TypeError):
                pass
            return raw

        def _build_field_rows() -> list[ft.Control]:
            rows: list[ft.Control] = []
            for fk, fv in list(_extra_fields.items()):
                def make_delete(k: str = fk) -> ft.ControlEvent:
                    def on_delete(e: ft.ControlEvent) -> None:
                        _extra_fields.pop(k, None)
                        _extra_fields_column.controls = _build_field_rows()
                        _extra_fields_column.update()
                    return on_delete
                label = _field_label(fk)
                display = _display_value(fk, fv)
                rows.append(
                    ft.Row(
                        controls=[
                            ft.Text(label, size=13, weight=ft.FontWeight.W_500, expand=1),
                            ft.Text(display, size=13, color=ft.Colors.GREY_700, expand=2),
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

        def _build_add_row() -> ft.Control:
            meta_loaded = bool(_jira_fields)
            if not meta_loaded:
                return ft.Row(
                    controls=[
                        ft.TextField(
                            hint_text="Сначала получите поля из Jira ↑",
                            dense=True,
                            expand=2,
                            disabled=True,
                        ),
                        ft.TextField(hint_text="Значение", dense=True, expand=3, disabled=True),
                        ft.IconButton(icon=ft.Icons.ADD, tooltip="Добавить поле", disabled=True),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=4,
                )

            state = _add_row_state[0]
            cur_fid: str | None = state.get("field_id")
            cur_multi_ids: list[str] = list(state.get("multi_ids", []))
            is_loading: bool = state.get("loading", False)
            cur_fmeta: dict | None = (
                next((f for f in _jira_fields if f["id"] == cur_fid), None)
                if cur_fid else None
            )

            def on_field_select(e: ft.ControlEvent) -> None:
                _add_row_state[0] = {"field_id": e.control.value, "multi_ids": [], "loading": False}
                _add_field_row_container.content = _build_add_row()
                self.page.update()

            key_dd = ft.Dropdown(
                options=[ft.dropdown.Option(f["id"], f["name"]) for f in _jira_fields],
                value=cur_fid,
                hint_text="Выберите поле",
                dense=True,
                expand=2,
                on_select=on_field_select,
            )

            # --- Build value control based on field meta ---
            chips_controls: list[ft.Control] = []
            is_insight = cur_fmeta is not None and cur_fmeta.get("insight", False)
            has_values = bool(cur_fmeta and cur_fmeta.get("allowed_values"))

            if cur_fmeta is None:
                # No field selected — free text placeholder
                val_ctrl: ft.Control = ft.TextField(
                    hint_text="Значение",
                    dense=True,
                    expand=3,
                    disabled=True,
                )

                def get_val() -> str:
                    return ""

            elif is_insight and not has_values:
                # Insight field without loaded values — show fetch button
                if is_loading:
                    val_ctrl = ft.Row(
                        controls=[
                            ft.ProgressRing(width=18, height=18, stroke_width=2),
                            ft.Text("Загрузка значений...", size=13, color=ft.Colors.GREY_600),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=8,
                        expand=3,
                    )
                else:
                    async def _do_fetch_insight(e: ft.ControlEvent) -> None:
                        _add_row_state[0]["loading"] = True
                        _add_field_row_container.content = _build_add_row()
                        self.page.update()
                        try:
                            settings = load_settings()
                            if not settings.jira_url or not settings.jira_token:
                                raise ValueError("Настройте подключение к Jira в Настройках")
                            objects = await get_insight_objects(
                                settings.jira_url, settings.jira_token, cur_fmeta["name"]
                            )
                            # Store fetched values into _jira_fields for this field
                            idx = next((i for i, f in enumerate(_jira_fields) if f["id"] == cur_fid), None)
                            if idx is not None:
                                _jira_fields[idx]["allowed_values"] = objects
                                _jira_fields[idx]["multi"] = True
                            _add_row_state[0] = {"field_id": cur_fid, "multi_ids": [], "loading": False}
                        except Exception as exc:
                            _add_row_state[0]["loading"] = False
                            error_snack(self.page, str(exc))
                        _add_field_row_container.content = _build_add_row()
                        self.page.update()

                    val_ctrl = ft.ElevatedButton(
                        "Получить значения",
                        icon=ft.Icons.CLOUD_DOWNLOAD_OUTLINED,
                        on_click=lambda e: self.page.run_task(_do_fetch_insight, e),
                        expand=3,
                    )

                def get_val() -> str:
                    return ""

            elif is_insight or cur_fmeta["multi"]:
                # Multi-select: dropdown picker + chips
                already_ids = set(cur_multi_ids)
                pick_dd = ft.Dropdown(
                    options=[
                        ft.dropdown.Option(av["id"], av["name"])
                        for av in cur_fmeta["allowed_values"]
                        if av["id"] not in already_ids
                    ],
                    hint_text="Добавить значение...",
                    dense=True,
                    expand=True,
                )

                def on_add_multi_val(e: ft.ControlEvent) -> None:
                    vid = pick_dd.value
                    if vid and vid not in _add_row_state[0]["multi_ids"]:
                        _add_row_state[0]["multi_ids"].append(vid)
                        _add_field_row_container.content = _build_add_row()
                        self.page.update()

                val_ctrl = ft.Row(
                    controls=[
                        pick_dd,
                        ft.IconButton(
                            icon=ft.Icons.ADD_CIRCLE_OUTLINE,
                            icon_size=20,
                            tooltip="Добавить значение",
                            on_click=on_add_multi_val,
                        ),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=4,
                    expand=3,
                )

                for vid in cur_multi_ids:
                    vname = next(
                        (av["name"] for av in cur_fmeta["allowed_values"] if av["id"] == vid),
                        vid,
                    )

                    def make_remove_chip(v: str = vid) -> Callable:
                        def handler(e: ft.ControlEvent) -> None:
                            _add_row_state[0]["multi_ids"] = [
                                x for x in _add_row_state[0]["multi_ids"] if x != v
                            ]
                            _add_field_row_container.content = _build_add_row()
                            self.page.update()
                        return handler

                    chips_controls.append(
                        ft.Container(
                            content=ft.Row(
                                controls=[
                                    ft.Text(vname, size=12),
                                    ft.IconButton(
                                        icon=ft.Icons.CLOSE,
                                        icon_size=14,
                                        on_click=make_remove_chip(),
                                        style=ft.ButtonStyle(padding=ft.padding.all(0)),
                                    ),
                                ],
                                spacing=2,
                                tight=True,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            bgcolor=ft.Colors.BLUE_100,
                            border_radius=12,
                            padding=ft.padding.symmetric(horizontal=8, vertical=2),
                        )
                    )

                def get_val() -> str:
                    ids = _add_row_state[0]["multi_ids"]
                    if not ids:
                        return ""
                    if is_insight:
                        return json.dumps([{"key": iid} for iid in ids])
                    return json.dumps([{"id": iid} for iid in ids])

            elif not has_values:
                # Non-insight field without allowed_values — free text
                val_ctrl = ft.TextField(
                    hint_text="Значение",
                    dense=True,
                    expand=3,
                )

                def get_val() -> str:
                    return (val_ctrl.value or "").strip()  # type: ignore[union-attr]

            else:
                # Single select from allowed values
                val_ctrl = ft.Dropdown(
                    options=[
                        ft.dropdown.Option(av["id"], av["name"])
                        for av in cur_fmeta["allowed_values"]
                    ],
                    hint_text="Выберите значение...",
                    dense=True,
                    expand=3,
                )

                def get_val() -> str:
                    vid = val_ctrl.value  # type: ignore[union-attr]
                    if not vid:
                        return ""
                    return json.dumps({"id": vid})

            def do_add(e: ft.ControlEvent) -> None:
                k = (key_dd.value or "").strip()
                v = get_val()
                if k and v:
                    _extra_fields[k] = v
                    _add_row_state[0] = {"field_id": None, "multi_ids": [], "loading": False}
                    _extra_fields_column.controls = _build_field_rows()
                    _extra_fields_column.update()
                    _add_field_row_container.content = _build_add_row()
                    self.page.update()

            main_row = ft.Row(
                controls=[
                    key_dd,
                    val_ctrl,
                    ft.IconButton(
                        icon=ft.Icons.ADD,
                        tooltip="Добавить поле",
                        on_click=do_add,
                        disabled=is_loading,
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=4,
            )

            if chips_controls:
                return ft.Column(
                    controls=[
                        main_row,
                        ft.Row(controls=chips_controls, spacing=4, wrap=True),
                    ],
                    spacing=6,
                    horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                )
            return main_row

        _extra_fields_column = ft.Column(controls=_build_field_rows(), spacing=6)
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

        # Keyboard shortcuts
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

            chosen_type = task_type_dropdown.value or ""
            if not chosen_type:
                error_text.value = "Выберите тип задачи (нажмите кнопку получения типов из Jira)"
                error_text.update()
                return

            new_team = Team(
                name=new_name,
                jira_project=new_project.upper(),
                default_task_type=chosen_type,
                default_task_type_id=_type_id_map.get(chosen_type, ""),
                rules=_get_current_rules(),
                team_lead=new_lead,
                context=context_field.value or "",
                extra_jira_fields=dict(_extra_fields),
                jira_fields_meta=list(_jira_fields),
                jira_issue_types_meta=list(_jira_issue_types),
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
                                ft.Row(
                                    controls=[fetch_btn, fetch_loading],
                                    expand=True,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    spacing=6,
                                ),
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=12,
                        ),
                        ft.Row(
                            controls=[fetch_status],
                            spacing=4,
                        ),
                        task_type_dropdown,
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

import json
import logging
import re
from typing import Callable

import flet as ft

from core.jira_client import get_insight_objects, get_project_meta, update_jira_issue
from data.settings_store import load_settings
from data.teams_store import load_all_teams
from ui.snack import error_snack

log = logging.getLogger(__name__)

# Matches a Jira browse URL: .../browse/PROJ-123
_URL_RE = re.compile(r"/browse/([A-Z][A-Z0-9_]*-\d+)", re.IGNORECASE)
# Matches a plain issue key: PROJECT-123
_KEY_RE = re.compile(r"\b([A-Z][A-Z0-9_]*-\d+)\b")


def _extract_issue_key(raw: str, project_key: str) -> str | None:
    raw = raw.strip()
    if not raw:
        return None
    m = _URL_RE.search(raw)
    if m:
        return m.group(1).upper()
    m = _KEY_RE.fullmatch(raw.upper())
    if m:
        return m.group(1)
    if raw.isdigit() and project_key:
        return f"{project_key}-{raw}"
    return raw.upper()


def _parse_issues(text: str, project_key: str) -> list[str]:
    parts = [p.strip() for p in re.split(r"[,\n]+", text)]
    result: list[str] = []
    for part in parts:
        key = _extract_issue_key(part, project_key)
        if key:
            result.append(key)
    return result


class BulkEditScreen:
    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self._last_project_key: str = ""
        self._jira_fields: list[dict] = []
        self._extra_fields: dict[str, str] = {}
        self._add_row_state: list[dict] = [{"field_id": None, "multi_ids": [], "loading": False}]

        # UI refs updated each build(); used by async handlers
        self._load_btn: ft.ElevatedButton | None = None
        self._load_status: ft.Text | None = None
        self._targets_field: ft.TextField | None = None
        self._apply_btn: ft.ElevatedButton | None = None
        self._results_col: ft.Column | None = None
        self._extra_fields_column: ft.Column | None = None
        self._add_field_row_container: ft.Container | None = None

        # Closures from the latest build(); used by _do_fetch_meta after meta loads
        self._rebuild_field_rows: Callable[[], list[ft.Control]] | None = None
        self._rebuild_add_row: Callable[[], ft.Control] | None = None

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def build(self) -> ft.Control:
        team_keys = sorted({t.jira_project for t in load_all_teams() if t.jira_project})

        project_ac = ft.AutoComplete(
            value=self._last_project_key,
            suggestions=[ft.AutoCompleteSuggestion(key=k, value=k) for k in team_keys],
            suggestions_max_height=200,
            on_select=self._on_project_key_selected,
            on_change=self._on_project_key_change,
        )

        has_meta = bool(self._jira_fields)
        self._load_btn = ft.ElevatedButton(
            "Обновить поля из Jira" if has_meta else "Получить поля из Jira",
            icon=ft.Icons.CLOUD_SYNC if has_meta else ft.Icons.CLOUD_DOWNLOAD_OUTLINED,
            on_click=lambda e: self.page.run_task(self._do_fetch_meta),
        )
        self._load_status = ft.Text(
            f"Загружено {len(self._jira_fields)} полей" if has_meta else "",
            size=13,
            color=ft.Colors.GREEN_700 if has_meta else ft.Colors.GREY_600,
        )

        # ---- Extra-fields closures (pattern from team_editor) ----

        def _field_label(fid: str) -> str:
            for f in self._jira_fields:
                if f["id"] == fid:
                    return f["name"]
            return fid

        def _display_value(fid: str, raw: str) -> str:
            fmeta = next((f for f in self._jira_fields if f["id"] == fid), None)
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    names: list[str] = []
                    for item in parsed:
                        if isinstance(item, dict):
                            vid = item.get("id") or item.get("key")
                            if vid:
                                name = vid
                                if fmeta and fmeta.get("allowed_values"):
                                    name = next(
                                        (av["name"] for av in fmeta["allowed_values"] if av["id"] == vid),
                                        vid,
                                    )
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
            for fk, fv in list(self._extra_fields.items()):
                def make_delete(k: str = fk) -> Callable:
                    def on_delete(e: ft.ControlEvent) -> None:
                        self._extra_fields.pop(k, None)
                        if self._extra_fields_column is not None:
                            self._extra_fields_column.controls = _build_field_rows()
                            self._extra_fields_column.update()
                        if self._add_field_row_container is not None:
                            self._add_field_row_container.content = _build_add_row()
                        self._update_apply_btn()
                        self.page.update()
                    return on_delete

                rows.append(
                    ft.Row(
                        controls=[
                            ft.Text(_field_label(fk), size=13, weight=ft.FontWeight.W_500, expand=1),
                            ft.Text(_display_value(fk, fv), size=13, color=ft.Colors.GREY_700, expand=2),
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
            if not rows:
                rows = [
                    ft.Text(
                        "Нет выбранных изменений",
                        size=12,
                        color=ft.Colors.GREY_500,
                        italic=True,
                    )
                ]
            return rows

        def _build_add_row() -> ft.Control:
            if not self._jira_fields:
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

            state = self._add_row_state[0]
            cur_fid: str | None = state.get("field_id")
            cur_multi_ids: list[str] = list(state.get("multi_ids", []))
            is_loading: bool = state.get("loading", False)
            cur_fmeta: dict | None = (
                next((f for f in self._jira_fields if f["id"] == cur_fid), None)
                if cur_fid else None
            )

            def on_field_select(e: ft.ControlEvent) -> None:
                self._add_row_state[0] = {"field_id": e.control.value, "multi_ids": [], "loading": False}
                if self._add_field_row_container is not None:
                    self._add_field_row_container.content = _build_add_row()
                self.page.update()

            _available_fields = [
                f for f in self._jira_fields
                if f["id"] not in self._extra_fields
            ]

            key_dd = ft.Dropdown(
                options=[ft.dropdown.Option(f["id"], f["name"]) for f in _available_fields],
                value=cur_fid if cur_fid not in self._extra_fields else None,
                hint_text="Выберите поле",
                dense=True,
                expand=2,
                on_select=on_field_select,
            )

            chips_controls: list[ft.Control] = []
            is_insight = cur_fmeta is not None and cur_fmeta.get("insight", False)
            has_values = bool(cur_fmeta and cur_fmeta.get("allowed_values"))

            if cur_fmeta is None:
                val_ctrl: ft.Control = ft.TextField(
                    hint_text="Значение",
                    dense=True,
                    expand=3,
                    disabled=True,
                    content_padding=ft.padding.only(left=10, top=16, right=10, bottom=16),
                )

                def get_val() -> str:
                    return ""

            elif is_insight and not has_values:
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
                    _type_id_field = ft.TextField(
                        label="TypeID",
                        dense=True,
                        width=90,
                        keyboard_type=ft.KeyboardType.NUMBER,
                        tooltip="Из URL Jira: ObjectSchema.jspa?id=…&typeId=XXXX",
                        content_padding=ft.padding.only(left=10, top=16, right=10, bottom=16),
                    )

                    _captured_fid = cur_fid
                    _captured_fmeta = cur_fmeta

                    async def _do_fetch_insight(e: ft.ControlEvent) -> None:
                        self._add_row_state[0]["loading"] = True
                        if self._add_field_row_container is not None:
                            self._add_field_row_container.content = _build_add_row()
                        self.page.update()
                        try:
                            settings = load_settings()
                            if not settings.jira_url or not settings.jira_token:
                                raise ValueError("Настройте подключение к Jira в Настройках")
                            raw_tid = (_type_id_field.value or "").strip()
                            explicit_type_id = int(raw_tid) if raw_tid.isdigit() else None
                            objects = await get_insight_objects(
                                settings.jira_url, settings.jira_token,
                                _captured_fmeta["name"], _captured_fid or "",
                                object_type_id=explicit_type_id,
                            )
                            idx = next(
                                (i for i, f in enumerate(self._jira_fields) if f["id"] == _captured_fid),
                                None,
                            )
                            if idx is not None:
                                self._jira_fields[idx]["allowed_values"] = objects
                                self._jira_fields[idx]["multi"] = True
                            self._add_row_state[0] = {
                                "field_id": _captured_fid, "multi_ids": [], "loading": False,
                            }
                        except Exception as exc:
                            self._add_row_state[0]["loading"] = False
                            error_snack(self.page, str(exc))
                        if self._add_field_row_container is not None:
                            self._add_field_row_container.content = _build_add_row()
                        self.page.update()

                    val_ctrl = ft.Column(
                        controls=[
                            ft.Row(
                                controls=[
                                    _type_id_field,
                                    ft.ElevatedButton(
                                        "Получить значения",
                                        icon=ft.Icons.CLOUD_DOWNLOAD_OUTLINED,
                                        on_click=lambda e: self.page.run_task(_do_fetch_insight, e),
                                        expand=True,
                                    ),
                                ],
                                spacing=6,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                        ],
                        spacing=0,
                        expand=3,
                        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                    )

                def get_val() -> str:
                    return ""

            elif is_insight or cur_fmeta["multi"]:
                already_ids = set(cur_multi_ids)
                filtered_avs = [av for av in cur_fmeta["allowed_values"] if av["id"] not in already_ids]

                def on_add_multi_val(e: ft.ControlEvent) -> None:
                    vid = e.control.value
                    if vid and vid not in self._add_row_state[0]["multi_ids"]:
                        self._add_row_state[0]["multi_ids"].append(vid)
                        if self._add_field_row_container is not None:
                            self._add_field_row_container.content = _build_add_row()
                        self.page.update()

                pick_dd = ft.Dropdown(
                    options=[ft.dropdown.Option(av["id"], av["name"]) for av in filtered_avs],
                    hint_text="Добавить значение...",
                    dense=True,
                    expand=3,
                    on_select=on_add_multi_val,
                )
                val_ctrl = ft.Column(
                    controls=[ft.Row(controls=[pick_dd], spacing=4)],
                    spacing=4,
                    expand=3,
                    horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                )

                for vid in cur_multi_ids:
                    vname = next(
                        (av["name"] for av in cur_fmeta["allowed_values"] if av["id"] == vid),
                        vid,
                    )

                    def make_remove_chip(v: str = vid) -> Callable:
                        def handler(e: ft.ControlEvent) -> None:
                            self._add_row_state[0]["multi_ids"] = [
                                x for x in self._add_row_state[0]["multi_ids"] if x != v
                            ]
                            if self._add_field_row_container is not None:
                                self._add_field_row_container.content = _build_add_row()
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
                    ids = self._add_row_state[0]["multi_ids"]
                    if not ids:
                        return ""
                    if is_insight:
                        return json.dumps([{"key": iid} for iid in ids])
                    return json.dumps([{"id": iid} for iid in ids])

            elif not has_values:
                val_ctrl = ft.TextField(
                    hint_text="Значение",
                    dense=True,
                    expand=3,
                    content_padding=ft.padding.only(left=10, top=16, right=10, bottom=16),
                )

                def get_val() -> str:
                    return (val_ctrl.value or "").strip()  # type: ignore[union-attr]

            else:
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

            if cur_fmeta is None or is_loading:
                _add_btn_disabled = True
            elif is_insight or cur_fmeta["multi"]:
                _add_btn_disabled = len(cur_multi_ids) == 0
            else:
                _add_btn_disabled = not bool(get_val())

            _add_btn_ref: list[ft.IconButton | None] = [None]

            def _refresh_add_btn() -> None:
                btn = _add_btn_ref[0]
                if btn is None:
                    return
                enabled = bool((key_dd.value or "").strip()) and bool(get_val())
                btn.disabled = not enabled
                btn.update()

            def do_add(e: ft.ControlEvent) -> None:
                k = (key_dd.value or "").strip()
                v = get_val()
                if k and v:
                    self._extra_fields[k] = v
                    self._add_row_state[0] = {"field_id": None, "multi_ids": [], "loading": False}
                    if self._extra_fields_column is not None:
                        self._extra_fields_column.controls = _build_field_rows()
                        self._extra_fields_column.update()
                    if self._add_field_row_container is not None:
                        self._add_field_row_container.content = _build_add_row()
                    self._update_apply_btn()
                    self.page.update()

            if isinstance(val_ctrl, ft.TextField):
                _orig_on_change = val_ctrl.on_change

                def _on_val_change(e: ft.ControlEvent) -> None:
                    if _orig_on_change:
                        _orig_on_change(e)
                    _refresh_add_btn()

                val_ctrl.on_change = _on_val_change
            elif isinstance(val_ctrl, ft.Dropdown):
                _orig_on_select = val_ctrl.on_select

                def _on_val_select(e: ft.ControlEvent) -> None:
                    if _orig_on_select:
                        _orig_on_select(e)
                    _refresh_add_btn()

                val_ctrl.on_select = _on_val_select

            _add_btn = ft.IconButton(
                icon=ft.Icons.ADD,
                tooltip="Добавить поле",
                on_click=do_add,
                disabled=_add_btn_disabled,
            )
            _add_btn_ref[0] = _add_btn

            main_row = ft.Row(
                controls=[key_dd, val_ctrl, _add_btn],
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

        # Wire up closure references
        self._rebuild_field_rows = _build_field_rows
        self._rebuild_add_row = _build_add_row

        extra_fields_col = ft.Column(controls=_build_field_rows(), spacing=6)
        add_field_row_cont = ft.Container(content=_build_add_row())
        self._extra_fields_column = extra_fields_col
        self._add_field_row_container = add_field_row_cont

        self._targets_field = ft.TextField(
            label="Список задач",
            hint_text="Ключи, номера или ссылки — через запятую или с новой строки",
            multiline=True,
            min_lines=4,
            max_lines=10,
            expand=True,
            on_change=self._update_apply_btn,
        )

        self._apply_btn = ft.ElevatedButton(
            "Применить изменения",
            icon=ft.Icons.SAVE_OUTLINED,
            on_click=lambda e: self.page.run_task(self._do_apply),
            disabled=True,
            width=220,
        )

        self._results_col = ft.Column(controls=[], spacing=6)

        return ft.Container(
            padding=30,
            expand=True,
            content=ft.Column(
                controls=[
                    ft.Text("Массовое изменение задач", size=24, weight=ft.FontWeight.BOLD),
                    ft.Divider(),
                    ft.Text(
                        "Шаг 1 — Загрузите поля проекта",
                        size=13, weight=ft.FontWeight.W_500, color=ft.Colors.GREY_700,
                    ),
                    ft.Row(
                        controls=[
                            ft.Column(
                                controls=[
                                    ft.Text("Код проекта", size=13, color=ft.Colors.GREY_700),
                                    project_ac,
                                ],
                                spacing=4,
                                width=200,
                            ),
                            self._load_btn,
                            self._load_status,
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=12,
                    ),
                    ft.Divider(height=1),
                    ft.Text(
                        "Шаг 2 — Укажите изменения",
                        size=13, weight=ft.FontWeight.W_500, color=ft.Colors.GREY_700,
                    ),
                    extra_fields_col,
                    add_field_row_cont,
                    ft.Divider(height=1),
                    ft.Text(
                        "Шаг 3 — Список задач",
                        size=13, weight=ft.FontWeight.W_500, color=ft.Colors.GREY_700,
                    ),
                    self._targets_field,
                    ft.Row(controls=[self._apply_btn]),
                    self._results_col,
                ],
                spacing=14,
                scroll=ft.ScrollMode.AUTO,
                expand=True,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
        )

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_project_key_change(self, e: ft.ControlEvent) -> None:
        raw = e.control.value if hasattr(e, "control") else ""
        self._last_project_key = (raw or "").strip().upper()

    def _on_project_key_selected(self, e: ft.AutoCompleteSelectEvent) -> None:
        self._last_project_key = e.selection.value.strip().upper()

    def _update_apply_btn(self, e: ft.ControlEvent | None = None) -> None:
        if self._apply_btn is None:
            return
        has_fields = bool(self._extra_fields)
        has_targets = bool((self._targets_field.value or "").strip()) if self._targets_field else False
        self._apply_btn.disabled = not (has_fields and has_targets)
        self._apply_btn.update()

    # ------------------------------------------------------------------
    # Load project fields
    # ------------------------------------------------------------------

    async def _do_fetch_meta(self) -> None:
        proj_key = self._last_project_key
        if not proj_key:
            error_snack(self.page, "Введите код проекта")
            return
        settings = load_settings()
        if not settings.jira_url or not settings.jira_token:
            error_snack(self.page, "Настройте подключение к Jira в разделе «Настройки»")
            return

        if self._load_btn:
            self._load_btn.disabled = True
            self._load_btn.update()
        if self._load_status:
            self._load_status.value = "Загрузка..."
            self._load_status.color = ft.Colors.GREY_600
            self._load_status.update()

        try:
            meta = await get_project_meta(settings.jira_url, settings.jira_token, proj_key)
        except Exception as exc:
            log.exception("Failed to fetch project meta for %s", proj_key)
            if self._load_status:
                self._load_status.value = f"Ошибка: {exc}"
                self._load_status.color = ft.Colors.RED_400
                self._load_status.update()
            if self._load_btn:
                self._load_btn.disabled = False
                self._load_btn.update()
            return

        self._jira_fields.clear()
        self._jira_fields.extend(meta["fields"])

        # Clear field selections when meta is reloaded
        self._extra_fields.clear()
        self._add_row_state[0] = {"field_id": None, "multi_ids": [], "loading": False}

        # Rebuild extra-fields UI via stored closures
        if self._rebuild_field_rows and self._extra_fields_column is not None:
            self._extra_fields_column.controls = self._rebuild_field_rows()
            self._extra_fields_column.update()
        if self._rebuild_add_row and self._add_field_row_container is not None:
            self._add_field_row_container.content = self._rebuild_add_row()

        self._update_apply_btn()

        if self._load_status:
            self._load_status.value = f"Загружено {len(self._jira_fields)} полей"
            self._load_status.color = ft.Colors.GREEN_700
            self._load_status.update()
        if self._load_btn:
            self._load_btn.content = "Обновить поля из Jira"
            self._load_btn.icon = ft.Icons.CLOUD_SYNC
            self._load_btn.disabled = False
            self._load_btn.update()

        self.page.update()

    # ------------------------------------------------------------------
    # Apply changes
    # ------------------------------------------------------------------

    async def _do_apply(self) -> None:
        settings = load_settings()
        if not settings.jira_url or not settings.jira_token:
            error_snack(self.page, "Настройте подключение к Jira в разделе «Настройки»")
            return

        if not self._extra_fields:
            error_snack(self.page, "Укажите хотя бы одно изменение")
            return

        targets = _parse_issues(self._targets_field.value or "", self._last_project_key)
        if not targets:
            error_snack(self.page, "Укажите список задач")
            return

        if self._apply_btn:
            self._apply_btn.disabled = True
            self._apply_btn.update()
        if self._results_col:
            self._results_col.controls = []
            self._results_col.update()

        for issue_key in targets:
            pending_row = ft.Row(
                controls=[
                    ft.ProgressRing(width=16, height=16, stroke_width=2),
                    ft.Text(issue_key, size=13),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
            if self._results_col:
                self._results_col.controls.append(pending_row)
                self._results_col.update()

            try:
                await update_jira_issue(
                    settings.jira_url, settings.jira_token,
                    issue_key, self._extra_fields,
                )
                pending_row.controls = [
                    ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE, color=ft.Colors.GREEN_600, size=18),
                    ft.Text(issue_key, size=13),
                ]
            except Exception as exc:
                log.exception("Failed to update %s", issue_key)
                pending_row.controls = [
                    ft.Icon(ft.Icons.ERROR_OUTLINE, color=ft.Colors.RED_400, size=18),
                    ft.Text(f"{issue_key}: {exc}", size=13, color=ft.Colors.RED_400),
                ]

            if self._results_col:
                self._results_col.update()

        if self._apply_btn:
            self._apply_btn.disabled = False
            self._apply_btn.update()

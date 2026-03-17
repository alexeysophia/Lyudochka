import logging
import re

import flet as ft

from core.jira_client import create_issue_link, get_link_types
from data.settings_store import load_settings, save_settings
from data.teams_store import load_all_teams
from ui.snack import error_snack

log = logging.getLogger(__name__)

# Matches a Jira issue key: PROJECT-123
_KEY_RE = re.compile(r"\b([A-Z][A-Z0-9_]*-\d+)\b")
# Matches a Jira browse URL: .../browse/PROJ-123
_URL_RE = re.compile(r"/browse/([A-Z][A-Z0-9_]*-\d+)", re.IGNORECASE)


def _extract_issue_key(raw: str, project_key: str) -> str | None:
    """Extract a Jira issue key from a URL, plain key, or plain number.

    Returns None if the input is empty after stripping.
    """
    raw = raw.strip()
    if not raw:
        return None
    # Try to extract from URL first
    m = _URL_RE.search(raw)
    if m:
        return m.group(1).upper()
    # Plain key  (PROJ-123)
    m = _KEY_RE.fullmatch(raw.upper())
    if m:
        return m.group(1)
    # Plain number — prefix with project key
    if raw.isdigit() and project_key:
        return f"{project_key}-{raw}"
    # Fallback: return as-is (will fail on Jira if wrong)
    return raw.upper()


def _parse_issues(text: str, project_key: str) -> list[str]:
    """Split comma/newline-separated input and extract a key from each part."""
    parts = [p.strip() for p in re.split(r"[,\n]+", text)]
    result: list[str] = []
    for part in parts:
        key = _extract_issue_key(part, project_key)
        if key:
            result.append(key)
    return result


class LinksScreen:
    def __init__(self, page: ft.Page) -> None:
        self.page = page
        # Preserved across build() calls
        self._link_type_options: list[dict] = []  # [{id, label, is_outward, type_name}]
        self._last_project_key: str = ""
        self._selected_opt_idx: int | None = None  # index into _link_type_options

        # UI refs (recreated each build)
        self._project_key_field: ft.TextField | None = None
        self._load_btn: ft.ElevatedButton | None = None
        self._load_status: ft.Text | None = None
        self._autocomplete: ft.AutoComplete | None = None
        self._selected_label: ft.Text | None = None
        self._source_field: ft.TextField | None = None
        self._targets_field: ft.TextField | None = None
        self._link_btn: ft.ElevatedButton | None = None
        self._results_col: ft.Column | None = None

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def build(self) -> ft.Control:
        self._selected_opt_idx = None

        # Load cached link types from settings if not already in memory
        if not self._link_type_options:
            cached = load_settings().jira_link_types
            if cached:
                self._link_type_options = self._build_options(cached)

        # Project key suggestions from known teams
        team_keys = sorted({t.jira_project for t in load_all_teams() if t.jira_project})

        project_ac = ft.AutoComplete(
            value=self._last_project_key,
            suggestions=[ft.AutoCompleteSuggestion(key=k, value=k) for k in team_keys],
            suggestions_max_height=200,
            on_select=self._on_project_key_selected,
            on_change=self._on_project_key_change,
        )

        self._project_key_field = ft.TextField(
            label="Код проекта",
            hint_text="Например: BACKEND",
            value=self._last_project_key,
            width=200,
            on_change=self._on_project_key_change,
            on_submit=lambda e: self.page.run_task(self._load_link_types),
            visible=False,
        )

        self._load_btn = ft.ElevatedButton(
            "Загрузить типы связей",
            icon=ft.Icons.REFRESH,
            on_click=lambda e: self.page.run_task(self._load_link_types),
        )

        n_types = len(self._link_type_options) // 2
        self._load_status = ft.Text(
            f"Загружено {n_types} типов (из кэша)" if n_types else "",
            size=13,
            color=ft.Colors.GREY_600,
        )

        suggestions = [
            ft.AutoCompleteSuggestion(key=opt["label"], value=opt["label"])
            for opt in self._link_type_options
        ]
        self._autocomplete = ft.AutoComplete(
            suggestions=suggestions,
            suggestions_max_height=300,
            on_select=self._on_link_type_selected,
            on_change=self._on_autocomplete_change,
        )

        self._selected_label = ft.Text(
            "", size=12, color=ft.Colors.GREY_600, italic=True,
        )

        self._source_field = ft.TextField(
            label="Задача-источник",
            hint_text="Ключ (PROJ-123), номер (123) или ссылка из Jira",
            expand=True,
            on_change=self._update_link_btn,
        )

        self._targets_field = ft.TextField(
            label="Связать с задачами",
            hint_text="Ключи, номера или ссылки — через запятую или с новой строки",
            multiline=True,
            min_lines=4,
            max_lines=10,
            expand=True,
            on_change=self._update_link_btn,
        )

        self._link_btn = ft.ElevatedButton(
            "Связать задачи",
            icon=ft.Icons.LINK,
            on_click=lambda e: self.page.run_task(self._do_link),
            disabled=True,
            width=200,
        )

        self._results_col = ft.Column(controls=[], spacing=6)

        return ft.Container(
            padding=30,
            expand=True,
            content=ft.Column(
                controls=[
                    ft.Text("Связи между задачами", size=24, weight=ft.FontWeight.BOLD),
                    ft.Divider(),
                    # Step 1
                    ft.Text("Шаг 1 — Загрузите типы связей",
                            size=13, weight=ft.FontWeight.W_500, color=ft.Colors.GREY_700),
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
                    # Step 2
                    ft.Text("Шаг 2 — Укажите параметры связи",
                            size=13, weight=ft.FontWeight.W_500, color=ft.Colors.GREY_700),
                    ft.Column(
                        controls=[
                            ft.Text("Тип связи", size=13, color=ft.Colors.GREY_700),
                            self._autocomplete,
                            self._selected_label,
                        ],
                        spacing=4,
                    ),
                    self._source_field,
                    self._targets_field,
                    ft.Row(controls=[self._link_btn]),
                    self._results_col,
                ],
                spacing=14,
                scroll=ft.ScrollMode.AUTO,
                expand=True,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_options(raw_types: list[dict]) -> list[dict]:
        """Build flat option list (both directions) from raw link type dicts."""
        opts: list[dict] = []
        for lt in raw_types:
            opts.append({"id": lt["id"], "type_name": lt["name"],
                         "label": lt["outward"], "is_outward": True})
            opts.append({"id": lt["id"], "type_name": lt["name"],
                         "label": lt["inward"], "is_outward": False})
        return opts

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_project_key_change(self, e: ft.ControlEvent) -> None:
        raw = e.control.value if hasattr(e, "control") else ""
        self._last_project_key = (raw or "").strip().upper()

    def _on_project_key_selected(self, e: ft.AutoCompleteSelectEvent) -> None:
        self._last_project_key = e.selection.value.strip().upper()

    def _on_autocomplete_change(self, e: ft.ControlEvent) -> None:
        # User is typing — clear current selection until they pick again
        self._selected_opt_idx = None
        if self._selected_label:
            self._selected_label.value = ""
            self._selected_label.update()
        self._update_link_btn()

    def _on_link_type_selected(self, e: ft.AutoCompleteSelectEvent) -> None:
        self._selected_opt_idx = e.index
        opt = self._link_type_options[e.index]
        if self._selected_label:
            self._selected_label.value = f"[{opt['type_name']}]  «{opt['label']}»"
            self._selected_label.update()
        self._update_link_btn()

    def _update_link_btn(self, e: ft.ControlEvent | None = None) -> None:
        if self._link_btn is None:
            return
        has_type = self._selected_opt_idx is not None
        has_source = bool((self._source_field.value or "").strip()) if self._source_field else False
        has_targets = bool((self._targets_field.value or "").strip()) if self._targets_field else False
        self._link_btn.disabled = not (has_type and has_source and has_targets)
        self._link_btn.update()

    # ------------------------------------------------------------------
    # Load link types
    # ------------------------------------------------------------------

    async def _load_link_types(self) -> None:
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
            raw_types = await get_link_types(settings.jira_url, settings.jira_token)
        except Exception as exc:
            log.exception("Failed to load link types")
            if self._load_status:
                self._load_status.value = f"Ошибка: {exc}"
                self._load_status.color = ft.Colors.RED_400
                self._load_status.update()
            if self._load_btn:
                self._load_btn.disabled = False
                self._load_btn.update()
            return

        self._link_type_options = self._build_options(raw_types)

        # Persist to settings so other screens and future sessions can use them
        try:
            s = load_settings()
            s.jira_link_types = raw_types
            save_settings(s)
        except Exception:
            pass

        self._selected_opt_idx = None
        if self._autocomplete:
            self._autocomplete.suggestions = [
                ft.AutoCompleteSuggestion(key=opt["label"], value=opt["label"])
                for opt in self._link_type_options
            ]
            self._autocomplete.value = ""
            self._autocomplete.update()
        if self._selected_label:
            self._selected_label.value = ""
            self._selected_label.update()

        if self._load_status:
            self._load_status.value = f"Загружено {len(raw_types)} типов"
            self._load_status.color = ft.Colors.GREEN_700
            self._load_status.update()
        if self._load_btn:
            self._load_btn.disabled = False
            self._load_btn.update()

        self._update_link_btn()

    # ------------------------------------------------------------------
    # Create links
    # ------------------------------------------------------------------

    async def _do_link(self) -> None:
        settings = load_settings()
        if not settings.jira_url or not settings.jira_token:
            error_snack(self.page, "Настройте подключение к Jira в разделе «Настройки»")
            return

        if self._selected_opt_idx is None:
            error_snack(self.page, "Выберите тип связи из списка")
            return

        opt = self._link_type_options[self._selected_opt_idx]
        link_type_id: str = opt["id"]
        is_outward: bool = opt["is_outward"]
        link_label: str = opt["label"]

        source_raw = (self._source_field.value or "").strip()
        source = _extract_issue_key(source_raw, self._last_project_key)
        if not source:
            error_snack(self.page, "Укажите задачу-источник")
            return

        targets = _parse_issues(self._targets_field.value or "", self._last_project_key)
        if not targets:
            error_snack(self.page, "Укажите задачи для связи")
            return

        if self._link_btn:
            self._link_btn.disabled = True
            self._link_btn.update()
        if self._results_col:
            self._results_col.controls = []
            self._results_col.update()

        for target in targets:
            outward = source if is_outward else target
            inward = target if is_outward else source
            label_text = f"{source}  {link_label}  {target}"

            pending_row = ft.Row(
                controls=[
                    ft.ProgressRing(width=16, height=16, stroke_width=2),
                    ft.Text(label_text, size=13),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
            if self._results_col:
                self._results_col.controls.append(pending_row)
                self._results_col.update()

            try:
                await create_issue_link(
                    settings.jira_url, settings.jira_token,
                    link_type_id, outward, inward,
                )
                pending_row.controls = [
                    ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE,
                            color=ft.Colors.GREEN_600, size=18),
                    ft.Text(label_text, size=13),
                ]
            except Exception as exc:
                log.exception("Failed to link %s → %s", source, target)
                pending_row.controls = [
                    ft.Icon(ft.Icons.ERROR_OUTLINE, color=ft.Colors.RED_400, size=18),
                    ft.Text(f"{label_text}: {exc}", size=13, color=ft.Colors.RED_400),
                ]

            if self._results_col:
                self._results_col.update()

        if self._link_btn:
            self._link_btn.disabled = False
            self._link_btn.update()

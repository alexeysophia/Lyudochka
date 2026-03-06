import logging
import subprocess

import flet as ft

from core.jira_client import create_jira_issue
from data.models import AIResponse
from data.settings_store import load_settings
from ui.snack import error_snack

log = logging.getLogger(__name__)


def _copy_to_clipboard(text: str) -> None:
    proc = subprocess.Popen(
        "clip",
        stdin=subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    proc.communicate(input=text.encode("utf-16"))


class ResultCard:
    def __init__(self, page: ft.Page, response: AIResponse) -> None:
        self.page = page
        self.response = response
        self._task_text = response.task_text
        self._labels: list[str] = list(response.jira_params.get("labels", []))
        self._edit_mode = False
        self._saved_sel: list[int] = [0, 0]
        self._text_container: ft.Container | None = None
        self._edit_field: ft.TextField | None = None
        self._edit_btn: ft.IconButton | None = None
        self._jira_btn: ft.ElevatedButton | None = None
        self._jira_action_row: ft.Row | None = None
        self._tags_row: ft.Row | None = None
        self._new_label_field: ft.TextField | None = None

    # ------------------------------------------------------------------
    # Formatting helpers
    # ------------------------------------------------------------------

    def _on_selection_change(self, e: ft.TextSelectionChangeEvent) -> None:
        if e.selection.base_offset is not None:
            self._saved_sel[0] = min(
                e.selection.base_offset,
                e.selection.extent_offset or e.selection.base_offset,
            )
            self._saved_sel[1] = max(
                e.selection.base_offset,
                e.selection.extent_offset or e.selection.base_offset,
            )

    def _apply_format(self, prefix: str, suffix: str) -> None:
        field = self._edit_field
        if field is None:
            return
        value = field.value or ""
        start = min(self._saved_sel[0], len(value))
        end = min(self._saved_sel[1], len(value))
        field.value = value[:start] + prefix + value[start:end] + suffix + value[end:]
        self._saved_sel[0] = self._saved_sel[1] = (
            start + len(prefix) + (end - start) + len(suffix)
        )
        field.update()
        self.page.run_task(field.focus)

    def _build_formatting_toolbar(self) -> ft.Row:
        af = self._apply_format
        return ft.Row(
            controls=[
                ft.IconButton(
                    icon=ft.Icons.FORMAT_BOLD,
                    tooltip="Жирный (**текст**)",
                    on_click=lambda e: af("**", "**"),
                    icon_size=18,
                    style=ft.ButtonStyle(padding=ft.padding.all(4)),
                ),
                ft.IconButton(
                    icon=ft.Icons.FORMAT_ITALIC,
                    tooltip="Курсив (*текст*)",
                    on_click=lambda e: af("*", "*"),
                    icon_size=18,
                    style=ft.ButtonStyle(padding=ft.padding.all(4)),
                ),
                ft.IconButton(
                    icon=ft.Icons.CODE,
                    tooltip="Код (`текст`)",
                    on_click=lambda e: af("`", "`"),
                    icon_size=18,
                    style=ft.ButtonStyle(padding=ft.padding.all(4)),
                ),
                ft.IconButton(
                    icon=ft.Icons.FORMAT_UNDERLINED,
                    tooltip="Подчёркнутый (<u>текст</u>)",
                    on_click=lambda e: af("<u>", "</u>"),
                    icon_size=18,
                    style=ft.ButtonStyle(padding=ft.padding.all(4)),
                ),
                ft.IconButton(
                    icon=ft.Icons.FORMAT_STRIKETHROUGH,
                    tooltip="Зачёркнутый (~~текст~~)",
                    on_click=lambda e: af("~~", "~~"),
                    icon_size=18,
                    style=ft.ButtonStyle(padding=ft.padding.all(4)),
                ),
                ft.IconButton(
                    icon=ft.Icons.FORMAT_LIST_BULLETED,
                    tooltip="Список (- пункт)",
                    on_click=lambda e: af("\n- ", ""),
                    icon_size=18,
                    style=ft.ButtonStyle(padding=ft.padding.all(4)),
                ),
                ft.VerticalDivider(width=12),
                ft.Text("Markdown", size=11, color=ft.Colors.GREY_500, italic=True),
            ],
            spacing=0,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def build(self) -> ft.Control:
        jira = self.response.jira_params

        async def copy_clicked(e: ft.ControlEvent) -> None:
            copy_text = f"{self.response.task_title}\n\n{self._task_text}"
            _copy_to_clipboard(copy_text)
            snack = ft.SnackBar(
                content=ft.Text("Скопировано в буфер обмена"), open=True
            )
            self.page.overlay.append(snack)
            self.page.update()

        self._edit_btn = ft.IconButton(
            icon=ft.Icons.EDIT_OUTLINED,
            tooltip="Редактировать",
            on_click=self._toggle_edit,
        )

        in_jira = bool(self.response.jira_issue_key)
        header_icon = ft.Icons.TASK_ALT if in_jira else ft.Icons.CHECK_CIRCLE_OUTLINE
        header_color = ft.Colors.TEAL_700 if in_jira else ft.Colors.GREEN
        header_text = "Задача в Jira" if in_jira else "Задача готова"

        controls: list[ft.Control] = [
            ft.Row(
                controls=[
                    ft.Icon(header_icon, color=header_color),
                    ft.Text(
                        header_text,
                        size=16,
                        weight=ft.FontWeight.BOLD,
                        color=header_color,
                    ),
                    ft.Container(expand=True),
                    ft.IconButton(
                        icon=ft.Icons.COPY,
                        tooltip="Скопировать всё",
                        on_click=copy_clicked,
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            ft.Divider(),
        ]

        if self.response.task_title:
            controls += [
                ft.Text("Название задачи", size=11, color=ft.Colors.GREY_600),
                ft.Container(
                    padding=ft.padding.symmetric(vertical=8, horizontal=12),
                    bgcolor=ft.Colors.SURFACE_CONTAINER,
                    border_radius=8,
                    content=ft.Text(
                        self.response.task_title,
                        size=15,
                        weight=ft.FontWeight.W_500,
                        selectable=True,
                    ),
                ),
            ]

        if self._task_text:
            self._text_container = ft.Container(
                padding=12,
                bgcolor=ft.Colors.SURFACE_CONTAINER,
                border_radius=8,
                content=self._build_text_content(),
            )
            desc_row_controls: list[ft.Control] = [
                ft.Text("Описание задачи", size=11, color=ft.Colors.GREY_600),
                ft.Container(expand=True),
            ]
            if not in_jira:
                desc_row_controls.append(self._edit_btn)
            controls += [
                ft.Row(
                    controls=desc_row_controls,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                self._text_container,
            ]

        jira_chips: list[ft.Control] = []
        if jira.get("project"):
            jira_chips.append(ft.Chip(label=ft.Text(f"Проект: {jira['project']}")))
        if jira.get("type"):
            jira_chips.append(ft.Chip(label=ft.Text(f"Тип: {jira['type']}")))
        for field_key, field_val in (jira.get("extra_fields") or {}).items():
            jira_chips.append(ft.Chip(label=ft.Text(f"{field_key}: {field_val}")))

        if jira_chips:
            controls += [
                ft.Text("Параметры Jira", size=11, color=ft.Colors.GREY_600),
                ft.Row(controls=jira_chips, wrap=True),
            ]

        self._new_label_field = ft.TextField(
            hint_text="Новый тег",
            dense=True,
            width=180,
            on_submit=self._add_label,
        )
        self._tags_row = self._build_tags_row()
        controls += [
            ft.Text("Теги", size=11, color=ft.Colors.GREY_600),
            self._tags_row,
            ft.Row(
                controls=[
                    self._new_label_field,
                    ft.IconButton(
                        icon=ft.Icons.ADD,
                        tooltip="Добавить тег",
                        on_click=self._add_label,
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=4,
            ),
        ]

        settings = load_settings()
        self._jira_action_row = ft.Row(controls=[])
        if self.response.jira_issue_key:
            issue_url = f"{settings.jira_url.rstrip('/')}/browse/{self.response.jira_issue_key}"
            self._jira_action_row.controls = [
                ft.TextButton(
                    f"Открыть {self.response.jira_issue_key} в Jira",
                    icon=ft.Icons.OPEN_IN_NEW,
                    url=issue_url,
                )
            ]
        else:
            jira_configured = bool(settings.jira_url and settings.jira_token)
            self._jira_btn = ft.ElevatedButton(
                "Создать в Jira",
                icon=ft.Icons.ADD_TASK,
                disabled=not jira_configured,
                tooltip=None if jira_configured else "Настройте Jira в разделе Настройки",
                on_click=lambda e: self.page.run_task(self._create_in_jira),
            )
            self._jira_action_row.controls = [self._jira_btn]
        controls += [
            ft.Divider(),
            self._jira_action_row,
        ]

        return ft.Container(
            padding=16,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=12,
            content=ft.Column(controls=controls, spacing=10),
        )

    def _build_text_content(self) -> ft.Control:
        if self._edit_mode:
            self._edit_field = ft.TextField(
                value=self._task_text,
                multiline=True,
                min_lines=6,
                border=ft.InputBorder.NONE,
                expand=True,
            )
            self._edit_field.on_selection_change = self._on_selection_change
            self._saved_sel = [0, 0]
            return ft.Column(
                controls=[
                    self._build_formatting_toolbar(),
                    ft.Divider(height=1, color="#C3C7CF"),
                    self._edit_field,
                ],
                spacing=4,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            )
        else:
            self._edit_field = None
            return ft.Markdown(
                value=self._task_text,
                selectable=True,
                extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                soft_line_break=True,
                expand=True,
            )

    def _build_tags_row(self) -> ft.Row:
        chips: list[ft.Control] = [
            ft.Chip(
                label=ft.Text(lbl),
                on_delete=lambda e, l=lbl: self._remove_label(l),
            )
            for lbl in self._labels
        ]
        if not chips:
            chips = [ft.Text("Нет тегов", size=12, color=ft.Colors.GREY_400, italic=True)]
        if self._tags_row is None:
            return ft.Row(controls=chips, wrap=True)
        self._tags_row.controls = chips
        self._tags_row.update()
        return self._tags_row

    def _remove_label(self, label: str) -> None:
        if label in self._labels:
            self._labels.remove(label)
            self.response.jira_params["labels"] = self._labels
            self._build_tags_row()

    def _add_label(self, e: ft.ControlEvent) -> None:
        if self._new_label_field is None:
            return
        value = (self._new_label_field.value or "").strip()
        if value and value not in self._labels:
            self._labels.append(value)
            self.response.jira_params["labels"] = self._labels
            self._new_label_field.value = ""
            self._new_label_field.update()
            self._build_tags_row()

    def _toggle_edit(self, e: ft.ControlEvent) -> None:
        if self._edit_mode:
            if self._edit_field is not None:
                self._task_text = self._edit_field.value or self._task_text
            self._edit_mode = False
            self._edit_btn.icon = ft.Icons.EDIT_OUTLINED
            self._edit_btn.tooltip = "Редактировать"
        else:
            self._edit_mode = True
            self._edit_btn.icon = ft.Icons.CHECK
            self._edit_btn.tooltip = "Сохранить изменения"

        if self._text_container is not None:
            self._text_container.content = self._build_text_content()
            self._text_container.update()
        self._edit_btn.update()

    async def _create_in_jira(self) -> None:
        if self._jira_btn is None or self._jira_action_row is None:
            return

        self._jira_btn.disabled = True
        self._jira_btn.content = "Создаю задачу..."
        self._jira_btn.update()

        settings = load_settings()
        jira_params = self.response.jira_params
        try:
            key = await create_jira_issue(
                jira_url=settings.jira_url,
                token=settings.jira_token,
                project_key=jira_params.get("project", ""),
                summary=self.response.task_title,
                description=self._task_text,
                issue_type=jira_params.get("type", "Story"),
                issue_type_id=jira_params.get("type_id", ""),
                labels=jira_params.get("labels", []),
                extra_fields=jira_params.get("extra_fields"),
            )
        except Exception as exc:
            log.exception("Jira issue creation failed")
            self._jira_btn.disabled = False
            self._jira_btn.content = "Создать в Jira"
            self._jira_btn.update()
            error_snack(self.page, f"Ошибка Jira: {exc}")
            return

        self.response.jira_issue_key = key
        issue_url = f"{settings.jira_url.rstrip('/')}/browse/{key}"
        open_btn = ft.TextButton(
            f"Открыть {key} в Jira",
            icon=ft.Icons.OPEN_IN_NEW,
            url=issue_url,
        )
        self._jira_action_row.controls = [open_btn]
        self._jira_action_row.update()

        snack = ft.SnackBar(
            content=ft.Text(f"Задача {key} создана в Jira"), open=True
        )
        self.page.overlay.append(snack)
        self.page.update()

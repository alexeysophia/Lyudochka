import subprocess

import flet as ft


def _copy_to_clipboard(text: str) -> None:
    proc = subprocess.Popen(
        "clip",
        stdin=subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    proc.communicate(input=text.encode("utf-16"))

from data.models import AIResponse


class ResultCard:
    def __init__(self, page: ft.Page, response: AIResponse) -> None:
        self.page = page
        self.response = response
        self._task_text = response.task_text
        self._edit_mode = False
        self._saved_sel: list[int] = [0, 0]
        self._text_container: ft.Container | None = None
        self._edit_field: ft.TextField | None = None
        self._edit_btn: ft.IconButton | None = None

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

        controls: list[ft.Control] = [
            ft.Row(
                controls=[
                    ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE, color=ft.Colors.GREEN),
                    ft.Text(
                        "Задача готова",
                        size=16,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.GREEN,
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
            controls += [
                ft.Row(
                    controls=[
                        ft.Text(
                            "Описание задачи", size=11, color=ft.Colors.GREY_600
                        ),
                        ft.Container(expand=True),
                        self._edit_btn,
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                self._text_container,
            ]

        jira_chips: list[ft.Control] = []
        if jira.get("project"):
            jira_chips.append(ft.Chip(label=ft.Text(f"Проект: {jira['project']}")))
        if jira.get("type"):
            jira_chips.append(ft.Chip(label=ft.Text(f"Тип: {jira['type']}")))
        if jira.get("priority"):
            jira_chips.append(ft.Chip(label=ft.Text(f"Приоритет: {jira['priority']}")))
        for lbl in jira.get("labels", []):
            jira_chips.append(ft.Chip(label=ft.Text(str(lbl))))

        if jira_chips:
            controls += [
                ft.Text("Параметры Jira", size=11, color=ft.Colors.GREY_600),
                ft.Row(controls=jira_chips, wrap=True),
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

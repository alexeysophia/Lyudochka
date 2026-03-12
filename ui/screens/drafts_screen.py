from datetime import datetime
from typing import Callable

import flet as ft

from data.drafts_store import delete_draft, load_all_drafts
from data.models import Draft

_STAGE_LABELS: dict[str, tuple[str, str]] = {
    "input": ("Ввод", ft.Colors.GREY_600),
    "clarification": ("Уточнение", ft.Colors.BLUE_600),
    "ready": ("Готово", ft.Colors.GREEN_600),
}


class DraftsScreen:
    def __init__(
        self,
        page: ft.Page,
        on_restore: Callable[[Draft], None],
    ) -> None:
        self.page = page
        self._on_restore = on_restore
        self._container: ft.Container | None = None
        self._all_drafts: list[Draft] = []
        self._drafts_list_column: ft.Column | None = None
        self._filter_value: str = "Все команды"
        self._stage_filter: str = "Все статусы"

    def build(self) -> ft.Control:
        self._filter_value = "Все команды"
        self._stage_filter = "Все статусы"
        self._container = ft.Container(
            padding=30,
            content=self._build_content(),
            expand=True,
        )
        return self._container

    def _build_content(self) -> ft.Control:
        self._all_drafts = load_all_drafts()

        team_names = sorted({d.team_name for d in self._all_drafts if d.team_name})
        dropdown_options = [ft.dropdown.Option("Все команды")] + [
            ft.dropdown.Option(name) for name in team_names
        ]
        filter_dropdown = ft.Dropdown(
            options=dropdown_options,
            value=self._filter_value,
            width=200,
            content_padding=ft.padding.symmetric(horizontal=10, vertical=6),
            on_select=self._on_filter_change,
        )

        stage_options = [ft.dropdown.Option("Все статусы")] + [
            ft.dropdown.Option(key, label)
            for key, (label, _) in _STAGE_LABELS.items()
        ] + [ft.dropdown.Option("jira", "В Jira")]
        stage_dropdown = ft.Dropdown(
            options=stage_options,
            value=self._stage_filter,
            width=170,
            content_padding=ft.padding.symmetric(horizontal=10, vertical=6),
            on_select=self._on_stage_filter_change,
        )

        header = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Text("Сохраненные задачи", size=24, weight=ft.FontWeight.BOLD),
                        ft.Container(expand=True),
                        stage_dropdown,
                        filter_dropdown,
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Divider(),
            ],
            spacing=8,
        )

        if not self._all_drafts:
            return ft.Column(
                controls=[
                    header,
                    ft.Container(
                        padding=ft.padding.only(top=40),
                        content=ft.Column(
                            controls=[
                                ft.Icon(
                                    ft.Icons.BOOKMARK_BORDER,
                                    size=48,
                                    color=ft.Colors.GREY_400,
                                ),
                                ft.Text(
                                    "Нет сохранённых черновиков",
                                    color=ft.Colors.GREY_500,
                                    size=16,
                                ),
                            ],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=12,
                        ),
                    ),
                ],
                spacing=0,
                expand=True,
            )

        filtered = self._filtered_drafts()
        self._drafts_list_column = ft.Column(
            controls=[self._build_draft_card(d) for d in filtered],
            spacing=12,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

        return ft.Column(
            controls=[
                header,
                self._drafts_list_column,
            ],
            spacing=0,
            expand=True,
        )

    def _filtered_drafts(self) -> list[Draft]:
        result = self._all_drafts
        if self._filter_value != "Все команды":
            result = [d for d in result if d.team_name == self._filter_value]
        if self._stage_filter != "Все статусы":
            if self._stage_filter == "jira":
                result = [
                    d for d in result
                    if d.ai_response and d.ai_response.jira_issue_key
                ]
            else:
                result = [
                    d for d in result
                    if d.stage == self._stage_filter
                    and not (d.ai_response and d.ai_response.jira_issue_key)
                ]
        return result

    def _on_filter_change(self, e: ft.ControlEvent) -> None:
        self._filter_value = e.control.value or "Все команды"
        if self._drafts_list_column is not None:
            self._drafts_list_column.controls = [self._build_draft_card(d) for d in self._filtered_drafts()]
            self.page.update()

    def _on_stage_filter_change(self, e: ft.ControlEvent) -> None:
        self._stage_filter = e.control.value or "Все статусы"
        if self._drafts_list_column is not None:
            self._drafts_list_column.controls = [self._build_draft_card(d) for d in self._filtered_drafts()]
            self.page.update()

    def _build_draft_card(self, draft: Draft) -> ft.Control:
        jira_key = (
            draft.ai_response.jira_issue_key
            if draft.ai_response and draft.ai_response.jira_issue_key
            else ""
        )
        if jira_key:
            stage_label, stage_color = "В Jira", ft.Colors.TEAL_700
        else:
            stage_label, stage_color = _STAGE_LABELS.get(
                draft.stage, ("Неизвестно", ft.Colors.GREY_600)
            )

        try:
            dt = datetime.fromisoformat(draft.created_at)
            created_str = dt.strftime("%d.%m.%Y %H:%M")
        except Exception:
            created_str = draft.created_at

        updated_str = ""
        if draft.updated_at:
            try:
                dt_upd = datetime.fromisoformat(draft.updated_at)
                updated_str = dt_upd.strftime("%d.%m.%Y %H:%M")
            except Exception:
                updated_str = draft.updated_at

        preview = draft.user_input[:120] + (
            "..." if len(draft.user_input) > 120 else ""
        )

        def on_restore_click(e: ft.ControlEvent, d: Draft = draft) -> None:
            self._on_restore(d)

        def on_delete_click(e: ft.ControlEvent, d: Draft = draft) -> None:
            delete_draft(d.id)
            if self._container is not None:
                self._container.content = self._build_content()
            self.page.update()

        return ft.Container(
            padding=16,
            border=ft.border.all(1, ft.Colors.GREY_300),
            border_radius=12,
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Text(
                                draft.team_name,
                                size=15,
                                weight=ft.FontWeight.W_600,
                            ),
                            ft.Container(
                                content=ft.Text(
                                    stage_label, size=12, color=ft.Colors.WHITE
                                ),
                                bgcolor=stage_color,
                                padding=ft.padding.symmetric(
                                    horizontal=8, vertical=3
                                ),
                                border_radius=10,
                            ),
                            *(
                                [ft.Text(jira_key, size=12, color=ft.Colors.TEAL_700, weight=ft.FontWeight.W_500)]
                                if jira_key else []
                            ),
                            ft.Text(
                                f"Создана: {created_str}", size=12, color=ft.Colors.GREY_500
                            ),
                            *(
                                [ft.Text(f"Изменена: {updated_str}", size=12, color=ft.Colors.GREY_500)]
                                if updated_str and updated_str != created_str else []
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=8,
                    ),
                    ft.Text(preview, size=13, color=ft.Colors.GREY_700),
                    ft.Row(
                        controls=[
                            ft.ElevatedButton(
                                "Продолжить",
                                icon=ft.Icons.PLAY_ARROW,
                                on_click=on_restore_click,
                            ),
                            ft.TextButton(
                                "Удалить",
                                icon=ft.Icons.DELETE_OUTLINE,
                                style=ft.ButtonStyle(color=ft.Colors.RED_400),
                                on_click=on_delete_click,
                            ),
                        ],
                        spacing=8,
                    ),
                ],
                spacing=8,
            ),
        )

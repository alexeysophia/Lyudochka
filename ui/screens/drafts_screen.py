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

    def build(self) -> ft.Control:
        self._container = ft.Container(
            padding=30,
            content=self._build_content(),
            expand=True,
        )
        return self._container

    def _build_content(self) -> ft.Control:
        drafts = load_all_drafts()

        header = ft.Column(
            controls=[
                ft.Text("Черновики", size=24, weight=ft.FontWeight.BOLD),
                ft.Divider(),
            ],
            spacing=8,
        )

        if not drafts:
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

        draft_cards = [self._build_draft_card(d) for d in drafts]

        return ft.Column(
            controls=[
                header,
                ft.Column(
                    controls=draft_cards,
                    spacing=12,
                    scroll=ft.ScrollMode.AUTO,
                    expand=True,
                ),
            ],
            spacing=0,
            expand=True,
        )

    def _build_draft_card(self, draft: Draft) -> ft.Control:
        stage_label, stage_color = _STAGE_LABELS.get(
            draft.stage, ("Неизвестно", ft.Colors.GREY_600)
        )

        try:
            dt = datetime.fromisoformat(draft.created_at)
            date_str = dt.strftime("%d.%m.%Y %H:%M")
        except Exception:
            date_str = draft.created_at

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
                            ft.Text(
                                date_str, size=12, color=ft.Colors.GREY_500
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

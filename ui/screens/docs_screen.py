import os

import flet as ft

_README_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "README.md")


class DocsScreen:
    def __init__(self, page: ft.Page) -> None:
        self.page = page

    def build(self) -> ft.Control:
        try:
            with open(_README_PATH, encoding="utf-8") as f:
                content = f.read()
        except OSError:
            content = "_Файл README.md не найден._"

        return ft.Container(
            padding=ft.padding.symmetric(horizontal=30, vertical=20),
            expand=True,
            content=ft.Column(
                controls=[
                    ft.Markdown(
                        value=content,
                        selectable=True,
                        extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                        soft_line_break=True,
                        expand=True,
                    ),
                ],
                scroll=ft.ScrollMode.AUTO,
                expand=True,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
        )

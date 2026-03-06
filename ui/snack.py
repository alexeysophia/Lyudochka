import subprocess

import flet as ft


def _copy_text(text: str) -> None:
    proc = subprocess.Popen(
        "clip",
        stdin=subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    proc.communicate(input=text.encode("utf-16"))


def error_snack(page: ft.Page, message: str) -> None:
    """Show a red SnackBar with a copy button."""
    snack = ft.SnackBar(
        content=ft.Row(
            controls=[
                ft.IconButton(
                    icon=ft.Icons.COPY,
                    icon_color=ft.Colors.WHITE,
                    icon_size=18,
                    on_click=lambda e: _copy_text(message),
                    style=ft.ButtonStyle(padding=ft.padding.all(4)),
                ),
                ft.Text(message, color=ft.Colors.WHITE, expand=True),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        bgcolor=ft.Colors.RED_700,
        duration=7000,
        open=True,
    )
    page.overlay.append(snack)
    page.update()

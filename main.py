import os

import flet as ft

from ui.app import AppShell

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _build_icon_ico() -> str:
    """Create app.ico from icon128.png (preserving RGBA transparency). Returns ICO path."""
    ico_path = os.path.join(_BASE_DIR, "icons", "app.ico")
    png_path = os.path.join(_BASE_DIR, "icons", "icon128.png")
    if not os.path.exists(ico_path) and os.path.exists(png_path):
        try:
            from PIL import Image  # noqa: PLC0415
            img = Image.open(png_path).convert("RGBA")
            img.save(
                ico_path,
                format="ICO",
                sizes=[(16, 16), (32, 32), (48, 48), (128, 128)],
            )
        except Exception:
            return png_path
    return ico_path if os.path.exists(ico_path) else png_path


def main(page: ft.Page) -> None:
    page.title = "Людочка — твой помощник заведения задач"
    page.theme_mode = ft.ThemeMode.SYSTEM
    page.window.width = 1000
    page.window.height = 700
    page.window.min_width = 800
    page.window.min_height = 580
    page.window.icon = _build_icon_ico()

    shell = AppShell(page)
    page.add(shell.build())


if __name__ == "__main__":
    ft.run(main)

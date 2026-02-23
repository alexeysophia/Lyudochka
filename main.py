import flet as ft

from ui.app import AppShell


def main(page: ft.Page) -> None:
    page.title = "Lyudochka — Создание задач Jira"
    page.theme_mode = ft.ThemeMode.SYSTEM
    page.window.width = 1000
    page.window.height = 700
    page.window.min_width = 800
    page.window.min_height = 580

    shell = AppShell(page)
    page.add(shell.build())


if __name__ == "__main__":
    ft.app(target=main)

import flet as ft

from data.models import AIResponse


class ResultCard:
    def __init__(self, page: ft.Page, response: AIResponse) -> None:
        self.page = page
        self.response = response

    def build(self) -> ft.Control:
        jira = self.response.jira_params
        copy_text = f"{self.response.task_title}\n\n{self.response.task_text}"

        async def copy_clicked(e: ft.ControlEvent) -> None:
            cb = ft.Clipboard()
            self.page.overlay.append(cb)
            self.page.update()
            await cb.set(copy_text)
            self.page.overlay.remove(cb)

            snack = ft.SnackBar(
                content=ft.Text("Скопировано в буфер обмена"),
                open=True,
            )
            self.page.overlay.append(snack)
            self.page.update()

        controls: list[ft.Control] = [
            ft.Row(
                controls=[
                    ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE, color=ft.Colors.GREEN),
                    ft.Text("Задача готова", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN),
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
                    bgcolor=ft.Colors.SURFACE_VARIANT,
                    border_radius=8,
                    content=ft.Text(
                        self.response.task_title,
                        size=15,
                        weight=ft.FontWeight.W_500,
                        selectable=True,
                    ),
                ),
            ]

        if self.response.task_text:
            controls += [
                ft.Text("Описание задачи", size=11, color=ft.Colors.GREY_600),
                ft.Container(
                    padding=12,
                    bgcolor=ft.Colors.SURFACE_VARIANT,
                    border_radius=8,
                    content=ft.Text(self.response.task_text, selectable=True),
                ),
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

from typing import Callable

import flet as ft


class QuestionsForm:
    def __init__(
        self,
        page: ft.Page,
        questions: list[str],
        on_submit: Callable[[list[tuple[str, str]]], None],
        initial_answers: list[str] | None = None,
    ) -> None:
        self.page = page
        self.questions = questions
        self.on_submit = on_submit
        self._initial_answers = initial_answers or []
        self._answer_fields: list[ft.TextField] = []
        self._submit_btn: ft.ElevatedButton | None = None
        self._submit_loading: ft.ProgressRing | None = None

    def get_current_answers(self) -> list[tuple[str, str]]:
        return [
            (self.questions[i], self._answer_fields[i].value or "")
            for i in range(len(self.questions))
        ]

    def build(self) -> ft.Control:
        self._answer_fields = []
        question_controls: list[ft.Control] = []

        for i, question in enumerate(self.questions):
            field = ft.TextField(
                hint_text="Введите ответ...",
                multiline=True,
                min_lines=3,
                max_lines=8,
                expand=True,
                align_label_with_hint=True,
                value=self._initial_answers[i] if i < len(self._initial_answers) else "",
            )
            self._answer_fields.append(field)
            question_controls.append(
                ft.Column(
                    controls=[
                        ft.Text(f"{i + 1}. {question}", size=14, weight=ft.FontWeight.W_500),
                        field,
                    ],
                    spacing=6,
                    horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                )
            )

        self._submit_btn = ft.ElevatedButton(
            "Отправить ответы",
            icon=ft.Icons.SEND,
            width=210,
        )
        self._submit_loading = ft.ProgressRing(visible=False, width=20, height=20, stroke_width=2)

        def submit_clicked(e: ft.ControlEvent) -> None:
            answers = [
                (self.questions[i], self._answer_fields[i].value or "")
                for i in range(len(self.questions))
            ]
            if not any(a.strip() for _, a in answers):
                snack = ft.SnackBar(
                    content=ft.Text("Нет данных для отправки", color=ft.Colors.WHITE),
                    bgcolor=ft.Colors.RED_700,
                    open=True,
                )
                self.page.overlay.append(snack)
                self.page.update()
                return
            if self._submit_btn is not None:
                self._submit_btn.disabled = True
                self._submit_btn.update()
            if self._submit_loading is not None:
                self._submit_loading.visible = True
                self._submit_loading.update()
            self.on_submit(answers)

        self._submit_btn.on_click = submit_clicked

        return ft.Container(
            padding=16,
            border=ft.border.all(1, ft.Colors.BLUE_200),
            border_radius=12,
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.HELP_OUTLINE, color=ft.Colors.BLUE_400),
                            ft.Text(
                                "Требуется уточнение",
                                size=16,
                                weight=ft.FontWeight.BOLD,
                                color=ft.Colors.BLUE_700,
                            ),
                        ],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Text(
                        "ИИ задал уточняющие вопросы. Ответьте на них и нажмите «Отправить»:",
                        color=ft.Colors.GREY_700,
                        size=13,
                    ),
                    ft.Divider(),
                    *question_controls,
                    ft.Row(
                        controls=[self._submit_btn, self._submit_loading],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=12,
                    ),
                ],
                spacing=12,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
        )

    def reset_submit(self) -> None:
        """Re-enable submit button and hide spinner after error or timeout."""
        if self._submit_btn is not None:
            self._submit_btn.disabled = False
            self._submit_btn.update()
        if self._submit_loading is not None:
            self._submit_loading.visible = False
            self._submit_loading.update()

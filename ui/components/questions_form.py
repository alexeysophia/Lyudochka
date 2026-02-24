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

        def submit_clicked(e: ft.ControlEvent) -> None:
            answers = [
                (self.questions[i], self._answer_fields[i].value or "")
                for i in range(len(self.questions))
            ]
            self.on_submit(answers)

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
                    ft.ElevatedButton(
                        "Отправить ответы",
                        icon=ft.Icons.SEND,
                        on_click=submit_clicked,
                    ),
                ],
                spacing=12,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
        )

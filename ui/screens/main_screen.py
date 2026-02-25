import uuid
from datetime import datetime

import flet as ft

from core.ai_router import generate
from data.drafts_store import save_draft
from data.models import AIResponse, Draft, Team
from data.settings_store import load_settings
from data.teams_store import load_all_teams
from ui.components.questions_form import QuestionsForm
from ui.components.result_card import ResultCard


class MainScreen:
    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self._teams: list[Team] = []
        self._selected_team: Team | None = None
        self._user_input_value: str = ""

        # Stage tracking for drafts
        self._stage: str = "input"
        self._current_questions: list[str] = []
        self._current_questions_form: QuestionsForm | None = None
        self._current_ai_response: AIResponse | None = None
        self._last_submitted_answers: list[list[str]] = []

        # Mutable UI refs (set in build / _build_content)
        self._container: ft.Container | None = None
        self._team_dropdown: ft.Dropdown | None = None
        self._user_input: ft.TextField | None = None
        self._generate_btn: ft.ElevatedButton | None = None
        self._back_btn: ft.TextButton | None = None
        self._save_draft_btn: ft.OutlinedButton | None = None
        self._loading: ft.ProgressRing | None = None
        self._error_text: ft.Text | None = None
        self._result_area: ft.Column | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build(self) -> ft.Control:
        self._teams = load_all_teams()
        self._selected_team = None
        self._stage = "input"
        self._current_questions = []
        self._current_questions_form = None
        self._current_ai_response = None
        self._container = ft.Container(
            padding=30,
            content=self._build_content(),
            expand=True,
        )
        return self._container

    def refresh_teams(self) -> None:
        """Reload teams list and rebuild the screen content."""
        self._teams = load_all_teams()
        self._selected_team = None
        self._stage = "input"
        self._current_questions = []
        self._current_questions_form = None
        self._current_ai_response = None
        if self._container is not None:
            self._container.content = self._build_content()
            self.page.update()

    def restore_draft(self, draft: Draft) -> None:
        """Populate the screen with draft data. Must be called after build()."""
        self._selected_team = next(
            (t for t in self._teams if t.name == draft.team_name), None
        )
        self._stage = draft.stage
        self._user_input_value = draft.user_input
        self._current_questions = draft.questions
        self._current_questions_form = None
        self._current_ai_response = draft.ai_response

        if self._team_dropdown is not None:
            self._team_dropdown.value = draft.team_name
        if self._user_input is not None:
            self._user_input.value = draft.user_input

        if draft.stage == "clarification" and draft.questions:
            self._set_clarification_view()
            initial_answers = [
                a[1] if len(a) > 1 else "" for a in draft.answers
            ]

            def on_answers_submitted(answers: list[tuple[str, str]]) -> None:
                self.page.run_task(self._run_generation, draft.user_input, answers)

            form = QuestionsForm(
                page=self.page,
                questions=draft.questions,
                on_submit=on_answers_submitted,
                initial_answers=initial_answers,
            )
            self._current_questions_form = form
            if self._result_area is not None:
                self._result_area.controls = [form.build()]

        elif draft.stage == "ready" and draft.ai_response is not None:
            self._set_ready_view()
            if self._result_area is not None:
                self._result_area.controls = [
                    ResultCard(self.page, draft.ai_response).build()
                ]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_content(self) -> ft.Control:
        team_options = [ft.dropdown.Option(t.name) for t in self._teams]

        self._team_dropdown = ft.Dropdown(
            label="Команда",
            options=team_options,
            hint_text="Выберите команду..." if team_options else "Добавьте команды в разделе «Команды»",
            width=320,
            on_select=self._on_team_change,
        )

        self._user_input = ft.TextField(
            label="Описание задачи",
            multiline=True,
            min_lines=5,
            max_lines=12,
            hint_text="Опишите задачу своими словами — что нужно сделать и зачем...",
            expand=True,
        )

        self._error_text = ft.Text("", color=ft.Colors.RED_400)
        self._loading = ft.ProgressRing(visible=False, width=24, height=24)

        self._generate_btn = ft.ElevatedButton(
            "Сгенерировать",
            icon=ft.Icons.AUTO_AWESOME,
            on_click=self._on_generate_clicked,
        )

        self._back_btn = ft.TextButton(
            "Назад",
            icon=ft.Icons.ARROW_BACK,
            on_click=self._on_back_clicked,
            visible=False,
        )

        self._save_draft_btn = ft.OutlinedButton(
            "Сохранить черновик",
            icon=ft.Icons.BOOKMARK_BORDER,
            on_click=self._save_draft_clicked,
        )

        self._result_area = ft.Column(controls=[], spacing=16)

        return ft.Column(
            controls=[
                ft.Text("Создать задачу", size=24, weight=ft.FontWeight.BOLD),
                ft.Divider(),
                self._team_dropdown,
                self._user_input,
                ft.Row(
                    controls=[
                        self._generate_btn,
                        self._back_btn,
                        self._save_draft_btn,
                        self._loading,
                        self._error_text,
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=12,
                ),
                self._result_area,
            ],
            spacing=16,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

    def _on_team_change(self, e: ft.ControlEvent) -> None:
        selected_name = e.control.value
        self._selected_team = next(
            (t for t in self._teams if t.name == selected_name),
            None,
        )

    async def _on_generate_clicked(self, e: ft.ControlEvent) -> None:
        if not self._selected_team:
            self._show_error("Выберите команду")
            return
        raw = self._user_input.value if self._user_input else ""
        if not raw or not raw.strip():
            self._show_error("Введите описание задачи")
            return

        self._user_input_value = raw.strip()
        self._stage = "input"
        self._current_questions = []
        self._current_questions_form = None
        self._current_ai_response = None
        await self._run_generation(self._user_input_value, None)

    def _save_draft_clicked(self, e: ft.ControlEvent) -> None:
        # In ready stage use the stored value (input field is hidden but value is preserved).
        # For input/clarification stages read live from the field so we catch any edits.
        if self._stage == "ready":
            user_input = self._user_input_value
        elif self._user_input is not None:
            user_input = (self._user_input.value or "").strip()
        else:
            user_input = self._user_input_value

        if not self._selected_team:
            self._show_error("Выберите команду, чтобы сохранить черновик")
            return
        if not user_input:
            self._show_error("Введите описание задачи, чтобы сохранить черновик")
            return

        answers: list[list[str]] = []
        if self._stage == "clarification" and self._current_questions_form is not None:
            answers = [
                [q, a]
                for q, a in self._current_questions_form.get_current_answers()
            ]

        draft = Draft(
            id=str(uuid.uuid4()),
            created_at=datetime.now().isoformat(),
            team_name=self._selected_team.name,
            user_input=user_input,
            stage=self._stage,
            questions=self._current_questions,
            answers=answers,
            ai_response=self._current_ai_response,
        )
        save_draft(draft)
        self._clear_error()
        msg = "Сохранено" if self._stage == "ready" else "Черновик сохранён"
        snack = ft.SnackBar(content=ft.Text(msg), open=True)
        self.page.overlay.append(snack)
        self.page.update()

    async def _run_generation(
        self,
        user_input: str,
        answers: list[tuple[str, str]] | None,
    ) -> None:
        self._set_loading(True)
        self._clear_result()
        self._clear_error()

        try:
            settings = load_settings()
            response = await generate(
                team=self._selected_team,
                user_input=user_input,
                answers=answers,
                settings=settings,
            )
            self._handle_response(response, user_input)
        except Exception as exc:
            self._show_error(str(exc))
        finally:
            self._set_loading(False)
            self.page.update()

    def _handle_response(self, response: AIResponse, user_input: str) -> None:
        if response.status == "ready":
            self._stage = "ready"
            self._current_ai_response = response
            self._set_ready_view()
            self._result_area.controls = [ResultCard(self.page, response).build()]

        elif response.status == "need_clarification":
            if not response.questions:
                self._show_error("ИИ вернул пустой список вопросов.")
                return

            self._stage = "clarification"
            self._current_questions = response.questions
            self._set_clarification_view()

            def on_answers_submitted(answers: list[tuple[str, str]]) -> None:
                self._last_submitted_answers = [[q, a] for q, a in answers]
                self.page.run_task(self._run_generation, user_input, answers)

            form = QuestionsForm(
                page=self.page,
                questions=response.questions,
                on_submit=on_answers_submitted,
            )
            self._current_questions_form = form
            self._result_area.controls = [form.build()]

        else:
            self._show_error(f"Неизвестный статус ответа: {response.status!r}")

    # ------------------------------------------------------------------
    # UI state helpers
    # ------------------------------------------------------------------

    def _set_loading(self, loading: bool) -> None:
        if self._loading is not None:
            self._loading.visible = loading
        if self._generate_btn is not None:
            self._generate_btn.disabled = loading
        if self._back_btn is not None:
            self._back_btn.disabled = loading
        if self._save_draft_btn is not None:
            self._save_draft_btn.disabled = loading
        self.page.update()

    def _show_error(self, message: str) -> None:
        if self._error_text is not None:
            self._error_text.value = message
        self.page.update()

    def _clear_error(self) -> None:
        if self._error_text is not None:
            self._error_text.value = ""

    def _clear_result(self) -> None:
        if self._result_area is not None:
            self._result_area.controls = []

    def _set_ready_view(self) -> None:
        """Switch to ready stage: hide input fields, show Back button, rename Save."""
        if self._team_dropdown is not None:
            self._team_dropdown.visible = False
        if self._user_input is not None:
            self._user_input.visible = False
        if self._generate_btn is not None:
            self._generate_btn.visible = False
        if self._back_btn is not None:
            self._back_btn.visible = True
        if self._save_draft_btn is not None:
            self._save_draft_btn.content = "Сохранить"
            self._save_draft_btn.icon = ft.Icons.SAVE

    def _set_clarification_view(self) -> None:
        """Switch to clarification stage: make inputs read-only, show Back button."""
        if self._team_dropdown is not None:
            self._team_dropdown.visible = True
            self._team_dropdown.disabled = True
        if self._user_input is not None:
            self._user_input.visible = True
            self._user_input.disabled = True
        if self._generate_btn is not None:
            self._generate_btn.visible = False
        if self._back_btn is not None:
            self._back_btn.visible = True

    def _set_input_view(self) -> None:
        """Switch back to input stage: restore editable fields and Generate button."""
        if self._team_dropdown is not None:
            self._team_dropdown.visible = True
            self._team_dropdown.disabled = False
        if self._user_input is not None:
            self._user_input.visible = True
            self._user_input.disabled = False
        if self._generate_btn is not None:
            self._generate_btn.visible = True
        if self._back_btn is not None:
            self._back_btn.visible = False
        if self._save_draft_btn is not None:
            self._save_draft_btn.content = "Сохранить черновик"
            self._save_draft_btn.icon = ft.Icons.BOOKMARK_BORDER

    def _on_back_clicked(self, e: ft.ControlEvent) -> None:
        """Back from clarification → input; back from ready → clarification or input."""
        if self._stage == "clarification":
            self._stage = "input"
            self._current_questions = []
            self._current_questions_form = None
            self._set_input_view()
            self._clear_result()
            self.page.update()
            return

        # From ready stage: go back to clarification (with previous answers) or input
        self._current_ai_response = None

        if self._current_questions:
            self._stage = "clarification"
            initial_answers = [
                a[1] if len(a) > 1 else "" for a in self._last_submitted_answers
            ]

            def on_answers_submitted(answers: list[tuple[str, str]]) -> None:
                self._last_submitted_answers = [[q, a] for q, a in answers]
                self.page.run_task(
                    self._run_generation, self._user_input_value, answers
                )

            form = QuestionsForm(
                page=self.page,
                questions=self._current_questions,
                on_submit=on_answers_submitted,
                initial_answers=initial_answers,
            )
            self._current_questions_form = form
            self._set_clarification_view()
            if self._result_area is not None:
                self._result_area.controls = [form.build()]
        else:
            self._stage = "input"
            self._set_input_view()
            self._clear_result()

        self.page.update()

import flet as ft

from data.models import Term
from data.terms_store import load_terms, save_terms


class TermsScreen:
    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self._terms: list[Term] = []
        self._list_column: ft.Column | None = None
        self._edit_index: int | None = None  # index of term being edited

    def build(self) -> ft.Control:
        self._terms = load_terms()
        self._edit_index = None

        name_field = ft.TextField(
            hint_text="Термин или сокращение",
            dense=True,
            width=200,
        )
        desc_field = ft.TextField(
            hint_text="Расшифровка / описание",
            dense=True,
            expand=True,
        )
        add_error = ft.Text("", color=ft.Colors.RED_400, size=12)

        def do_add(e: ft.ControlEvent) -> None:
            name = (name_field.value or "").strip()
            desc = (desc_field.value or "").strip()
            if not name:
                add_error.value = "Введите термин"
                add_error.update()
                return
            if not desc:
                add_error.value = "Введите описание"
                add_error.update()
                return
            if any(t.name.lower() == name.lower() for t in self._terms):
                add_error.value = "Такой термин уже есть"
                add_error.update()
                return
            add_error.value = ""
            self._terms.append(Term(name=name, description=desc))
            save_terms(self._terms)
            name_field.value = ""
            desc_field.value = ""
            name_field.update()
            desc_field.update()
            add_error.update()
            self._refresh_list()

        add_row = ft.Row(
            controls=[
                name_field,
                desc_field,
                ft.IconButton(
                    icon=ft.Icons.ADD_CIRCLE_OUTLINE,
                    tooltip="Добавить термин",
                    on_click=do_add,
                ),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=8,
        )

        self._list_column = ft.Column(
            controls=self._build_rows(),
            spacing=4,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

        return ft.Container(
            padding=30,
            expand=True,
            content=ft.Column(
                controls=[
                    ft.Text("Термины и сокращения", size=24, weight=ft.FontWeight.BOLD),
                    ft.Text(
                        "Термины учитываются при формировании задач для команд с включённой опцией "
                        "«Учитывать сохранённые термины и сокращения».",
                        size=13,
                        color=ft.Colors.GREY_600,
                    ),
                    ft.Divider(),
                    add_row,
                    add_error,
                    ft.Divider(height=1),
                    self._list_column,
                ],
                spacing=10,
                expand=True,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
        )

    def _build_rows(self) -> list[ft.Control]:
        if not self._terms:
            return [
                ft.Text(
                    "Термины не добавлены",
                    color=ft.Colors.GREY_500,
                    italic=True,
                    size=13,
                )
            ]
        rows: list[ft.Control] = []
        for i, term in enumerate(self._terms):
            rows.append(self._build_row(i, term))
        return rows

    def _build_row(self, index: int, term: Term) -> ft.Control:
        if self._edit_index == index:
            return self._build_edit_row(index, term)
        return self._build_view_row(index, term)

    def _build_view_row(self, index: int, term: Term) -> ft.Control:
        def on_edit(e: ft.ControlEvent, i: int = index) -> None:
            self._edit_index = i
            self._refresh_list()

        def on_delete(e: ft.ControlEvent, i: int = index) -> None:
            self._terms.pop(i)
            save_terms(self._terms)
            if self._edit_index == i:
                self._edit_index = None
            elif self._edit_index is not None and self._edit_index > i:
                self._edit_index -= 1
            self._refresh_list()

        return ft.Container(
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
            bgcolor=ft.Colors.SURFACE_CONTAINER,
            border_radius=8,
            content=ft.Row(
                controls=[
                    ft.Text(term.name, size=14, weight=ft.FontWeight.W_600, width=200),
                    ft.Text(term.description, size=13, color=ft.Colors.GREY_700, expand=True),
                    ft.IconButton(
                        icon=ft.Icons.EDIT_OUTLINED,
                        icon_size=18,
                        tooltip="Редактировать",
                        on_click=on_edit,
                        style=ft.ButtonStyle(padding=ft.padding.all(4)),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE,
                        icon_size=18,
                        tooltip="Удалить",
                        on_click=on_delete,
                        style=ft.ButtonStyle(
                            color=ft.Colors.RED_400,
                            padding=ft.padding.all(4),
                        ),
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=6,
            ),
        )

    def _build_edit_row(self, index: int, term: Term) -> ft.Control:
        name_f = ft.TextField(value=term.name, dense=True, width=200)
        desc_f = ft.TextField(value=term.description, dense=True, expand=True)

        def on_save(e: ft.ControlEvent, i: int = index) -> None:
            name = (name_f.value or "").strip()
            desc = (desc_f.value or "").strip()
            if not name or not desc:
                return
            # Check duplicate (excluding self)
            if any(
                j != i and t.name.lower() == name.lower()
                for j, t in enumerate(self._terms)
            ):
                return
            self._terms[i] = Term(name=name, description=desc)
            save_terms(self._terms)
            self._edit_index = None
            self._refresh_list()

        def on_cancel(e: ft.ControlEvent) -> None:
            self._edit_index = None
            self._refresh_list()

        return ft.Container(
            padding=ft.padding.symmetric(horizontal=12, vertical=6),
            border=ft.border.all(1, ft.Colors.PRIMARY),
            border_radius=8,
            content=ft.Row(
                controls=[
                    name_f,
                    desc_f,
                    ft.IconButton(
                        icon=ft.Icons.CHECK,
                        icon_size=18,
                        tooltip="Сохранить",
                        on_click=on_save,
                        style=ft.ButtonStyle(
                            color=ft.Colors.GREEN_700,
                            padding=ft.padding.all(4),
                        ),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.CLOSE,
                        icon_size=18,
                        tooltip="Отмена",
                        on_click=on_cancel,
                        style=ft.ButtonStyle(padding=ft.padding.all(4)),
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=6,
            ),
        )

    def _refresh_list(self) -> None:
        if self._list_column is not None:
            self._list_column.controls = self._build_rows()
            self._list_column.update()

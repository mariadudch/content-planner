"""Тесты для sheets.py. Запуск из папки проекта: pytest

Настоящий Google в тестах не трогаем: вместо библиотеки gspread подставляем поддельную
(FakeGspread) — она ведёт себя как gspread, но всё хранит в памяти. Так проверяем свою логику
без интернета и без риска испортить настоящую таблицу.
"""

import json
import sys
import types

import pytest

from export import HEADER
from models import ContentUnit
from reader import parse_line
from sheets import SheetsError, load_settings, sheet_values, upload, write_values
from storage import ContentPlan

URL = "https://docs.google.com/spreadsheets/d/abc123/edit"


# ---------- подделки ----------

class FakeWorksheet:
    """Поддельный лист: запоминает, что с ним делали."""

    def __init__(self, title, rows=100):
        self.title = title
        self.row_count = rows
        self.values = [["старое содержимое"]]

    def resize(self, rows):
        self.row_count = rows

    def clear(self):
        self.values = []

    def update(self, values, range_name, value_input_option):
        assert range_name == "A1"
        assert value_input_option == "USER_ENTERED"
        self.values = values


def make_fake_gspread(existing_sheets=("Календарь",), error=None):
    """Собирает поддельный модуль gspread.

    error — какую ошибку «бросит Google» при открытии таблицы: готовая ошибка (PermissionError(...))
    или название ошибки самой библиотеки gspread строкой ("NoValidUrlKeyFound").
    """
    fake = types.SimpleNamespace()
    fake.exceptions = types.SimpleNamespace(
        WorksheetNotFound=type("WorksheetNotFound", (Exception,), {}),
        NoValidUrlKeyFound=type("NoValidUrlKeyFound", (Exception,), {}),
        SpreadsheetNotFound=type("SpreadsheetNotFound", (Exception,), {}),
        APIError=type("APIError", (Exception,), {}),
    )
    sheets = {name: FakeWorksheet(name) for name in existing_sheets}

    class FakeSpreadsheet:
        def worksheet(self, title):
            if title not in sheets:
                raise fake.exceptions.WorksheetNotFound(title)
            return sheets[title]

        def add_worksheet(self, title, rows, cols):
            sheets[title] = FakeWorksheet(title, rows)
            return sheets[title]

    class FakeClient:
        def open_by_url(self, url):
            if isinstance(error, str):
                raise getattr(fake.exceptions, error)()
            if error is not None:
                raise error
            return FakeSpreadsheet()

    fake.service_account = lambda filename: FakeClient()
    fake.sheets = sheets  # чтобы тест мог заглянуть, что записалось
    return fake


@pytest.fixture
def key_path(tmp_path):
    path = tmp_path / "google_key.json"
    path.write_text(json.dumps({"client_email": "planner@project.iam.gserviceaccount.com"}), encoding="utf-8")
    return path


def small_plan():
    plan = ContentPlan()
    idea = parse_line("Мой вечерний уход", 1)
    unit = ContentUnit(idea=idea, rubric="Бьюти", format_name="Рилс", platforms=["Instagram"], matched=[],
                       date="2026-10-26")
    plan.add(idea, [unit], "2026-10-22")
    return plan


SETTINGS = {"spreadsheet_url": URL, "worksheet": "План от программы"}


# ---------- настройки ----------

def test_load_settings_missing_file_is_none(tmp_path):
    assert load_settings(tmp_path / "google.json") is None


def test_load_settings_ok(tmp_path):
    path = tmp_path / "google.json"
    path.write_text(json.dumps(SETTINGS, ensure_ascii=False), encoding="utf-8")
    assert load_settings(path) == SETTINGS


def test_load_settings_broken_json(tmp_path):
    path = tmp_path / "google.json"
    path.write_text('{"spreadsheet_url": "abc" "worksheet": "План"}', encoding="utf-8")
    with pytest.raises(SheetsError, match="строка 1"):
        load_settings(path)


def test_load_settings_empty_worksheet(tmp_path):
    path = tmp_path / "google.json"
    path.write_text('{"spreadsheet_url": "abc", "worksheet": "  "}', encoding="utf-8")
    with pytest.raises(SheetsError, match="worksheet"):
        load_settings(path)


# ---------- что пишем на лист ----------

def test_sheet_values_header_first():
    values = sheet_values(small_plan())
    assert values[0] == HEADER
    assert values[1] == ["26.10.2026", "пн", "Рилс", "Instagram", "Бьюти", "Мой вечерний уход"]


def test_write_values_replaces_old_content():
    sheet = FakeWorksheet("План", rows=100)
    write_values(sheet, [["a"], ["b"]])
    assert sheet.values == [["a"], ["b"]]


def test_write_values_adds_rows_when_needed():
    sheet = FakeWorksheet("План", rows=2)
    write_values(sheet, [["строка"]] * 5)
    assert sheet.row_count == 5


# ---------- отправка целиком (с поддельным gspread) ----------

def test_upload_creates_sheet_and_keeps_others(monkeypatch, key_path):
    fake = make_fake_gspread(existing_sheets=("Календарь",))
    monkeypatch.setitem(sys.modules, "gspread", fake)

    count = upload(small_plan(), SETTINGS, key_path)

    assert count == 1
    assert fake.sheets["План от программы"].values[0] == HEADER  # новый лист создан и заполнен
    assert fake.sheets["Календарь"].values == [["старое содержимое"]]  # твой календарь не тронут


def test_upload_without_key(tmp_path):
    with pytest.raises(SheetsError, match="нет ключа"):
        upload(small_plan(), SETTINGS, tmp_path / "google_key.json")


def test_upload_without_gspread_installed(monkeypatch, key_path):
    monkeypatch.setitem(sys.modules, "gspread", None)  # так Python считает, что библиотеки нет
    with pytest.raises(SheetsError, match="pip install"):
        upload(small_plan(), SETTINGS, key_path)


def test_upload_no_access_names_service_email(monkeypatch, key_path):
    # Таблицей не поделились с сервисным аккаунтом — в сообщении должна быть его почта
    monkeypatch.setitem(sys.modules, "gspread", make_fake_gspread(error=PermissionError("403")))
    with pytest.raises(SheetsError, match="planner@project.iam.gserviceaccount.com"):
        upload(small_plan(), SETTINGS, key_path)


def test_upload_bad_url(monkeypatch, key_path):
    monkeypatch.setitem(sys.modules, "gspread", make_fake_gspread(error="NoValidUrlKeyFound"))
    with pytest.raises(SheetsError, match="не похожа на ссылку"):
        upload(small_plan(), SETTINGS, key_path)


def test_upload_no_internet(monkeypatch, key_path):
    monkeypatch.setitem(sys.modules, "gspread", make_fake_gspread(error=ConnectionError("no network")))
    with pytest.raises(SheetsError, match="интернет"):
        upload(small_plan(), SETTINGS, key_path)


def test_upload_broken_key(monkeypatch, key_path):
    fake = make_fake_gspread()

    def broken_service_account(filename):
        raise ValueError("Service account info was not in the expected format")

    fake.service_account = broken_service_account
    monkeypatch.setitem(sys.modules, "gspread", fake)
    with pytest.raises(SheetsError, match="повреждён"):
        upload(small_plan(), SETTINGS, key_path)

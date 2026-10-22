"""Тесты для export.py. Запуск из папки проекта: pytest"""

import csv

from export import HEADER, plan_rows, safe_cell, save_csv
from models import ContentUnit
from reader import parse_line
from storage import ContentPlan


def add(plan, text, unit_date, format_name="Рилс"):
    """Помощник: идея с одной единицей контента на указанную дату ("" — бэклог)."""
    idea = parse_line(text, 1)
    unit = ContentUnit(
        idea=idea, rubric="Бьюти", format_name=format_name,
        platforms=["Instagram", "VK"], matched=[], date=unit_date,
    )
    plan.add(idea, [unit], "2026-10-22")


def test_safe_cell():
    assert safe_cell("=) смешной рилс") == "'=) смешной рилс"
    assert safe_cell("+100 к уверенности") == "'+100 к уверенности"
    assert safe_cell("Обычная идея") == "Обычная идея"


def test_rows_sorted_by_date_backlog_last():
    plan = ContentPlan()
    add(plan, "Идея в бэклоге", "")
    add(plan, "Идея на среду", "2026-10-28")
    add(plan, "Идея на понедельник", "2026-10-26")
    rows = plan_rows(plan)
    assert [row[5] for row in rows] == ["Идея на понедельник", "Идея на среду", "Идея в бэклоге"]
    assert rows[0][:2] == ["26.10.2026", "пн"]
    assert rows[2][:2] == ["", ""]  # у бэклога нет даты и дня недели


def test_row_columns():
    plan = ContentPlan()
    add(plan, "Мой вечерний уход", "2026-10-26")
    add(plan, "Мой вечерний уход", "2026-10-27")  # часть 2
    rows = plan_rows(plan)
    assert rows[0] == ["26.10.2026", "пн", "Рилс", "Instagram, VK", "Бьюти", "Мой вечерний уход"]
    assert rows[1][5] == "Мой вечерний уход — часть 2"


def test_save_csv_for_excel(tmp_path):
    plan = ContentPlan()
    add(plan, "Тоник; сыворотка и крем", "2026-10-26")  # точка с запятой внутри текста
    path = tmp_path / "data" / "plan.csv"
    save_csv(plan, path)

    raw = path.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")  # метка BOM — Excel поймёт, что это UTF-8

    with open(path, encoding="utf-8-sig", newline="") as file:
        rows = list(csv.reader(file, delimiter=";"))
    assert rows[0] == HEADER
    assert rows[1][5] == "Тоник; сыворотка и крем"  # «;» в тексте не разрезал ячейку


def test_save_csv_empty_plan(tmp_path):
    path = tmp_path / "plan.csv"
    save_csv(ContentPlan(), path)
    with open(path, encoding="utf-8-sig", newline="") as file:
        rows = list(csv.reader(file, delimiter=";"))
    assert rows == [HEADER]

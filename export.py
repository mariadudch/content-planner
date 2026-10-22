"""Выгрузка плана в таблицу.

- plan_rows — превращает план в строки таблицы (их же на этапе 6 отправим в Google Таблицу);
- save_csv — сохраняет эти строки в CSV-файл, который открывается в Excel и Google Таблицах.
"""

import csv
from datetime import date
from pathlib import Path

from models import ContentUnit
from storage import ContentPlan

HEADER = ["Дата", "День", "Формат", "Площадки", "Рубрика", "Идея"]
WEEKDAYS = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]

# Если ячейка начинается с этих символов, Excel и Google Таблицы считают её ФОРМУЛОЙ.
# Идея «=) смешной рилс» превратилась бы в ошибку, а хитрая «формула» могла бы что-то выполнить.
FORMULA_START = ("=", "+", "-", "@")


def safe_cell(text: str) -> str:
    """Защита от формул: если текст начинается с = + - @, ставим перед ним апостроф.

    Апостроф в начале ячейки таблицы понимают как «это просто текст» и сами его не показывают.
    """
    if text.startswith(FORMULA_START):
        return "'" + text
    return text


def by_date(unit: ContentUnit) -> str:
    """Ключ сортировки: дата строкой "2026-10-24" — такие строки сортируются как даты."""
    return unit.date


def plan_rows(plan: ContentPlan) -> list[list[str]]:
    """Строки таблицы: сначала единицы с датами по порядку, в конце — бэклог (без даты)."""
    dated = sorted([unit for unit in plan.units if unit.date], key=by_date)
    waiting = [unit for unit in plan.units if not unit.date]

    rows = []
    for unit in dated + waiting:
        if unit.date:
            day = date.fromisoformat(unit.date)
            date_text = day.strftime("%d.%m.%Y")
            weekday = WEEKDAYS[day.weekday()]
        else:
            date_text = ""
            weekday = ""
        rows.append([
            date_text,
            weekday,
            unit.format_name,
            ", ".join(unit.platforms),
            unit.rubric,
            safe_cell(unit.idea.title()),
        ])
    return rows


def save_csv(plan: ContentPlan, path: Path) -> None:
    """Сохраняет план в CSV для Excel и Google Таблиц.

    - encoding="utf-8-sig": в начале файла невидимая метка BOM — по ней Excel понимает,
      что это UTF-8, и не ломает русские буквы;
    - delimiter=";": русский Excel ждёт точку с запятой, а не запятую;
    - newline="": так требует модуль csv, иначе на Windows между строками появятся пустые.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file, delimiter=";")
        writer.writerow(HEADER)
        writer.writerows(plan_rows(plan))

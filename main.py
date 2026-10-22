"""Точка входа в программу.

Этап 4: разбирает новые идеи, запоминает их и расставляет единицы контента по датам.

Два режима:
- файл из папки data/ (например, data/ideas.txt) — РАБОЧИЙ режим: идеи заносятся в память
  (data/state.json), а их строки удаляются из файла — он работает как «входящие»;
- любой другой файл (например, examples/ideas_demo.txt) — режим ПРОСМОТРА: программа только
  показывает разбор и план, ничего не запоминает и файл не трогает.

Запуск:  python main.py data/ideas.txt
"""

import sys
from datetime import date, timedelta
from pathlib import Path

from classifier import RulesError, load_rules, make_units
from models import ContentUnit, Idea
from planner import backlog, schedule, units_by_day
from reader import IdeasFileError, read_ideas
from storage import ContentPlan, clean_inbox, is_inside, load_plan, save_plan

PROJECT_DIR = Path(__file__).parent
RULES_PATH = PROJECT_DIR / "rules.json"
DATA_DIR = PROJECT_DIR / "data"
STATE_PATH = DATA_DIR / "state.json"

WEEKDAYS = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]


def print_new_idea(idea: Idea, units: list[ContentUnit]) -> None:
    """Печатает новую идею: какие рубрики подошли и сколько единиц контента получилось."""
    mark = "!" if idea.urgent else " "
    rubrics = []
    for unit in units:
        if unit.rubric not in rubrics:
            rubrics.append(unit.rubric)
    print(f"{mark} [строка {idea.line_no}] {idea.title()}")
    print(f"     рубрики: {', '.join(rubrics)} → единиц контента: {len(units)}")


def print_calendar(plan: ContentPlan, first: date, last: date) -> None:
    """Печатает план по дням: дата, формат, рубрика, идея."""
    print(f"\n=== План с {first:%d.%m} по {last:%d.%m} ===")
    days = units_by_day(plan, first, last)
    if not days:
        print("Пока пусто.")
    for day, units in days.items():
        print(f"\n{WEEKDAYS[day.weekday()]} {day:%d.%m}")
        for unit in units:
            print(f"   {unit.format_name:<16} | {unit.rubric:<30} | {unit.idea.title()}")


def main() -> None:
    if len(sys.argv) < 2:
        print("Как запускать: python main.py путь/к/файлу_с_идеями.txt")
        return

    path = sys.argv[1]
    working_mode = is_inside(path, DATA_DIR)

    try:
        rules = load_rules(str(RULES_PATH))
        ideas, warnings = read_ideas(path)
    except (RulesError, IdeasFileError) as error:
        print(f"Ошибка: {error}")
        return

    if working_mode:
        plan, state_warning = load_plan(STATE_PATH)
        if state_warning:
            print(f"Внимание: {state_warning}")
    else:
        plan = ContentPlan()  # в режиме просмотра начинаем с пустого плана и ничего не сохраняем

    today = date.today()
    repeats = 0
    for idea in ideas:
        units = make_units(idea, rules)
        plan.add(idea, units, today.isoformat())
        if idea.part > 1:
            repeats += 1
        print_new_idea(idea, units)

    if warnings:
        print(f"\nПропущено строк: {len(warnings)}")
        for message in warnings.values():
            print(f"  - {message}")

    print(f"\nНовых идей: {len(ideas)} (из них повторов: {repeats})")

    # Расстановка по датам: с завтрашнего дня на horizon_days дней вперёд
    start = today + timedelta(days=1)
    horizon_days = rules["planning"]["horizon_days"]
    for message in schedule(plan, rules["formats"], start, horizon_days):
        print(f"Внимание: {message}")

    print_calendar(plan, start, start + timedelta(days=horizon_days - 1))
    print(f"\nВ бэклоге (ждут свободного места) — единиц контента: {len(backlog(plan))}")

    if not working_mode:
        print("\nРежим просмотра: файл не из папки data — ничего не сохраняю.")
        return

    # Сначала сохраняем память, и только потом чистим файл с идеями.
    # Если что-то сломается между этими шагами, идея не потеряется (в худшем случае повторится).
    try:
        save_plan(plan, STATE_PATH)
        clean_inbox(path, list(warnings.keys()))
    except OSError as error:
        print(f"Ошибка: не получилось сохранить ({error}). Файл с идеями не трогаю.")
        return

    print(f"\nВсего в памяти — идей: {len(plan.ideas)}, единиц контента: {len(plan.units)}.")
    if warnings:
        print(f"В {path} остались только строки, которые нужно поправить.")
    else:
        print(f"Файл {path} очищен — все идеи в плане.")


if __name__ == "__main__":
    main()

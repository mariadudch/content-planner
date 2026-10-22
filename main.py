"""Точка входа в программу.

Этап 3: программа запоминает разобранные идеи между запусками.

Два режима:
- файл из папки data/ (например, data/ideas.txt) — РАБОЧИЙ режим: идеи заносятся в память
  (data/state.json), а их строки удаляются из файла — он работает как «входящие»;
- любой другой файл (например, examples/ideas_demo.txt) — режим ПРОСМОТРА: программа только
  показывает разбор, ничего не запоминает и файл не трогает.

Запуск:  python main.py data/ideas.txt
"""

import sys
from datetime import date
from pathlib import Path

from classifier import RulesError, load_rules, make_units
from models import ContentUnit, Idea
from reader import IdeasFileError, read_ideas
from storage import ContentPlan, clean_inbox, is_inside, load_plan, save_plan

PROJECT_DIR = Path(__file__).parent
RULES_PATH = PROJECT_DIR / "rules.json"
DATA_DIR = PROJECT_DIR / "data"
STATE_PATH = DATA_DIR / "state.json"


def print_idea(idea: Idea, units: list[ContentUnit]) -> None:
    """Печатает идею и её единицы контента."""
    mark = "!" if idea.urgent else " "
    print(f"\n{mark} [строка {idea.line_no}] {idea.title()}")
    for unit in units:
        reason = ", ".join(unit.matched) if unit.matched else "нет совпадений"
        platforms = ", ".join(unit.platforms)
        print(f"     {unit.format_name:<16} | {unit.rubric:<30} | {reason}  →  {platforms}")


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

    today = date.today().isoformat()
    repeats = 0
    for idea in ideas:
        units = make_units(idea, rules)
        plan.add(idea, units, today)
        if idea.part > 1:
            repeats += 1
        print_idea(idea, units)

    if warnings:
        print(f"\nПропущено строк: {len(warnings)}")
        for message in warnings.values():
            print(f"  - {message}")

    print(f"\nНовых идей: {len(ideas)} (из них повторов: {repeats})")

    if not working_mode:
        print("Режим просмотра: файл не из папки data — ничего не сохраняю.")
        return

    # Сначала сохраняем память, и только потом чистим файл с идеями.
    # Если что-то сломается между этими шагами, идея не потеряется (в худшем случае повторится).
    try:
        save_plan(plan, STATE_PATH)
        clean_inbox(path, list(warnings.keys()))
    except OSError as error:
        print(f"Ошибка: не получилось сохранить ({error}). Файл с идеями не трогаю.")
        return

    print(f"Всего в памяти — идей: {len(plan.ideas)}, единиц контента: {len(plan.units)}.")
    if warnings:
        print(f"В {path} остались только строки, которые нужно поправить.")
    else:
        print(f"Файл {path} очищен — все идеи в плане.")


if __name__ == "__main__":
    main()

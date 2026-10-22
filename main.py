"""Точка входа в программу: команды.

    python main.py run                        разобрать data/ideas.txt, поставить даты, сохранить, выгрузить CSV
    python main.py add "Нашла классный тинт"   добавить одну идею прямо из терминала
    python main.py show [--days 7]            показать текущий план (ничего не меняет)
    python main.py preview ФАЙЛ               разбор и план для любого файла, ничего не сохраняет (демо)
    python main.py --help                     список команд

Память программы — data/state.json, план в виде таблицы — data/plan.csv.
"""

import argparse
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from classifier import RulesError, load_rules, make_units
from export import WEEKDAYS, save_csv
from models import ContentUnit, Idea
from planner import backlog, schedule, units_by_day
from reader import IdeasFileError, parse_line, read_ideas
from storage import ContentPlan, clean_inbox, load_plan, save_plan

PROJECT_DIR = Path(__file__).parent
RULES_PATH = PROJECT_DIR / "rules.json"
DATA_DIR = PROJECT_DIR / "data"
INBOX_PATH = DATA_DIR / "ideas.txt"
STATE_PATH = DATA_DIR / "state.json"
CSV_PATH = DATA_DIR / "plan.csv"


# ---------- печать ----------

def print_new_idea(idea: Idea, units: list[ContentUnit]) -> None:
    """Печатает новую идею: какие рубрики подошли и сколько единиц контента получилось."""
    mark = "!" if idea.urgent else " "
    where = f"[строка {idea.line_no}] " if idea.line_no > 0 else ""
    rubrics = []
    for unit in units:
        if unit.rubric not in rubrics:
            rubrics.append(unit.rubric)
    print(f"{mark} {where}{idea.title()}")
    print(f"     рубрики: {', '.join(rubrics)} → единиц контента: {len(units)}")


def print_calendar(plan: ContentPlan, first: date, last: date) -> None:
    """Печатает план по дням: дата, формат, рубрика, идея. И размер бэклога."""
    print(f"\n=== План с {first:%d.%m} по {last:%d.%m} ===")
    days = units_by_day(plan, first, last)
    if not days:
        print("Пока пусто.")
    for day, units in days.items():
        print(f"\n{WEEKDAYS[day.weekday()]} {day:%d.%m}")
        for unit in units:
            print(f"   {unit.format_name:<16} | {unit.rubric:<30} | {unit.idea.title()}")
    print(f"\nВ бэклоге (ждут свободного места) — единиц контента: {len(backlog(plan))}")


# ---------- общие шаги ----------

def add_ideas(plan: ContentPlan, ideas: list[Idea], rules: dict, today: date) -> None:
    """Разбирает идеи на единицы контента, добавляет в план и печатает каждую."""
    repeats = 0
    for idea in ideas:
        units = make_units(idea, rules)
        plan.add(idea, units, today.isoformat())
        if idea.part > 1:
            repeats += 1
        print_new_idea(idea, units)
    print(f"\nНовых идей: {len(ideas)} (из них повторов: {repeats})")


def schedule_and_print(plan: ContentPlan, rules: dict, today: date) -> None:
    """Ставит даты (с завтрашнего дня на horizon_days вперёд) и печатает план."""
    start = today + timedelta(days=1)
    horizon_days = rules["planning"]["horizon_days"]
    for message in schedule(plan, rules["formats"], start, horizon_days):
        print(f"Внимание: {message}")
    print_calendar(plan, start, start + timedelta(days=horizon_days - 1))


def load_memory() -> ContentPlan:
    """Загружает память и печатает предупреждение, если файл памяти был повреждён."""
    plan, warning = load_plan(STATE_PATH)
    if warning:
        print(f"Внимание: {warning}")
    return plan


def save_memory(plan: ContentPlan) -> bool:
    """Сохраняет память и CSV. Возвращает True, если всё получилось."""
    try:
        save_plan(plan, STATE_PATH)
        save_csv(plan, CSV_PATH)
    except OSError as error:
        print(f"Ошибка: не получилось сохранить ({error}).")
        return False
    print(f"\nВсего в памяти — идей: {len(plan.ideas)}, единиц контента: {len(plan.units)}.")
    print(f"План в виде таблицы: {CSV_PATH.relative_to(PROJECT_DIR)}")
    return True


def print_warnings(warnings: dict[int, str]) -> None:
    if warnings:
        print(f"\nПропущено строк: {len(warnings)}")
        for message in warnings.values():
            print(f"  - {message}")


# ---------- команды ----------

def command_run(rules: dict) -> None:
    """run: разобрать «входящие» data/ideas.txt, поставить даты, сохранить, очистить файл."""
    if INBOX_PATH.exists():
        ideas, warnings = read_ideas(str(INBOX_PATH))
    else:
        print(f"Файла {INBOX_PATH.relative_to(PROJECT_DIR)} нет — новых идей нет, обновляю план.")
        ideas, warnings = [], {}

    plan = load_memory()
    add_ideas(plan, ideas, rules, date.today())
    print_warnings(warnings)
    schedule_and_print(plan, rules, date.today())

    # Сначала сохраняем память, и только потом чистим файл с идеями.
    # Если что-то сломается между этими шагами, идея не потеряется (в худшем случае повторится).
    if not save_memory(plan):
        print("Файл с идеями не трогаю.")
        return
    if INBOX_PATH.exists():
        try:
            clean_inbox(str(INBOX_PATH), list(warnings.keys()))
        except OSError as error:
            print(f"Ошибка: не получилось очистить файл с идеями ({error}).")
            return
        if warnings:
            print("В data/ideas.txt остались только строки, которые нужно поправить.")
        else:
            print("Файл data/ideas.txt очищен — все идеи в плане.")


def command_add(rules: dict, text: str) -> None:
    """add: добавить одну идею из терминала."""
    try:
        idea = parse_line(text, 0)  # 0 — идея не из файла, номера строки нет
    except ValueError:
        print("Ошибка: слишком коротко — допиши мысль хотя бы до двух слов.")
        return
    if idea is None:
        print("Ошибка: в идее нет ни одного слова.")
        return

    plan = load_memory()
    add_ideas(plan, [idea], rules, date.today())
    schedule_and_print(plan, rules, date.today())
    save_memory(plan)


def command_show(rules: dict, days: Optional[int]) -> None:
    """show: показать план из памяти, начиная с сегодня. Ничего не меняет."""
    plan = load_memory()
    if days is None:
        days = rules["planning"]["horizon_days"]
    today = date.today()
    print_calendar(plan, today, today + timedelta(days=days - 1))


def command_preview(rules: dict, path: str) -> None:
    """preview: разбор и план для любого файла — на пустой памяти, ничего не сохраняет."""
    ideas, warnings = read_ideas(path)
    plan = ContentPlan()
    add_ideas(plan, ideas, rules, date.today())
    print_warnings(warnings)
    schedule_and_print(plan, rules, date.today())
    print("\nРежим просмотра — ничего не сохраняю.")


# ---------- разбор команд ----------

def positive_int(text: str) -> int:
    """Тип для argparse: целое число от 1 (для --days)."""
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"нужно целое число, а не «{text}»")
    if value < 1:
        raise argparse.ArgumentTypeError("нужно число от 1")
    return value


def build_parser() -> argparse.ArgumentParser:
    """Описывает, какие команды и аргументы понимает программа."""
    parser = argparse.ArgumentParser(
        description="Контент-планер: идеи → рубрики, форматы и даты по моим правилам.",
    )
    commands = parser.add_subparsers(dest="command", required=True, metavar="команда")

    commands.add_parser("run", help="разобрать data/ideas.txt, поставить даты, сохранить и выгрузить CSV")

    add = commands.add_parser("add", help="добавить одну идею из терминала")
    add.add_argument("text", help="текст идеи в кавычках, например \"Нашла классный тинт\"")

    show = commands.add_parser("show", help="показать текущий план (ничего не меняет)")
    show.add_argument(
        "--days", type=positive_int, default=None, help="сколько дней показать (по умолчанию — весь горизонт)",
    )

    preview = commands.add_parser("preview", help="разбор и план для любого файла, ничего не сохраняет")
    preview.add_argument("path", help="путь к файлу с идеями, например examples/ideas_demo.txt")

    return parser


def main(argv: Optional[list[str]] = None) -> None:
    args = build_parser().parse_args(argv)

    try:
        rules = load_rules(str(RULES_PATH))
        if args.command == "run":
            command_run(rules)
        elif args.command == "add":
            command_add(rules, args.text)
        elif args.command == "show":
            command_show(rules, args.days)
        elif args.command == "preview":
            command_preview(rules, args.path)
    except (RulesError, IdeasFileError) as error:
        print(f"Ошибка: {error}")


if __name__ == "__main__":
    main()

"""Точка входа в программу.

Этап 2: программа читает файл с идеями, находит рубрики и показывает,
какие единицы контента получаются из каждой идеи.
Команды (add / plan / show) появятся на этапе 5.

Запуск:  python main.py examples/ideas_demo.txt
"""

import sys
from pathlib import Path

from classifier import RulesError, load_rules, make_units
from reader import IdeasFileError, read_ideas

# rules.json лежит рядом с main.py — так программа найдёт его, откуда бы её ни запустили
RULES_PATH = Path(__file__).parent / "rules.json"


def main() -> None:
    if len(sys.argv) < 2:
        print("Как запускать: python main.py путь/к/файлу_с_идеями.txt")
        return

    path = sys.argv[1]

    try:
        rules = load_rules(str(RULES_PATH))
        ideas, warnings = read_ideas(path)
    except (RulesError, IdeasFileError) as error:
        print(f"Ошибка: {error}")
        return

    units_total = 0
    no_rubric_total = 0

    for idea in ideas:
        units = make_units(idea, rules)
        units_total += len(units)
        if units[0].rubric == rules["no_rubric"]["name"]:
            no_rubric_total += 1

        mark = "!" if idea.urgent else " "
        print(f"\n{mark} [строка {idea.line_no}] {idea.text}")
        for unit in units:
            reason = ", ".join(unit.matched) if unit.matched else "нет совпадений"
            platforms = ", ".join(unit.platforms)
            print(f"     {unit.format_name:<16} | {unit.rubric:<30} | {reason}  →  {platforms}")

    print(f"\nИдей: {len(ideas)}, единиц контента: {units_total}, без рубрики: {no_rubric_total}")

    if warnings:
        print(f"\nПропущено строк: {len(warnings)}")
        for warning in warnings:
            print(f"  - {warning}")


if __name__ == "__main__":
    main()

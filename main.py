"""Точка входа в программу.

Этап 1: программа умеет только прочитать файл с идеями и показать,
что из него получилось. Команды (add / plan / show) появятся на этапе 5.

Запуск:  python main.py examples/ideas_demo.txt
"""

import sys

from reader import IdeasFileError, read_ideas


def main() -> None:
    if len(sys.argv) < 2:
        print("Как запускать: python main.py путь/к/файлу_с_идеями.txt")
        return

    path = sys.argv[1]

    try:
        ideas, warnings = read_ideas(path)
    except IdeasFileError as error:
        print(f"Ошибка: {error}")
        return

    print(f"Нашла идей: {len(ideas)}\n")
    for idea in ideas:
        mark = "!" if idea.urgent else " "
        print(f"{mark} [строка {idea.line_no}] {idea.text}")

    if warnings:
        print(f"\nПропущено строк: {len(warnings)}")
        for warning in warnings:
            print(f"  - {warning}")


if __name__ == "__main__":
    main()

"""Чтение файла с идеями и чистка «грязных» строк.

Правила файла с идеями:
- одна идея = одна строка;
- «!» в начале строки — срочная идея, ставится в план первой;
- маркеры списка («- », «• », «1. », «2) ») можно оставлять — программа их уберёт.
"""

from typing import Optional

from models import Idea

MIN_WORDS = 2  # идея короче двух слов — это заготовка («крем»), а не мысль
BULLETS = ("-", "•", "*", "—", "–")  # маркеры списка, которые бывают в заметках


class IdeasFileError(Exception):
    """Файл с идеями нельзя прочитать целиком (нет файла, это папка, непонятная кодировка)."""


def normalize(text: str) -> str:
    """Приводит текст к простому виду для сравнения.

    «Ещё раз: КРЕМ!!! ✨» -> «еще раз крем»
    Маленькие буквы, «ё» -> «е», всё, что не буква и не цифра, -> пробел,
    лишние пробелы убираются.
    """
    text = text.lower().replace("ё", "е")
    cleaned = ""
    for char in text:
        if char.isalnum():
            cleaned += char
        else:
            cleaned += " "
    return " ".join(cleaned.split())


def strip_bullet(line: str) -> str:
    """Убирает маркер списка в начале строки: «- », «• », «1. », «2) »."""
    for bullet in BULLETS:
        if line.startswith(bullet):
            return line[len(bullet):].strip()

    first_word, _, rest = line.partition(" ")
    if len(first_word) >= 2 and first_word[:-1].isdigit() and first_word[-1] in ".)":
        return rest.strip()

    return line


def parse_line(raw_line: str, line_no: int) -> Optional[Idea]:
    """Превращает одну строку файла в идею.

    Возвращает:
    - Idea — если строка нормальная;
    - None — если строка пустая или это разделитель («---», «✨✨✨»): пропускаем молча.
    Бросает ValueError с понятным текстом, если строка есть, но идеей быть не может.
    """
    line = raw_line.strip()
    if normalize(line) == "":
        return None

    line = strip_bullet(line)

    urgent = line.startswith("!")
    text = line.lstrip("!").strip()
    key = normalize(text)

    if len(key.split()) < MIN_WORDS:
        raise ValueError(
            f"строка {line_no}: «{raw_line.strip()}» — слишком коротко, "
            f"допиши мысль хотя бы до {MIN_WORDS} слов"
        )

    return Idea(text=text, key=key, line_no=line_no, urgent=urgent)


def read_lines(path: str) -> list[str]:
    """Читает файл и возвращает список строк.

    Сначала пробует UTF-8 (так сохраняют Mac и телефоны), если не вышло —
    Windows-1251 (так сохраняет старый Блокнот в Windows).
    """
    try:
        with open(path, encoding="utf-8-sig") as file:
            return file.read().splitlines()
    except FileNotFoundError:
        raise IdeasFileError(f"файл «{path}» не найден — проверь путь")
    except IsADirectoryError:
        raise IdeasFileError(f"«{path}» — это папка, а нужен файл с идеями")
    except UnicodeDecodeError:
        pass  # не UTF-8 — попробуем другую кодировку ниже

    try:
        with open(path, encoding="cp1251") as file:
            return file.read().splitlines()
    except UnicodeDecodeError:
        raise IdeasFileError(
            f"не получилось прочитать «{path}»: сохрани файл в кодировке UTF-8"
        )


def read_ideas(path: str) -> tuple[list[Idea], dict[int, str]]:
    """Читает файл с идеями.

    Возвращает:
    - список идей, которые получилось разобрать;
    - словарь предупреждений {номер строки: текст} про строки, которые пришлось пропустить.

    Повторы НЕ пропускаются: одинаковая идея — это следующая «часть» (решает storage.py).
    """
    lines = read_lines(path)

    # Файл из TextEdit по умолчанию сохраняется в RTF (текст с оформлением) и начинается с «{\rtf».
    # Служебные строки RTF нельзя принимать за идеи — просим сохранить обычным текстом.
    if lines and lines[0].lstrip().startswith("{\\rtf"):
        raise IdeasFileError(
            f"«{path}» — файл RTF (текст с оформлением), а нужен обычный текст. "
            f"В TextEdit: Формат → Конвертировать в простой текст, и сохрани как .txt"
        )

    ideas = []
    warnings = {}

    for line_no, raw_line in enumerate(lines, start=1):
        try:
            idea = parse_line(raw_line, line_no)
        except ValueError as error:
            warnings[line_no] = str(error)
            continue

        if idea is not None:
            ideas.append(idea)

    return ideas, warnings

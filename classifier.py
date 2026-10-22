"""Рубрики и форматы.

По словам-сигналам из rules.json находит, в какие рубрики попадает идея,
и превращает идею в единицы контента: каждая пара «рубрика + формат» — отдельная единица.

Как сравниваются слова:
- слово-сигнал — это НАЧАЛО слова: «собира» находит «собираюсь», «собиралась»;
- короткие сигналы (1–2 буквы: «wb», «xl», «с») сравниваются со словом ЦЕЛИКОМ;
- фраза из нескольких слов («больш низ») ищется как слова, стоящие ПОДРЯД.
"""

import json

from models import ContentUnit, Idea
from reader import normalize

SHORT_KEY = 2    # сигналы такой длины и короче сравниваются со словом целиком
MIN_MATCHES = 1  # сколько слов-сигналов должно найтись, чтобы рубрика подошла


class RulesError(Exception):
    """Файл с правилами нельзя прочитать или в нём ошибка."""


# ---------- загрузка и проверка правил ----------

def load_rules(path: str) -> dict:
    """Читает rules.json и проверяет, что в нём нет ошибок."""
    try:
        with open(path, encoding="utf-8") as file:
            rules = json.load(file)
    except FileNotFoundError:
        raise RulesError(f"файл с правилами «{path}» не найден")
    except json.JSONDecodeError as error:
        raise RulesError(
            f"{path}, строка {error.lineno}: ошибка в записи — проверь запятые, кавычки и скобки"
        )

    check_rules(rules)
    return rules


def check_rules(rules: dict) -> None:
    """Проверяет, что правила заполнены правильно. Если нет — бросает RulesError."""
    for section in ("rubrics", "no_rubric", "formats"):
        if section not in rules:
            raise RulesError(f"в rules.json нет раздела «{section}»")

    for name, rubric in rules["rubrics"].items():
        keywords = rubric.get("keywords", [])
        if not keywords:
            raise RulesError(f"у рубрики «{name}» нет слов-сигналов (keywords)")
        for keyword in keywords:
            if normalize(keyword) == "":
                raise RulesError(f"у рубрики «{name}» есть пустое слово-сигнал «{keyword}»")
        check_formats(name, rubric.get("formats", []), rules["formats"])

    check_formats("Без рубрики", rules["no_rubric"].get("formats", []), rules["formats"])


def check_formats(owner: str, formats: list[str], known_formats: dict) -> None:
    """Проверяет, что у рубрики есть форматы и все они описаны в разделе formats."""
    if not formats:
        raise RulesError(f"у «{owner}» не указаны форматы")
    for format_name in formats:
        if format_name not in known_formats:
            raise RulesError(
                f"у «{owner}» указан формат «{format_name}», которого нет в разделе formats — "
                f"проверь, как он написан"
            )


# ---------- поиск слов-сигналов ----------

def word_matches(word: str, key_part: str) -> bool:
    """Подходит ли одно слово идеи к одному слову сигнала.

    word_matches("собираюсь", "собира") -> True   (начало совпало)
    word_matches("вбить", "вб")         -> False  (короткий сигнал — нужно совпадение целиком)
    """
    if len(key_part) <= SHORT_KEY:
        return word == key_part
    return word.startswith(key_part)


def keyword_found(words: list[str], keyword: str) -> bool:
    """Есть ли сигнал (слово или фраза) среди слов идеи.

    Фраза ищется как слова, стоящие подряд и в том же порядке.
    """
    parts = normalize(keyword).split()  # «больш низ» -> ["больш", "низ"]

    for start in range(len(words) - len(parts) + 1):
        if all(word_matches(words[start + i], part) for i, part in enumerate(parts)):
            return True
    return False


def find_rubrics(idea: Idea, rules: dict) -> dict[str, list[str]]:
    """Находит все рубрики, которые подходят идее.

    Возвращает словарь {название рубрики: список совпавших слов-сигналов}.
    Рубрики, где совпадений меньше MIN_MATCHES, в словарь не попадают.
    """
    words = idea.key.split()
    found = {}

    for name, rubric in rules["rubrics"].items():
        matched = [keyword for keyword in rubric["keywords"] if keyword_found(words, keyword)]
        if len(matched) >= MIN_MATCHES:
            found[name] = matched

    return found


# ---------- идея -> единицы контента ----------

def make_units(idea: Idea, rules: dict) -> list[ContentUnit]:
    """Превращает идею в единицы контента: по одной на каждую пару «рубрика + формат».

    Если ни одна рубрика не подошла — берём форматы из раздела no_rubric.
    """
    found = find_rubrics(idea, rules)
    units = []

    if found:
        for rubric_name, matched in found.items():
            for format_name in rules["rubrics"][rubric_name]["formats"]:
                units.append(build_unit(idea, rubric_name, format_name, matched, rules))
    else:
        no_rubric = rules["no_rubric"]
        for format_name in no_rubric["formats"]:
            units.append(build_unit(idea, no_rubric["name"], format_name, [], rules))

    return units


def build_unit(idea: Idea, rubric: str, format_name: str, matched: list[str], rules: dict) -> ContentUnit:
    """Собирает одну единицу контента. Площадки берутся из раздела formats."""
    return ContentUnit(
        idea=idea,
        rubric=rubric,
        format_name=format_name,
        platforms=rules["formats"][format_name]["platforms"],
        matched=matched,
    )

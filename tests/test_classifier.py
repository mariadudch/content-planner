"""Тесты для classifier.py. Запуск из папки проекта: pytest"""

import json
from pathlib import Path

import pytest

from classifier import (
    RulesError,
    check_rules,
    find_rubrics,
    keyword_found,
    load_rules,
    make_units,
    word_matches,
)
from reader import parse_line

# Маленькие «игрушечные» правила только для тестов. Тесты не зависят от настоящего
# rules.json: его ты будешь менять, а тесты должны проверять логику, а не твои слова.
RULES = {
    "rubrics": {
        "Рутина": {"keywords": ["сбор", "утр"], "formats": ["Рилс", "Сторис"]},
        "Бьюти": {"keywords": ["крем", "тоник", "вб"], "formats": ["Рилс", "Карусель"]},
        "Фигура": {"keywords": ["больш низ", "с форм"], "formats": ["Карусель"]},
    },
    "no_rubric": {"name": "Без рубрики", "formats": ["Сторис"]},
    "formats": {
        "Рилс": {"platforms": ["Instagram", "TikTok"], "per_week": 5, "per_day": 1},
        "Сторис": {"platforms": ["Instagram"], "per_day": 2},
        "Карусель": {"platforms": ["Instagram", "VK"]},
    },
    "planning": {"horizon_days": 28},
}


def words(text: str) -> list[str]:
    """Помощник: текст -> нормализованные слова, как у идеи."""
    return parse_line(text, 1).key.split()


# ---------- word_matches ----------

@pytest.mark.parametrize(
    "word, key_part, expected",
    [
        ("собираюсь", "собира", True),   # начало совпало
        ("сбор", "сбор", True),           # совпало целиком
        ("разбор", "сбор", False),        # «сбор» внутри слова, а не в начале
        ("вб", "вб", True),               # короткий сигнал — целиком
        ("вбить", "вб", False),           # короткий сигнал — начала мало
        ("с", "с", True),
        ("спортивная", "с", False),
    ],
)
def test_word_matches(word, key_part, expected):
    assert word_matches(word, key_part) is expected


# ---------- keyword_found ----------

def test_keyword_found_single_word():
    assert keyword_found(words("Купила новый крем для рук"), "крем") is True


def test_keyword_found_phrase_in_a_row():
    assert keyword_found(words("Образы на фигуру с большим низом"), "больш низ") is True


def test_keyword_found_phrase_words_far_apart():
    assert keyword_found(words("Купила большую сумку, а низ у неё грязный"), "больш низ") is False


def test_keyword_found_phrase_wrong_order():
    assert keyword_found(words("Низ у платья большой"), "больш низ") is False


def test_keyword_found_phrase_with_short_part():
    assert keyword_found(words("Образы для девушек с формами"), "с форм") is True
    assert keyword_found(words("Новая спортивная форма"), "с форм") is False


def test_keyword_found_phrase_longer_than_idea():
    # во фразе 3 слова, в идее 2 — не должно быть ошибки, просто «не нашлось»
    assert keyword_found(["вечерний", "уход"], "не нрав себ") is False


def test_keyword_found_yo_in_rules():
    # если в rules.json случайно написать «ё», всё равно сработает
    assert keyword_found(words("Ещё один крем"), "ещё") is True


# ---------- find_rubrics ----------

def test_find_rubrics_several():
    idea = parse_line("Утренний уход: тоник и крем", 1)
    found = find_rubrics(idea, RULES)
    assert found == {"Рутина": ["утр"], "Бьюти": ["крем", "тоник"]}


def test_find_rubrics_none():
    idea = parse_line("Купила новую кружку", 1)
    assert find_rubrics(idea, RULES) == {}


# ---------- make_units ----------

def test_make_units_every_pair_rubric_format():
    idea = parse_line("Утренний уход: тоник и крем", 1)
    units = make_units(idea, RULES)
    pairs = [(unit.rubric, unit.format_name) for unit in units]
    # Рутина: Рилс, Сторис; Бьюти: Рилс, Карусель — два рилса, по одному на рубрику
    assert pairs == [
        ("Рутина", "Рилс"),
        ("Рутина", "Сторис"),
        ("Бьюти", "Рилс"),
        ("Бьюти", "Карусель"),
    ]


def test_make_units_platforms_and_matched():
    idea = parse_line("Нашла крем на ВБ", 1)
    units = make_units(idea, RULES)
    assert units[0].platforms == ["Instagram", "TikTok"]
    assert units[0].matched == ["крем", "вб"]
    assert units[0].idea is idea


def test_make_units_no_rubric():
    idea = parse_line("Купила новую кружку", 1)
    units = make_units(idea, RULES)
    assert len(units) == 1
    assert units[0].rubric == "Без рубрики"
    assert units[0].format_name == "Сторис"
    assert units[0].matched == []


# ---------- проверка правил ----------

def test_check_rules_ok():
    check_rules(RULES)  # не должно быть ошибки


def test_check_rules_unknown_format():
    bad = json.loads(json.dumps(RULES))  # копия правил, чтобы не испортить RULES
    bad["rubrics"]["Бьюти"]["formats"] = ["Рилз"]  # опечатка
    with pytest.raises(RulesError, match="Рилз"):
        check_rules(bad)


def test_check_rules_empty_keyword():
    bad = json.loads(json.dumps(RULES))
    bad["rubrics"]["Бьюти"]["keywords"].append("!!!")
    with pytest.raises(RulesError, match="пустое"):
        check_rules(bad)


def test_check_rules_missing_section():
    bad = json.loads(json.dumps(RULES))
    del bad["no_rubric"]
    with pytest.raises(RulesError, match="no_rubric"):
        check_rules(bad)


@pytest.mark.parametrize("bad_value", [0, -1, "5", 2.5, True, None])
def test_check_rules_bad_limit(bad_value):
    bad = json.loads(json.dumps(RULES))
    bad["formats"]["Рилс"]["per_week"] = bad_value
    with pytest.raises(RulesError, match="per_week"):
        check_rules(bad)


def test_check_rules_bad_horizon():
    bad = json.loads(json.dumps(RULES))
    bad["planning"]["horizon_days"] = 0
    with pytest.raises(RulesError, match="horizon_days"):
        check_rules(bad)


def test_load_rules_broken_json(tmp_path):
    file = tmp_path / "rules.json"
    file.write_text('{\n  "rubrics": {\n    "Бьюти": ["крем" "тоник"]\n  }\n}', encoding="utf-8")
    with pytest.raises(RulesError, match="строка 3"):
        load_rules(str(file))


def test_load_rules_missing_file():
    with pytest.raises(RulesError, match="не найден"):
        load_rules("нет_такого_файла.json")


def test_real_rules_file_is_valid():
    # Настоящий rules.json проекта читается без ошибок.
    # Если после твоих правок этот тест упал — значит, в rules.json опечатка.
    rules_path = Path(__file__).parent.parent / "rules.json"
    load_rules(str(rules_path))

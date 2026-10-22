"""Тесты для reader.py. Запуск из папки проекта: python3 -m pytest"""

import pytest

from reader import (
    IdeasFileError,
    normalize,
    parse_line,
    read_ideas,
    strip_bullet,
)


# ---------- normalize ----------

def test_normalize_lowercase_and_yo():
    assert normalize("Ещё КРЕМ") == "еще крем"


def test_normalize_removes_punctuation_and_emoji():
    assert normalize("Крем!!! ✨ — топ,  правда?") == "крем топ правда"


def test_normalize_empty_for_separator():
    assert normalize("---") == ""


# ---------- strip_bullet ----------

@pytest.mark.parametrize(
    "line, expected",
    [
        ("- идея", "идея"),
        ("• идея", "идея"),
        ("1. идея", "идея"),
        ("12) идея", "идея"),
        ("идея без маркера", "идея без маркера"),
        ("15 минут на макияж", "15 минут на макияж"),  # число без точки — не маркер
    ],
)
def test_strip_bullet(line, expected):
    assert strip_bullet(line) == expected


# ---------- parse_line ----------

def test_parse_line_normal():
    idea = parse_line("- ! Вечерний уход за кожей", 5)
    assert idea.text == "Вечерний уход за кожей"
    assert idea.key == "вечерний уход за кожей"
    assert idea.line_no == 5
    assert idea.urgent is True


def test_parse_line_hashtag_is_just_a_word():
    idea = parse_line("Нашла крем #уход", 1)
    assert idea.text == "Нашла крем #уход"  # в тексте хештег остаётся как был
    assert idea.key == "нашла крем уход"    # а для сравнения это просто слово «уход»


def test_parse_line_empty_and_separators_return_none():
    assert parse_line("", 1) is None
    assert parse_line("   ", 1) is None
    assert parse_line("---", 1) is None
    assert parse_line("✨✨✨", 1) is None


def test_parse_line_too_short_raises():
    with pytest.raises(ValueError, match="строка 3"):
        parse_line("крем", 3)


# ---------- read_ideas ----------

def test_read_ideas_keeps_duplicates(tmp_path):
    # Повторы не пропускаются: это будущие «части» (их номер ставит ContentPlan)
    file = tmp_path / "ideas.txt"
    file.write_text(
        "Поняла, что ухоженность — это ещё и регулярность\n"
        "\n"
        "поняла что ухоженность это еще и регулярность\n",
        encoding="utf-8",
    )
    ideas, warnings = read_ideas(str(file))
    assert len(ideas) == 2
    assert ideas[0].key == ideas[1].key
    assert warnings == {}


def test_read_ideas_warnings_by_line_number(tmp_path):
    file = tmp_path / "ideas.txt"
    file.write_text("Вечерний уход за кожей\nкрем\n---\n", encoding="utf-8")
    ideas, warnings = read_ideas(str(file))
    assert len(ideas) == 1
    assert list(warnings.keys()) == [2]  # строка 2 — «крем», строка 3 — разделитель, о нём молчим
    assert "слишком коротко" in warnings[2]


def test_read_ideas_line_numbers_count_empty_lines(tmp_path):
    file = tmp_path / "ideas.txt"
    file.write_text("\n\nВечерний уход за кожей\n", encoding="utf-8")
    ideas, _ = read_ideas(str(file))
    assert ideas[0].line_no == 3


def test_read_ideas_cp1251(tmp_path):
    file = tmp_path / "ideas.txt"
    file.write_bytes("Вечерний уход за кожей\n".encode("cp1251"))
    ideas, _ = read_ideas(str(file))
    assert ideas[0].text == "Вечерний уход за кожей"


def test_read_ideas_utf8_with_bom(tmp_path):
    file = tmp_path / "ideas.txt"
    file.write_bytes("Вечерний уход за кожей\n".encode("utf-8-sig"))
    ideas, _ = read_ideas(str(file))
    assert ideas[0].text == "Вечерний уход за кожей"  # без невидимого символа BOM в начале


def test_read_ideas_rtf_file(tmp_path):
    # Так выглядит пустой файл, сохранённый в TextEdit на Mac
    file = tmp_path / "ideas.rtf"
    file.write_text(
        "{\\rtf1\\ansi\\ansicpg1251\\cocoartf2761\n"
        "\\paperw11900\\paperh16840\\margl1440\\margr1440\\vieww28600\\viewh15380\\viewkind0\n"
        "}\n",
        encoding="utf-8",
    )
    with pytest.raises(IdeasFileError, match="RTF"):
        read_ideas(str(file))


def test_read_ideas_missing_file():
    with pytest.raises(IdeasFileError, match="не найден"):
        read_ideas("нет_такого_файла.txt")


def test_read_ideas_directory(tmp_path):
    with pytest.raises(IdeasFileError, match="папка"):
        read_ideas(str(tmp_path))

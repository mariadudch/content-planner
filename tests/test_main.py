"""Тесты команд main.py. Запуск из папки проекта: pytest

monkeypatch — помощник pytest: на время теста подменяет пути в main.py на временную папку,
чтобы тесты не трогали твою настоящую папку data/. После теста всё возвращается как было.
"""

import argparse

import pytest

import main
from storage import load_plan


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    """Временная папка data/ вместо настоящей."""
    folder = tmp_path / "data"
    folder.mkdir()
    monkeypatch.setattr(main, "DATA_DIR", folder)
    monkeypatch.setattr(main, "INBOX_PATH", folder / "ideas.txt")
    monkeypatch.setattr(main, "STATE_PATH", folder / "state.json")
    monkeypatch.setattr(main, "CSV_PATH", folder / "plan.csv")
    monkeypatch.setattr(main, "PROJECT_DIR", tmp_path)
    return folder


# ---------- разбор команд ----------

def test_parser_commands():
    parser = main.build_parser()
    assert parser.parse_args(["run"]).command == "run"
    assert parser.parse_args(["add", "Нашла тинт"]).text == "Нашла тинт"
    assert parser.parse_args(["show", "--days", "7"]).days == 7
    assert parser.parse_args(["show"]).days is None
    assert parser.parse_args(["preview", "examples/ideas_demo.txt"]).path == "examples/ideas_demo.txt"


def test_parser_without_command_exits():
    with pytest.raises(SystemExit):
        main.build_parser().parse_args([])


def test_positive_int():
    assert main.positive_int("7") == 7
    with pytest.raises(argparse.ArgumentTypeError):
        main.positive_int("0")
    with pytest.raises(argparse.ArgumentTypeError):
        main.positive_int("неделя")


# ---------- команды целиком ----------

def test_run_processes_inbox(data_dir):
    (data_dir / "ideas.txt").write_text("Мой вечерний уход: тоник и крем\nкрем\n", encoding="utf-8")
    main.main(["run"])

    plan, _ = load_plan(data_dir / "state.json")
    assert len(plan.ideas) == 1
    assert all(unit.date for unit in plan.units)  # всем единицам нашлось место
    assert (data_dir / "plan.csv").exists()
    assert (data_dir / "ideas.txt").read_text(encoding="utf-8") == "крем\n"  # осталась только проблемная строка


def test_run_without_inbox_file(data_dir):
    main.main(["run"])  # файла ideas.txt нет — не падаем
    assert (data_dir / "state.json").exists()


def test_add_then_repeat_is_part_2(data_dir):
    main.main(["add", "Мой вечерний уход"])
    main.main(["add", "мой вечерний уход!"])
    plan, _ = load_plan(data_dir / "state.json")
    assert [idea.part for idea in plan.ideas] == [1, 2]


def test_add_too_short_saves_nothing(data_dir):
    main.main(["add", "крем"])
    assert not (data_dir / "state.json").exists()


def test_preview_saves_nothing(data_dir):
    main.main(["preview", str(main.Path(__file__).parent.parent / "examples" / "ideas_demo.txt")])
    assert list(data_dir.iterdir()) == []


def test_broken_rules_message(data_dir, monkeypatch, tmp_path, capsys):
    broken = tmp_path / "rules.json"
    broken.write_text("{ сломано", encoding="utf-8")
    monkeypatch.setattr(main, "RULES_PATH", broken)
    main.main(["show"])
    assert "Ошибка" in capsys.readouterr().out

"""Тесты команд main.py. Запуск из папки проекта: pytest

monkeypatch — помощник pytest: на время теста подменяет пути в main.py на временную папку,
чтобы тесты не трогали твою настоящую папку data/. После теста всё возвращается как было.
"""

import argparse
import json
from datetime import date, timedelta

import pytest

import main
from models import ContentUnit
from reader import parse_line
from storage import ContentPlan, load_plan, save_plan


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
    # ВАЖНО: иначе тесты отправляли бы план в твою настоящую Google Таблицу
    monkeypatch.setattr(main, "GOOGLE_SETTINGS_PATH", folder / "google.json")
    monkeypatch.setattr(main, "GOOGLE_KEY_PATH", folder / "google_key.json")
    monkeypatch.setattr(main, "ARCHIVE_PATH", folder / "archive.json")
    return folder


# ---------- разбор команд ----------

def test_parser_commands():
    parser = main.build_parser()
    assert parser.parse_args(["run"]).command == "run"
    assert parser.parse_args(["add", "Нашла тинт"]).text == "Нашла тинт"
    assert parser.parse_args(["show", "--days", "7"]).days == 7
    assert parser.parse_args(["show"]).days is None
    assert parser.parse_args(["preview", "examples/ideas_demo.txt"]).path == "examples/ideas_demo.txt"
    assert parser.parse_args(["sync"]).command == "sync"


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


def test_sync_without_google_settings(data_dir, capsys):
    main.main(["sync"])
    assert "не настроена" in capsys.readouterr().out


def test_sync_with_settings_but_without_key(data_dir, capsys):
    (data_dir / "google.json").write_text(
        '{"spreadsheet_url": "https://docs.google.com/spreadsheets/d/abc/edit", "worksheet": "План"}',
        encoding="utf-8",
    )
    main.main(["sync"])
    out = capsys.readouterr().out
    assert "нет ключа доступа" in out          # понятная причина
    assert "сохранён в state.json" in out      # и успокаивающее «ничего не потеряно»


# ---------- archive (этап 7) ----------

def test_archive_days_minimum():
    assert main.archive_days("60") == 60
    with pytest.raises(argparse.ArgumentTypeError, match="минимум"):
        main.archive_days("10")
    with pytest.raises(SystemExit):
        main.build_parser().parse_args(["archive", "--days", "10"])
    assert main.build_parser().parse_args(["archive"]).days == 60


def test_archive_command(data_dir):
    long_ago = (date.today() - timedelta(days=90)).isoformat()
    soon = (date.today() + timedelta(days=3)).isoformat()
    plan = ContentPlan()
    for text, unit_date in [("Старая идея про уход", long_ago), ("Идея на будущее про тинт", soon)]:
        idea = parse_line(text, 1)
        unit = ContentUnit(idea=idea, rubric="Бьюти", format_name="Рилс", platforms=[], matched=[], date=unit_date)
        plan.add(idea, [unit], "2026-07-01")
    save_plan(plan, data_dir / "state.json")

    main.main(["archive"])

    plan, _ = load_plan(data_dir / "state.json")
    assert [idea.text for idea in plan.ideas] == ["Идея на будущее про тинт"]
    archive = json.loads((data_dir / "archive.json").read_text(encoding="utf-8"))
    assert [record["text"] for record in archive["ideas"]] == ["Старая идея про уход"]
    assert (data_dir / "plan.csv").exists()  # таблица обновилась без архивных строк


def test_archive_nothing_to_do(data_dir, capsys):
    main.main(["archive"])
    assert "Архивировать нечего" in capsys.readouterr().out
    assert not (data_dir / "archive.json").exists()

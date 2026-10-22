"""Тесты для storage.py. Запуск из папки проекта: pytest"""

from models import ContentUnit
from reader import parse_line
from storage import (
    ContentPlan,
    clean_inbox,
    load_plan,
    save_plan,
)

TODAY = "2026-10-22"


def unit_for(idea, rubric="Бьюти", format_name="Рилс"):
    """Помощник: одна единица контента для идеи."""
    return ContentUnit(
        idea=idea,
        rubric=rubric,
        format_name=format_name,
        platforms=["Instagram"],
        matched=["крем"],
    )


def add_idea(plan, text):
    """Помощник: разобрать строку и добавить её в план с одной единицей контента."""
    idea = parse_line(text, 1)
    plan.add(idea, [unit_for(idea)], TODAY)
    return idea


# ---------- ContentPlan: части ----------

def test_first_time_is_part_1_without_mark():
    plan = ContentPlan()
    idea = add_idea(plan, "Мой вечерний уход")
    assert idea.part == 1
    assert idea.title() == "Мой вечерний уход"
    assert idea.added == TODAY


def test_repeats_become_part_2_and_3():
    plan = ContentPlan()
    add_idea(plan, "Мой вечерний уход")
    second = add_idea(plan, "мой ВЕЧЕРНИЙ уход!")  # тот же текст после нормализации
    third = add_idea(plan, "Мой вечерний уход")
    assert second.part == 2
    assert third.part == 3
    assert third.title() == "Мой вечерний уход — часть 3"


def test_different_idea_starts_from_part_1():
    plan = ContentPlan()
    add_idea(plan, "Мой вечерний уход")
    other = add_idea(plan, "Мой утренний уход")
    assert other.part == 1


def test_units_of_returns_only_this_idea_units():
    plan = ContentPlan()
    first = add_idea(plan, "Мой вечерний уход")
    second = add_idea(plan, "Мой вечерний уход")  # часть 2 — тот же текст, но другая идея
    assert len(plan.units_of(first)) == 1
    assert plan.units_of(first)[0].idea is first
    assert plan.units_of(second)[0].idea is second


# ---------- сохранение и загрузка ----------

def test_save_and_load_keep_everything(tmp_path):
    path = tmp_path / "state.json"
    plan = ContentPlan()
    add_idea(plan, "! Мой вечерний уход")
    add_idea(plan, "Мой вечерний уход")
    save_plan(plan, path)

    loaded, warning = load_plan(path)
    assert warning == ""
    assert [idea.title() for idea in loaded.ideas] == ["Мой вечерний уход", "Мой вечерний уход — часть 2"]
    assert loaded.ideas[0].urgent is True
    assert loaded.ideas[0].added == TODAY
    assert len(loaded.units) == 2
    # единица контента снова «привязана» к своей идее
    assert loaded.units[1].idea is loaded.ideas[1]
    assert loaded.units[0].platforms == ["Instagram"]


def test_save_and_load_keep_dates(tmp_path):
    path = tmp_path / "state.json"
    plan = ContentPlan()
    add_idea(plan, "Мой вечерний уход")
    plan.units[0].date = "2026-10-24"
    save_plan(plan, path)
    loaded, _ = load_plan(path)
    assert loaded.units[0].date == "2026-10-24"


def test_load_old_state_without_dates(tmp_path):
    # Память, сохранённая на этапе 3, — у единиц ещё нет поля "date"
    path = tmp_path / "state.json"
    path.write_text(
        '{"ideas": [{"text": "Мой уход", "key": "мой уход", "line_no": 1, "urgent": false,'
        ' "part": 1, "added": "2026-10-22", "units": [{"rubric": "Бьюти", "format_name": "Рилс",'
        ' "platforms": ["Instagram"], "matched": ["уход"]}]}]}',
        encoding="utf-8",
    )
    plan, warning = load_plan(path)
    assert warning == ""
    assert plan.units[0].date == ""  # считается «в бэклоге» — планировщик поставит дату


def test_parts_continue_after_reload(tmp_path):
    path = tmp_path / "state.json"
    plan = ContentPlan()
    add_idea(plan, "Мой вечерний уход")
    save_plan(plan, path)

    loaded, _ = load_plan(path)
    again = add_idea(loaded, "Мой вечерний уход")
    assert again.part == 2  # программа «помнит» прошлый запуск


def test_load_missing_file_is_empty_plan(tmp_path):
    plan, warning = load_plan(tmp_path / "state.json")
    assert plan.ideas == []
    assert warning == ""


def test_load_broken_file(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("{ это не JSON", encoding="utf-8")

    plan, warning = load_plan(path)
    assert plan.ideas == []
    assert "повреждён" in warning
    assert not path.exists()                                # испорченный файл убран с дороги...
    assert (tmp_path / "state.broken.json").exists()        # ...но сохранён под другим именем


def test_load_wrong_structure_is_also_broken(tmp_path):
    path = tmp_path / "state.json"
    path.write_text('{"ideas": [{"text": "без остальных полей"}]}', encoding="utf-8")
    plan, warning = load_plan(path)
    assert plan.ideas == []
    assert "повреждён" in warning


def test_save_creates_folder_and_leaves_no_temp_file(tmp_path):
    path = tmp_path / "data" / "state.json"  # папки data ещё нет
    save_plan(ContentPlan(), path)
    assert path.exists()
    assert list(path.parent.iterdir()) == [path]  # временного .tmp не осталось


# ---------- файл с идеями как «входящие» ----------

def test_clean_inbox_keeps_only_given_lines(tmp_path):
    file = tmp_path / "ideas.txt"
    file.write_text("идея один\nкрем\n\nидея два\nтушь\n", encoding="utf-8")
    clean_inbox(str(file), [2, 5])
    assert file.read_text(encoding="utf-8") == "крем\nтушь\n"


def test_clean_inbox_everything_processed(tmp_path):
    file = tmp_path / "ideas.txt"
    file.write_text("идея один\nидея два\n", encoding="utf-8")
    clean_inbox(str(file), [])
    assert file.read_text(encoding="utf-8") == ""

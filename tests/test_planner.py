"""Тесты для planner.py. Запуск из папки проекта: pytest"""

from datetime import date

from models import ContentUnit
from planner import backlog, can_place, same_period, schedule, units_by_day
from reader import parse_line
from storage import ContentPlan

MONDAY = date(2026, 10, 26)  # понедельник — удобно считать недели

# Игрушечные лимиты только для тестов (настоящие — в rules.json)
FORMATS = {
    "Рилс": {"platforms": ["Instagram"], "per_week": 5, "per_day": 1},
    "Сторис": {"platforms": ["Instagram"], "per_day": 2},
    "Влог": {"platforms": ["YouTube"], "per_month": 2},
}


def add(plan, text, units_spec, date_=""):
    """Помощник: добавить идею с единицами [(формат, рубрика), ...] в план."""
    idea = parse_line(text, 1)
    units = [
        ContentUnit(idea=idea, rubric=rubric, format_name=fmt, platforms=[], matched=[], date=date_)
        for fmt, rubric in units_spec
    ]
    plan.add(idea, units, "2026-10-25")
    return units


def dates(units):
    return [unit.date for unit in units]


# ---------- same_period ----------

def test_same_period():
    sunday = date(2026, 11, 1)
    assert same_period(MONDAY, MONDAY, "per_day") is True
    assert same_period(MONDAY, sunday, "per_week") is True            # пн 26.10 и вс 01.11 — одна неделя
    assert same_period(MONDAY, date(2026, 11, 2), "per_week") is False  # следующий понедельник
    assert same_period(MONDAY, sunday, "per_month") is False          # октябрь и ноябрь


# ---------- лимиты ----------

def test_per_day_limit():
    plan = ContentPlan()
    first = add(plan, "Идея один про уход", [("Рилс", "Бьюти")])
    second = add(plan, "Идея два про образ", [("Рилс", "Одежда")])
    schedule(plan, FORMATS, MONDAY, 28)
    assert dates(first + second) == ["2026-10-26", "2026-10-27"]  # 1 рилс в день


def test_per_day_limit_two_stories():
    plan = ContentPlan()
    units = []
    for number, rubric in enumerate(["А", "Б", "В"]):
        units += add(plan, f"Идея номер {number}", [("Сторис", rubric)])
    schedule(plan, FORMATS, MONDAY, 28)
    assert dates(units) == ["2026-10-26", "2026-10-26", "2026-10-27"]  # 2 сторис в день


def test_per_week_limit():
    plan = ContentPlan()
    units = []
    for number in range(6):
        units += add(plan, f"Идея номер {number}", [("Рилс", f"Рубрика {number}")])
    schedule(plan, FORMATS, MONDAY, 28)
    # 5 рилсов на неделе пн–пт, шестой — только в следующий понедельник (сб и вс — та же неделя)
    assert dates(units)[:5] == ["2026-10-26", "2026-10-27", "2026-10-28", "2026-10-29", "2026-10-30"]
    assert units[5].date == "2026-11-02"


def test_per_month_limit():
    plan = ContentPlan()
    units = []
    for number in range(3):
        units += add(plan, f"Идея номер {number}", [("Влог", f"Рубрика {number}")])
    schedule(plan, FORMATS, MONDAY, 28)
    # два влога в октябре, третий — 1 ноября. Дневного лимита у влога нет — поэтому оба
    # октябрьских встают в один день (26-го). Хочешь иначе — добавь влогу "per_day": 1 в rules.json
    assert dates(units) == ["2026-10-26", "2026-10-26", "2026-11-01"]


def test_past_units_count_for_week_limit():
    plan = ContentPlan()
    # на этой неделе уже стоят 5 рилсов (даты назначены раньше)
    week = ["2026-10-26", "2026-10-27", "2026-10-28", "2026-10-29", "2026-10-30"]
    for number, day in enumerate(week):
        add(plan, f"Старая идея {number}", [("Рилс", f"Р{number}")], date_=day)
    new = add(plan, "Новая идея про уход", [("Рилс", "Новая")])
    schedule(plan, FORMATS, date(2026, 10, 31), 28)  # планируем с субботы
    assert new[0].date == "2026-11-02"  # сб и вс заняты лимитом недели → понедельник


# ---------- чередование тем ----------

def test_rotation_same_format_same_rubric_not_next_day():
    plan = ContentPlan()
    first = add(plan, "Идея один про уход", [("Сторис", "Бьюти")])
    second = add(plan, "Идея два про крем", [("Сторис", "Бьюти")])
    schedule(plan, FORMATS, MONDAY, 28)
    # в один день можно (лимит 2), а вот «вчера/завтра» — нельзя; поэтому второй — тот же день
    assert dates(first + second) == ["2026-10-26", "2026-10-26"]


def test_rotation_blocks_neighbour_days():
    plan = ContentPlan()
    first = add(plan, "Идея один про уход", [("Рилс", "Бьюти")])
    second = add(plan, "Идея два про крем", [("Рилс", "Бьюти")])
    schedule(plan, FORMATS, MONDAY, 28)
    # пн — первый; вт — нельзя (вчера был рилс «Бьюти»); ср — можно
    assert dates(first + second) == ["2026-10-26", "2026-10-28"]


def test_rotation_checks_both_sides():
    plan = ContentPlan()
    add(plan, "Старая идея про крем", [("Рилс", "Бьюти")], date_="2026-10-28")  # уже стоит в среду
    new = add(plan, "Новая идея про тоник", [("Рилс", "Бьюти")])
    schedule(plan, FORMATS, MONDAY, 28)
    # пн — можно (среда не соседний день); вт — уже нельзя бы (завтра среда)
    assert new[0].date == "2026-10-26"
    tuesday = date(2026, 10, 27)
    assert can_place(new[0], tuesday, [u for u in plan.units if u.date and u is not new[0]], FORMATS["Рилс"]) is False


# ---------- единицы одной идеи ----------

def test_units_of_one_idea_not_same_day():
    plan = ContentPlan()
    units = add(plan, "Мой вечерний уход", [("Рилс", "Бьюти"), ("Сторис", "Рутина"), ("Влог", "Рутина")])
    schedule(plan, FORMATS, MONDAY, 28)
    assert dates(units) == ["2026-10-26", "2026-10-27", "2026-10-28"]


def test_parts_are_different_ideas():
    plan = ContentPlan()
    first = add(plan, "Мой вечерний уход", [("Сторис", "Рутина")])
    second = add(plan, "Мой вечерний уход", [("Сторис", "Другая")])  # часть 2
    schedule(plan, FORMATS, MONDAY, 28)
    assert dates(first + second) == ["2026-10-26", "2026-10-26"]  # части — разные идеи


# ---------- очередь и стабильность ----------

def test_urgent_goes_first():
    plan = ContentPlan()
    usual = add(plan, "Обычная идея про уход", [("Рилс", "Бьюти")])
    urgent = add(plan, "! Срочная идея про образ", [("Рилс", "Одежда")])
    schedule(plan, FORMATS, MONDAY, 28)
    assert urgent[0].date == "2026-10-26"
    assert usual[0].date == "2026-10-27"


def test_scheduled_dates_do_not_move():
    plan = ContentPlan()
    old = add(plan, "Старая идея про уход", [("Рилс", "Бьюти")], date_="2026-10-30")
    schedule(plan, FORMATS, MONDAY, 28)
    assert old[0].date == "2026-10-30"


def test_beyond_horizon_goes_to_backlog():
    plan = ContentPlan()
    units = []
    for number in range(3):
        units += add(plan, f"Идея номер {number}", [("Рилс", f"Рубрика {number}")])
    schedule(plan, FORMATS, MONDAY, 2)  # горизонт — всего 2 дня
    assert dates(units) == ["2026-10-26", "2026-10-27", ""]
    assert backlog(plan) == [units[2]]


def test_backlog_gets_place_on_next_run():
    plan = ContentPlan()
    units = []
    for number in range(2):
        units += add(plan, f"Идея номер {number}", [("Рилс", f"Рубрика {number}")])
    schedule(plan, FORMATS, MONDAY, 1)
    assert units[1].date == ""
    schedule(plan, FORMATS, date(2026, 10, 27), 1)  # «следующий запуск» — на день позже
    assert units[1].date == "2026-10-27"


def test_unknown_format_stays_in_backlog_with_warning():
    plan = ContentPlan()
    units = add(plan, "Идея про подкаст", [("Подкаст", "Мысли")])
    warnings = schedule(plan, FORMATS, MONDAY, 28)
    assert units[0].date == ""
    assert "Подкаст" in warnings[0]


# ---------- вывод по дням ----------

def test_units_by_day_sorted_and_filtered():
    plan = ContentPlan()
    add(plan, "Идея номер один", [("Рилс", "А")], date_="2026-10-28")
    add(plan, "Идея номер два", [("Рилс", "Б")], date_="2026-10-26")
    add(plan, "Идея номер три", [("Рилс", "В")], date_="2026-12-01")  # за пределами окна
    add(plan, "Идея номер четыре", [("Рилс", "Г")])                   # в бэклоге
    days = units_by_day(plan, MONDAY, date(2026, 11, 1))
    assert list(days.keys()) == [date(2026, 10, 26), date(2026, 10, 28)]

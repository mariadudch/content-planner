"""Расстановка единиц контента по датам.

Алгоритм: берём единицы по очереди (сначала срочные, потом в порядке добавления)
и ставим каждую на БЛИЖАЙШИЙ день, где не нарушено ни одно правило:
1. лимиты формата: не больше N в день / в неделю / в месяц (точные правила — в rules.json);
2. чередование тем: один формат с одной рубрикой нельзя ставить 2 дня подряд;
3. единицы одной идеи — не в один день.
Не нашлось дня в пределах горизонта — единица остаётся в бэклоге (date = "")
и попробует найти место при следующем запуске.
Уже назначенные даты не двигаются.
"""

from datetime import date, timedelta

from models import ContentUnit
from storage import ContentPlan


# ---------- проверки одного дня ----------

def same_period(a: date, b: date, period: str) -> bool:
    """Попадают ли две даты в один день / одну неделю (пн–вс) / один месяц."""
    if period == "per_day":
        return a == b
    if period == "per_week":
        return a.isocalendar()[:2] == b.isocalendar()[:2]  # (год, номер недели)
    if period == "per_month":
        return (a.year, a.month) == (b.year, b.month)
    raise ValueError(f"неизвестный период: {period}")


def limit_reached(unit: ContentUnit, day: date, scheduled: list[ContentUnit], limits: dict) -> bool:
    """Достигнут ли лимит формата в этот день, неделю или месяц."""
    for period in ("per_day", "per_week", "per_month"):
        if period not in limits:
            continue  # такого лимита у формата нет
        count = 0
        for other in scheduled:
            if other.format_name == unit.format_name and same_period(date.fromisoformat(other.date), day, period):
                count += 1
        if count >= limits[period]:
            return True
    return False


def breaks_rotation(unit: ContentUnit, day: date, scheduled: list[ContentUnit]) -> bool:
    """Стоит ли накануне или на следующий день тот же формат с той же рубрикой."""
    for other in scheduled:
        if other.format_name == unit.format_name and other.rubric == unit.rubric:
            distance = abs((date.fromisoformat(other.date) - day).days)
            if distance == 1:
                return True
    return False


def same_idea_that_day(unit: ContentUnit, day: date, scheduled: list[ContentUnit]) -> bool:
    """Стоит ли в этот день уже другая единица из той же идеи."""
    for other in scheduled:
        if other.idea is unit.idea and date.fromisoformat(other.date) == day:
            return True
    return False


def can_place(unit: ContentUnit, day: date, scheduled: list[ContentUnit], limits: dict) -> bool:
    """Можно ли поставить единицу на этот день — все три правила соблюдены."""
    if limit_reached(unit, day, scheduled, limits):
        return False
    if breaks_rotation(unit, day, scheduled):
        return False
    if same_idea_that_day(unit, day, scheduled):
        return False
    return True


# ---------- расстановка ----------

def schedule(plan: ContentPlan, formats: dict, start: date, horizon_days: int) -> list[str]:
    """Ставит на даты все единицы плана, у которых ещё нет даты.

    formats — раздел formats из rules.json (там лимиты).
    start — первый день, на который можно ставить; horizon_days — на сколько дней вперёд.
    Возвращает предупреждения (например, про формат, которого больше нет в rules.json).
    """
    scheduled = [unit for unit in plan.units if unit.date]
    waiting = [unit for unit in plan.units if not unit.date]

    # Очередь: сначала срочные, потом остальные — внутри каждой группы в порядке добавления
    urgent = [unit for unit in waiting if unit.idea.urgent]
    usual = [unit for unit in waiting if not unit.idea.urgent]
    queue = urgent + usual

    days = [start + timedelta(days=i) for i in range(horizon_days)]
    warnings = []

    for unit in queue:
        limits = formats.get(unit.format_name)
        if limits is None:
            warnings.append(
                f"формата «{unit.format_name}» больше нет в rules.json — "
                f"«{unit.idea.title()}» остаётся в бэклоге"
            )
            continue

        for day in days:
            if can_place(unit, day, scheduled, limits):
                unit.date = day.isoformat()
                scheduled.append(unit)
                break

    return warnings


def backlog(plan: ContentPlan) -> list[ContentUnit]:
    """Единицы, которым пока не нашлось места в плане."""
    return [unit for unit in plan.units if not unit.date]


def units_by_day(plan: ContentPlan, first: date, last: date) -> dict[date, list[ContentUnit]]:
    """Единицы с датами от first до last включительно, сгруппированные по дням (по порядку)."""
    result = {}
    for unit in plan.units:
        if not unit.date:
            continue
        day = date.fromisoformat(unit.date)
        if first <= day <= last:
            result.setdefault(day, []).append(unit)
    return dict(sorted(result.items()))

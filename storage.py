"""Память программы: контент-план, который сохраняется между запусками.

- ContentPlan — всё, что программа помнит: идеи и их единицы контента.
- load_plan / save_plan — прочитать и сохранить память в JSON (data/state.json).
- clean_inbox — убрать из файла с идеями строки, которые уже попали в план.
- archive_old / append_to_archive — перенести давно прошедшие идеи в data/archive.json (этап 7).
"""

import json
import os
from pathlib import Path

from models import ContentUnit, Idea
from reader import read_lines


class ContentPlan:
    """Контент-план: все идеи, которые программа уже разобрала, и их единицы контента."""

    def __init__(self) -> None:
        self.ideas: list[Idea] = []
        self.units: list[ContentUnit] = []
        # Сколько раз каждая идея уже ушла в архив: {нормализованный текст: сколько раз}.
        # Нужно, чтобы после архивации нумерация частей продолжалась, а не начиналась заново.
        self.archived_parts: dict[str, int] = {}

    def times_seen(self, key: str) -> int:
        """Сколько раз идея с таким нормализованным текстом уже была: в плане + в архиве."""
        count = self.archived_parts.get(key, 0)
        for idea in self.ideas:
            if idea.key == key:
                count += 1
        return count

    def add(self, idea: Idea, units: list[ContentUnit], today: str) -> None:
        """Добавляет идею и её единицы контента в план.

        Если такая идея уже была — она становится следующей частью: 2, 3, ...
        """
        idea.part = self.times_seen(idea.key) + 1
        idea.added = today
        self.ideas.append(idea)
        self.units.extend(units)

    def units_of(self, idea: Idea) -> list[ContentUnit]:
        """Единицы контента, которые получились из этой идеи."""
        return [unit for unit in self.units if unit.idea is idea]

    def remove(self, idea: Idea) -> None:
        """Убирает идею и все её единицы контента из плана."""
        self.ideas = [other for other in self.ideas if other is not idea]
        self.units = [unit for unit in self.units if unit.idea is not idea]


# ---------- план <-> JSON ----------

def idea_to_dict(idea: Idea, units: list[ContentUnit]) -> dict:
    """Одна идея вместе с её единицами контента — в виде словаря для JSON.

    Единицы контента записываются внутрь своей идеи — так не нужно отдельно хранить,
    какая единица к какой идее относится. Используется и для памяти, и для архива.
    """
    unit_dicts = []
    for unit in units:
        unit_dicts.append({
            "rubric": unit.rubric,
            "format_name": unit.format_name,
            "platforms": unit.platforms,
            "matched": unit.matched,
            "date": unit.date,
        })
    return {
        "text": idea.text,
        "key": idea.key,
        "line_no": idea.line_no,
        "urgent": idea.urgent,
        "part": idea.part,
        "added": idea.added,
        "units": unit_dicts,
    }


def plan_to_dict(plan: ContentPlan) -> dict:
    """Превращает план в словарь, который можно записать в JSON."""
    ideas = [idea_to_dict(idea, plan.units_of(idea)) for idea in plan.ideas]
    return {"ideas": ideas, "archived_parts": plan.archived_parts}


def plan_from_dict(data: dict) -> ContentPlan:
    """Обратное превращение: словарь из JSON -> план с объектами Idea и ContentUnit."""
    plan = ContentPlan()
    for item in data["ideas"]:
        idea = Idea(
            text=item["text"],
            key=item["key"],
            line_no=item["line_no"],
            urgent=item["urgent"],
            part=item["part"],
            added=item["added"],
        )
        plan.ideas.append(idea)
        for unit in item["units"]:
            plan.units.append(ContentUnit(
                idea=idea,
                rubric=unit["rubric"],
                format_name=unit["format_name"],
                platforms=unit["platforms"],
                matched=unit["matched"],
                # .get: в памяти, сохранённой до этапа 4, дат ещё не было — считаем «в бэклоге»
                date=unit.get("date", ""),
            ))

    # .get: в памяти, сохранённой до этапа 7, счётчика архива ещё не было
    archived_parts = data.get("archived_parts", {})
    if not isinstance(archived_parts, dict):
        raise TypeError("archived_parts должен быть словарём")
    plan.archived_parts = archived_parts
    return plan


# ---------- чтение и запись файлов ----------

def load_plan(path: Path) -> tuple[ContentPlan, str]:
    """Читает память из файла.

    Возвращает план и предупреждение (пустая строка, если всё хорошо).
    - Файла нет (первый запуск) -> пустой план, без предупреждения.
    - Файл повреждён -> переименовываем его в *.broken.json (чтобы ничего не потерять),
      возвращаем пустой план и предупреждение.
    """
    if not path.exists():
        return ContentPlan(), ""

    try:
        with open(path, encoding="utf-8") as file:
            data = json.load(file)
        return plan_from_dict(data), ""
    except (ValueError, KeyError, TypeError):
        broken_path = path.with_suffix(".broken.json")
        os.replace(path, broken_path)
        warning = (
            f"файл памяти {path.name} повреждён — переименовала его в {broken_path.name} "
            f"и начинаю с пустого плана"
        )
        return ContentPlan(), warning


def write_text_safely(path: Path, text: str) -> None:
    """Записывает файл так, чтобы старая версия не испортилась, если запись оборвется.

    Сначала пишем во временный файл рядом, потом одним действием заменяем им старый.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(path.name + ".tmp")
    with open(temp_path, "w", encoding="utf-8") as file:
        file.write(text)
    os.replace(temp_path, path)


def save_plan(plan: ContentPlan, path: Path) -> None:
    """Сохраняет память в JSON-файл."""
    text = json.dumps(plan_to_dict(plan), ensure_ascii=False, indent=2)
    write_text_safely(path, text)


# ---------- файл с идеями как «входящие» ----------

def clean_inbox(path: str, keep_line_numbers: list[int]) -> None:
    """Оставляет в файле с идеями только строки с этими номерами, остальные удаляет.

    Остаются проблемные строки (например, «крем» — слишком коротко), чтобы их можно было дописать.
    """
    lines = read_lines(path)
    kept = []
    for line_no, line in enumerate(lines, start=1):
        if line_no in keep_line_numbers:
            kept.append(line)

    text = "\n".join(kept)
    if kept:
        text += "\n"
    write_text_safely(Path(path), text)


# ---------- архив (этап 7) ----------

def archive_old(plan: ContentPlan, before: str) -> list[dict]:
    """Убирает из плана идеи, у которых ВСЕ публикации раньше даты before ("2026-08-25").

    Идея остаётся в плане, если хоть одна её единица ещё впереди или ждёт в бэклоге (без даты).
    Для каждой убранной идеи увеличивает счётчик archived_parts — чтобы «часть N» не сбилась.
    Возвращает убранные идеи в виде словарей — их нужно дописать в архив.
    """
    records = []
    for idea in list(plan.ideas):  # list(...) — копия: из plan.ideas мы будем удалять
        units = plan.units_of(idea)
        if not units:
            continue
        all_in_past = True
        for unit in units:
            if not unit.date or unit.date >= before:
                all_in_past = False
                break
        if all_in_past:
            records.append(idea_to_dict(idea, units))
            plan.remove(idea)
            plan.archived_parts[idea.key] = plan.archived_parts.get(idea.key, 0) + 1
    return records


def append_to_archive(records: list[dict], path: Path) -> str:
    """Дописывает идеи в архив data/archive.json. Возвращает предупреждение ("" — всё хорошо).

    Старое содержимое архива не теряется. Если файл архива повреждён — откладываем его
    как archive.broken.json и начинаем новый архив.
    """
    warning = ""
    old_records = []
    if path.exists():
        try:
            with open(path, encoding="utf-8") as file:
                old_records = json.load(file)["ideas"]
            if not isinstance(old_records, list):
                raise TypeError("ideas должен быть списком")
        except (ValueError, KeyError, TypeError):
            broken_path = path.with_suffix(".broken.json")
            os.replace(path, broken_path)
            warning = f"файл архива {path.name} повреждён — отложила его как {broken_path.name}, начинаю новый"
            old_records = []

    text = json.dumps({"ideas": old_records + records}, ensure_ascii=False, indent=2)
    write_text_safely(path, text)
    return warning

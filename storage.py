"""Память программы: контент-план, который сохраняется между запусками.

- ContentPlan — всё, что программа помнит: идеи и их единицы контента.
- load_plan / save_plan — прочитать и сохранить память в JSON (data/state.json).
- clean_inbox — убрать из файла с идеями строки, которые уже попали в план.
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

    def times_seen(self, key: str) -> int:
        """Сколько раз идея с таким нормализованным текстом уже есть в плане."""
        count = 0
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


# ---------- план <-> JSON ----------

def plan_to_dict(plan: ContentPlan) -> dict:
    """Превращает план в словарь, который можно записать в JSON.

    Единицы контента записываются внутрь своей идеи — так не нужно отдельно хранить,
    какая единица к какой идее относится.
    """
    ideas = []
    for idea in plan.ideas:
        units = []
        for unit in plan.units_of(idea):
            units.append({
                "rubric": unit.rubric,
                "format_name": unit.format_name,
                "platforms": unit.platforms,
                "matched": unit.matched,
                "date": unit.date,
            })
        ideas.append({
            "text": idea.text,
            "key": idea.key,
            "line_no": idea.line_no,
            "urgent": idea.urgent,
            "part": idea.part,
            "added": idea.added,
            "units": units,
        })
    return {"ideas": ideas}


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
    """Записывает файл так, чтобы старая версия не испортилась, если запись оборвётся.

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

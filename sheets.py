"""Выгрузка плана в Google Таблицу — на отдельный лист (по умолчанию «План от программы»).

Лист каждый раз перезаписывается целиком: таблица — это «витрина», а главная память — data/state.json.
Остальные листы таблицы (например, календарная сетка) программа не трогает.

Что нужно (один раз, см. README → «Google Таблица»):
- data/google_key.json — ключ сервисного аккаунта Google (секрет! в репозиторий не попадает);
- data/google.json — ссылка на таблицу и название листа.
"""

import json
from pathlib import Path
from typing import Optional

from export import HEADER, plan_rows
from storage import ContentPlan


class SheetsError(Exception):
    """Не получилось записать план в Google Таблицу."""


def load_settings(path: Path) -> Optional[dict]:
    """Читает data/google.json.

    Файла нет — возвращает None: Google Таблица просто не настроена, это не ошибка.
    """
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as file:
            settings = json.load(file)
    except json.JSONDecodeError as error:
        raise SheetsError(f"{path.name}, строка {error.lineno}: ошибка в записи — проверь кавычки и запятые")

    for key in ("spreadsheet_url", "worksheet"):
        value = settings.get(key) if isinstance(settings, dict) else None
        if not isinstance(value, str) or not value.strip():
            raise SheetsError(f"в {path.name} не заполнено «{key}»")
    return settings


def sheet_values(plan: ContentPlan) -> list[list[str]]:
    """Всё содержимое листа: заголовок + строки плана (те же, что в CSV)."""
    return [HEADER] + plan_rows(plan)


def write_values(worksheet, values: list[list[str]]) -> None:
    """Перезаписывает лист: при нехватке строк добавляет их, очищает лист и пишет таблицу с ячейки A1.

    worksheet — лист из библиотеки gspread (в тестах — его простая замена).
    USER_ENTERED — значения вводятся так, как если бы их напечатали руками: «26.10.2026» станет датой,
    а апостроф перед «=)» (см. safe_cell в export.py) скажет таблице, что это текст, а не формула.
    """
    if worksheet.row_count < len(values):
        worksheet.resize(rows=len(values))
    worksheet.clear()
    worksheet.update(values=values, range_name="A1", value_input_option="USER_ENTERED")


def service_email(key_path: Path) -> str:
    """Почта сервисного аккаунта из ключа — её нужно добавить в доступ к таблице."""
    try:
        with open(key_path, encoding="utf-8") as file:
            return json.load(file).get("client_email", "почту сервисного аккаунта")
    except (OSError, ValueError, AttributeError):
        return "почту сервисного аккаунта"


def upload(plan: ContentPlan, settings: dict, key_path: Path) -> int:
    """Отправляет план в Google Таблицу. Возвращает, сколько строк плана записано.

    Любую проблему превращает в SheetsError с понятным текстом.
    """
    if not key_path.exists():
        raise SheetsError(f"нет ключа доступа data/{key_path.name} — см. README, раздел «Google Таблица»")

    # Импорт внутри функции: без библиотеки gspread программа всё равно работает (CSV, тесты),
    # она нужна только в момент отправки в Google.
    try:
        import gspread
    except ImportError:
        raise SheetsError("не установлена библиотека gspread — выполни: pip install -r requirements.txt")

    email = service_email(key_path)
    values = sheet_values(plan)

    try:
        client = gspread.service_account(filename=str(key_path))
    except (ValueError, KeyError):
        raise SheetsError(f"ключ data/{key_path.name} повреждён или это не ключ сервисного аккаунта — скачай заново")

    try:
        spreadsheet = client.open_by_url(settings["spreadsheet_url"])
        try:
            worksheet = spreadsheet.worksheet(settings["worksheet"])
        except gspread.exceptions.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(
                title=settings["worksheet"], rows=max(len(values), 100), cols=len(HEADER),
            )
        write_values(worksheet, values)
    except gspread.exceptions.NoValidUrlKeyFound:
        raise SheetsError("в google.json ссылка не похожа на ссылку Google Таблицы")
    except (gspread.exceptions.SpreadsheetNotFound, PermissionError):
        raise SheetsError(f"нет доступа к таблице — в «Настройках доступа» добавь {email} как редактора")
    except gspread.exceptions.APIError as error:
        raise SheetsError(f"Google ответил ошибкой: {error}. Если речь о доступе — добавь {email} как редактора")
    except Exception as error:
        # Сеть может оборваться десятком разных способов (нет интернета, таймаут, VPN...).
        # Ловим всё: таблица — не главное хранилище, план уже сохранён в state.json и plan.csv.
        raise SheetsError(f"не получилось связаться с Google ({type(error).__name__}) — проверь интернет")

    return len(values) - 1

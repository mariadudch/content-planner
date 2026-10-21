"""Подсказка для pytest.

Модули проекта (reader.py, models.py ...) лежат в корне, а тесты — в папке tests/.
Добавляем корень проекта в список мест, где Python ищет модули, — тогда
в тестах работает `from reader import ...`.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# logger.py
"""
УСТАРЕВШИЙ МОДУЛЬ - используйте utils.logger вместо этого!

Этот файл сохранен для обратной совместимости.
Новый код должен использовать utils.logger.
"""

import warnings
from typing import Dict, Any

# Импортируем новую систему логирования
try:
    from utils.logger import log_audit as new_log_audit
    NEW_LOGGER_AVAILABLE = True
except ImportError:
    NEW_LOGGER_AVAILABLE = False
    # Fallback к старой системе
    import os
    from datetime import datetime
    LOG_PATH = os.path.join(os.getcwd(), "audit.log")


def log_event(user: dict, event: str, obj_id: int, description: str):
    """
    УСТАРЕВШАЯ ФУНКЦИЯ - используйте utils.logger.log_audit!
    
    Записывает в audit.log одну строку:
    timestamp | user.login | event | obj_id | description
    """
    # Предупреждение об устаревшем использовании
    warnings.warn(
        "log_event() устарела. Используйте utils.logger.log_audit()",
        DeprecationWarning,
        stacklevel=2
    )
    
    if NEW_LOGGER_AVAILABLE:
        # Используем новую систему логирования
        new_log_audit(user, event, obj_id, description)
    else:
        # Fallback к старой системе
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"{ts} | {user.get('login','?')} | {event} | {obj_id} | {description}\n"
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line)

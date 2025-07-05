# logger.py

import os
from datetime import datetime

LOG_PATH = os.path.join(os.getcwd(), "audit.log")

def log_event(user: dict, event: str, obj_id: int, description: str):
    """
    Записывает в audit.log одну строку:
    timestamp | user.login | event | obj_id | description
    """
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{ts} | {user.get('login','?')} | {event} | {obj_id} | {description}\n"
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line)

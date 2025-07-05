# gui/lab/telegram_notifier.py

import requests
from db.database import Database

cfg = __import__('config').load_config()
BOT_TOKEN = cfg['TELEGRAM'].get('bot_token','').strip()
CHAT_ID   = cfg['TELEGRAM'].get('chat_id','').strip()
API_URL   = f"https://api.telegram.org/bot{BOT_TOKEN}"

def _send_message(text: str):
    if not BOT_TOKEN or not CHAT_ID:
        print("[Telegram] пропущено (нет токена или chat_id)")
        return
    requests.post(f"{API_URL}/sendMessage", data={
        'chat_id': CHAT_ID,
        'text': text,
        'parse_mode': 'Markdown'
    })

def notify_request_passed(req_id: int):
    """
    Уведомление о том, что ППСД пройдено.
    Отправляет ✅  и основные поля.
    """
    db = Database().connect()
    cur = db.cursor()
    cur.execute("""
        SELECT 
            lr.request_number, lr.creation_date,
            g.grade, m.size,
            s.name AS supplier
        FROM lab_requests lr
        JOIN Materials m ON lr.material_id = m.id
        JOIN Grades    g ON m.grade_id     = g.id
        JOIN Suppliers s ON m.supplier_id  = s.id
        WHERE lr.id = ?
    """, (req_id,))
    r = cur.fetchone()
    db.close()
    if not r:
        return

    msg = (
        f"✅ *ППСД пройдено*\n"
        f"• Номер заявки: `{r['request_number']}`\n"
        f"• Дата создания: {r['creation_date']}\n"
        f"• Поставщик: {r['supplier']}\n"
        f"• Марка: {r['grade']}\n"
        f"• Размер: {r['size']} мм\n"
    )
    _send_message(msg)

def notify_material_defect(req_id: int):
    """
    Уведомление о браке материала.
    Отправляет ❌  и основные поля.
    """
    db = Database().connect()
    cur = db.cursor()
    cur.execute("""
        SELECT 
            lr.request_number, lr.creation_date,
            g.grade, m.size,
            s.name AS supplier
        FROM lab_requests lr
        JOIN Materials m ON lr.material_id = m.id
        JOIN Grades    g ON m.grade_id     = g.id
        JOIN Suppliers s ON m.supplier_id  = s.id
        WHERE lr.id = ?
    """, (req_id,))
    r = cur.fetchone()
    db.close()
    if not r:
        return

    msg = (
        f"❌ *Брак материала*\n"
        f"• Номер заявки: `{r['request_number']}`\n"
        f"• Дата создания: {r['creation_date']}\n"
        f"• Поставщик: {r['supplier']}\n"
        f"• Марка: {r['grade']}\n"
        f"• Размер: {r['size']} мм\n"
    )
    _send_message(msg)

# gui/lab/telegram_notifier.py

import requests
from typing import Optional
from db.database import Database
from utils.logger import get_logger

# Получаем логгер для лабораторного модуля
logger = get_logger('lab')

# Загружаем конфигурацию
try:
    cfg = __import__('config').load_config()
    BOT_TOKEN = cfg['TELEGRAM'].get('bot_token','').strip()
    CHAT_ID   = cfg['TELEGRAM'].get('chat_id','').strip()
    API_URL   = f"https://api.telegram.org/bot{BOT_TOKEN}"
except Exception as e:
    logger.error(f"Ошибка загрузки конфигурации Telegram: {e}")
    BOT_TOKEN = ''
    CHAT_ID = ''
    API_URL = ''

def _send_message(text: str) -> bool:
    """
    Отправка сообщения в Telegram.
    
    Args:
        text: Текст сообщения
        
    Returns:
        True если сообщение отправлено успешно
    """
    if not BOT_TOKEN or not CHAT_ID:
        logger.warning("Telegram уведомление пропущено: не настроен токен или chat_id")
        return False
    
    try:
        response = requests.post(
            f"{API_URL}/sendMessage", 
            data={
                'chat_id': CHAT_ID,
                'text': text,
                'parse_mode': 'Markdown'
            },
            timeout=10
        )
        
        if response.status_code == 200:
            logger.info(f"Telegram уведомление отправлено успешно")
            return True
        else:
            logger.error(f"Ошибка отправки Telegram: HTTP {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при отправке Telegram уведомления: {e}")
        return False

def notify_request_passed(req_id: int) -> bool:
    """
    Уведомление о том, что ППСД пройдено.
    Отправляет ✅  и основные поля.
    
    Args:
        req_id: ID лабораторной заявки
        
    Returns:
        True если уведомление отправлено успешно
    """
    logger.info(f"Отправка уведомления о прохождении ППСД для заявки {req_id}")
    
    try:
        db = Database()
        db.connect()
        cur = db.conn.cursor()
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
            logger.warning(f"Заявка {req_id} не найдена для Telegram уведомления")
            return False

        msg = (
            f"✅ *ППСД пройдено*\n"
            f"• Номер заявки: `{r['request_number']}`\n"
            f"• Дата создания: {r['creation_date']}\n"
            f"• Поставщик: {r['supplier']}\n"
            f"• Марка: {r['grade']}\n"
            f"• Размер: {r['size']} мм\n"
        )
        
        success = _send_message(msg)
        if success:
            logger.info(f"Уведомление о прохождении ППСД отправлено для заявки {req_id}")
        
        return success
        
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления о прохождении ППСД для заявки {req_id}: {e}")
        return False

def notify_material_defect(req_id: int) -> bool:
    """
    Уведомление о браке материала.
    Отправляет ❌  и основные поля.
    
    Args:
        req_id: ID лабораторной заявки
        
    Returns:
        True если уведомление отправлено успешно
    """
    logger.info(f"Отправка уведомления о браке материала для заявки {req_id}")
    
    try:
        db = Database()
        db.connect()
        cur = db.conn.cursor()
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
            logger.warning(f"Заявка {req_id} не найдена для Telegram уведомления о браке")
            return False

        msg = (
            f"❌ *Брак материала*\n"
            f"• Номер заявки: `{r['request_number']}`\n"
            f"• Дата создания: {r['creation_date']}\n"
            f"• Поставщик: {r['supplier']}\n"
            f"• Марка: {r['grade']}\n"
            f"• Размер: {r['size']} мм\n"
        )
        
        success = _send_message(msg)
        if success:
            logger.info(f"Уведомление о браке материала отправлено для заявки {req_id}")
        
        return success
        
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления о браке материала для заявки {req_id}: {e}")
        return False

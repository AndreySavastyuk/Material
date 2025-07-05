# telegram_bot.py
import requests

def send_telegram_message(bot_token: str, chat_id: str, text: str, parse_mode: str = 'Markdown'):
    """
    Отправляет текст в Telegram через Bot API.
    """
    url = f'https://api.telegram.org/bot{bot_token}/sendMessage'
    payload = {
        'chat_id':    chat_id,
        'text':       text,
        'parse_mode': parse_mode,
        'disable_web_page_preview': True
    }
    resp = requests.post(url, json=payload, timeout=5)
    resp.raise_for_status()  # при ошибке вызовет исключение

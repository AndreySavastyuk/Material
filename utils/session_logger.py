"""
Утилита для детального логирования сессий пользователей.

Этот модуль предоставляет функции для:
- Логирования всех событий входа/выхода
- Анализа активности пользователей
- Отчетов по безопасности
- Мониторинга подозрительной активности
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import json
import platform
import socket

from db.database import Database
from utils.exceptions import BusinessLogicError

logger = logging.getLogger(__name__)


class SessionLogger:
    """
    Класс для логирования и анализа сессий пользователей.
    """
    
    def __init__(self, db: Database):
        """
        Инициализация логгера сессий.
        
        Args:
            db: Экземпляр базы данных
        """
        self.db = db
    
    def log_login_attempt(self, login: str, success: bool, ip_address: str = None, 
                         user_agent: str = None, reason: str = None, 
                         session_token: str = None, user_id: int = None):
        """
        Логирует попытку входа в систему.
        
        Args:
            login: Логин пользователя
            success: Успешность входа
            ip_address: IP-адрес
            user_agent: Информация о браузере/приложении
            reason: Причина неуспешного входа
            session_token: Токен созданной сессии
            user_id: ID пользователя (если аутентификация успешна)
        """
        try:
            cursor = self.db.conn.cursor()
            
            # Определяем действие
            action = 'login_success' if success else 'login_failed'
            
            # Получаем системную информацию
            system_info = self._get_system_info()
            
            # Формируем расширенную информацию
            extended_info = {
                'system_info': system_info,
                'timestamp': datetime.now().isoformat(),
                'session_token_provided': session_token is not None
            }
            
            if reason:
                extended_info['failure_reason'] = reason
            
            # Логируем в базу данных
            cursor.execute("""
                INSERT INTO user_login_logs 
                (user_id, login, action, ip_address, user_agent, session_token, 
                 success, reason, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """, (user_id, login, action, ip_address, user_agent, 
                  session_token, success, json.dumps(extended_info)))
            
            self.db.conn.commit()
            
            # Логируем в файл
            log_level = logging.INFO if success else logging.WARNING
            logger.log(log_level, 
                f"Попытка входа: {login} | IP: {ip_address} | Успех: {success} | Причина: {reason}")
            
        except Exception as e:
            logger.error(f"Ошибка логирования попытки входа: {e}")
    
    def log_logout(self, user_id: int, login: str, session_token: str = None,
                  ip_address: str = None, logout_type: str = 'manual', 
                  reason: str = None):
        """
        Логирует выход из системы.
        
        Args:
            user_id: ID пользователя
            login: Логин пользователя
            session_token: Токен сессии
            ip_address: IP-адрес
            logout_type: Тип выхода (manual, auto, forced, expired)
            reason: Причина выхода
        """
        try:
            cursor = self.db.conn.cursor()
            
            # Определяем действие
            action_map = {
                'manual': 'logout_manual',
                'auto': 'logout_auto',
                'forced': 'logout_forced',
                'expired': 'logout_expired'
            }
            action = action_map.get(logout_type, 'logout_unknown')
            
            # Формируем информацию о выходе
            logout_info = {
                'logout_type': logout_type,
                'timestamp': datetime.now().isoformat(),
                'system_info': self._get_system_info()
            }
            
            if reason:
                logout_info['reason'] = reason
            
            # Логируем в базу данных
            cursor.execute("""
                INSERT INTO user_login_logs 
                (user_id, login, action, ip_address, session_token, 
                 success, reason, created_at)
                VALUES (?, ?, ?, ?, ?, 1, ?, datetime('now'))
            """, (user_id, login, action, ip_address, session_token, 
                  json.dumps(logout_info)))
            
            self.db.conn.commit()
            
            # Логируем в файл
            logger.info(f"Выход из системы: {login} | Тип: {logout_type} | IP: {ip_address}")
            
        except Exception as e:
            logger.error(f"Ошибка логирования выхода: {e}")
    
    def log_session_event(self, user_id: int, login: str, event_type: str,
                         session_token: str = None, ip_address: str = None,
                         details: Dict = None):
        """
        Логирует событие сессии.
        
        Args:
            user_id: ID пользователя
            login: Логин пользователя
            event_type: Тип события (created, validated, expired, invalidated, extended)
            session_token: Токен сессии
            ip_address: IP-адрес
            details: Дополнительные детали события
        """
        try:
            cursor = self.db.conn.cursor()
            
            # Формируем информацию о событии
            event_info = {
                'event_type': event_type,
                'timestamp': datetime.now().isoformat(),
                'system_info': self._get_system_info()
            }
            
            if details:
                event_info.update(details)
            
            # Логируем в базу данных
            cursor.execute("""
                INSERT INTO user_login_logs 
                (user_id, login, action, ip_address, session_token, 
                 success, reason, created_at)
                VALUES (?, ?, ?, ?, ?, 1, ?, datetime('now'))
            """, (user_id, login, f'session_{event_type}', ip_address, 
                  session_token, json.dumps(event_info)))
            
            self.db.conn.commit()
            
            # Логируем в файл
            logger.info(f"Событие сессии: {login} | Тип: {event_type} | IP: {ip_address}")
            
        except Exception as e:
            logger.error(f"Ошибка логирования события сессии: {e}")
    
    def _get_system_info(self) -> Dict[str, str]:
        """
        Получает информацию о системе.
        
        Returns:
            Словарь с информацией о системе
        """
        try:
            return {
                'platform': platform.platform(),
                'system': platform.system(),
                'release': platform.release(),
                'version': platform.version(),
                'machine': platform.machine(),
                'processor': platform.processor(),
                'python_version': platform.python_version()
            }
        except Exception as e:
            logger.error(f"Ошибка получения системной информации: {e}")
            return {'error': str(e)}
    
    def get_login_history(self, user_id: int = None, login: str = None,
                         hours: int = 24) -> List[Dict[str, Any]]:
        """
        Получает историю входов пользователя.
        
        Args:
            user_id: ID пользователя (опционально)
            login: Логин пользователя (опционально)
            hours: Количество часов для анализа
            
        Returns:
            Список записей входов
        """
        try:
            cursor = self.db.conn.cursor()
            
            # Строим запрос
            query = """
                SELECT * FROM user_login_logs 
                WHERE created_at > datetime('now', '-{} hour')
            """.format(hours)
            
            params = []
            
            if user_id:
                query += " AND user_id = ?"
                params.append(user_id)
            
            if login:
                query += " AND login = ?"
                params.append(login)
            
            query += " ORDER BY created_at DESC"
            
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
            
        except Exception as e:
            logger.error(f"Ошибка получения истории входов: {e}")
            return []
    
    def get_security_report(self, hours: int = 24) -> Dict[str, Any]:
        """
        Генерирует отчет по безопасности.
        
        Args:
            hours: Количество часов для анализа
            
        Returns:
            Словарь с отчетом по безопасности
        """
        try:
            cursor = self.db.conn.cursor()
            
            # Общая статистика
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_attempts,
                    SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful_logins,
                    SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failed_logins,
                    COUNT(DISTINCT user_id) as unique_users,
                    COUNT(DISTINCT ip_address) as unique_ips
                FROM user_login_logs 
                WHERE created_at > datetime('now', '-{} hour')
            """.format(hours))
            
            stats = dict(cursor.fetchone())
            
            # Топ IP-адресов с неудачными попытками
            cursor.execute("""
                SELECT ip_address, COUNT(*) as failed_count
                FROM user_login_logs 
                WHERE created_at > datetime('now', '-{} hour') 
                AND success = 0 
                AND ip_address IS NOT NULL
                GROUP BY ip_address
                ORDER BY failed_count DESC
                LIMIT 10
            """.format(hours))
            
            suspicious_ips = [dict(row) for row in cursor.fetchall()]
            
            # Пользователи с множественными неудачными попытками
            cursor.execute("""
                SELECT login, COUNT(*) as failed_count
                FROM user_login_logs 
                WHERE created_at > datetime('now', '-{} hour') 
                AND success = 0
                GROUP BY login
                HAVING failed_count > 3
                ORDER BY failed_count DESC
            """.format(hours))
            
            suspicious_users = [dict(row) for row in cursor.fetchall()]
            
            # Активные сессии
            cursor.execute("""
                SELECT COUNT(*) as active_sessions
                FROM user_sessions 
                WHERE is_active = 1 AND expires_at > datetime('now')
            """)
            
            active_sessions = cursor.fetchone()['active_sessions']
            
            return {
                'period_hours': hours,
                'generated_at': datetime.now().isoformat(),
                'statistics': stats,
                'suspicious_ips': suspicious_ips,
                'suspicious_users': suspicious_users,
                'active_sessions': active_sessions
            }
            
        except Exception as e:
            logger.error(f"Ошибка генерации отчета безопасности: {e}")
            return {}
    
    def detect_suspicious_activity(self, hours: int = 1) -> List[Dict[str, Any]]:
        """
        Обнаруживает подозрительную активность.
        
        Args:
            hours: Количество часов для анализа
            
        Returns:
            Список подозрительных событий
        """
        suspicious_events = []
        
        try:
            cursor = self.db.conn.cursor()
            
            # 1. Множественные неудачные попытки входа с одного IP
            cursor.execute("""
                SELECT ip_address, COUNT(*) as failed_count,
                       GROUP_CONCAT(DISTINCT login) as attempted_logins
                FROM user_login_logs 
                WHERE created_at > datetime('now', '-{} hour') 
                AND success = 0 
                AND ip_address IS NOT NULL
                GROUP BY ip_address
                HAVING failed_count >= 5
            """.format(hours))
            
            for row in cursor.fetchall():
                suspicious_events.append({
                    'type': 'brute_force_ip',
                    'ip_address': row['ip_address'],
                    'failed_count': row['failed_count'],
                    'attempted_logins': row['attempted_logins'],
                    'severity': 'high'
                })
            
            # 2. Множественные неудачные попытки для одного пользователя
            cursor.execute("""
                SELECT login, COUNT(*) as failed_count,
                       GROUP_CONCAT(DISTINCT ip_address) as source_ips
                FROM user_login_logs 
                WHERE created_at > datetime('now', '-{} hour') 
                AND success = 0
                GROUP BY login
                HAVING failed_count >= 5
            """.format(hours))
            
            for row in cursor.fetchall():
                suspicious_events.append({
                    'type': 'brute_force_user',
                    'login': row['login'],
                    'failed_count': row['failed_count'],
                    'source_ips': row['source_ips'],
                    'severity': 'high'
                })
            
            # 3. Входы с разных IP-адресов для одного пользователя
            cursor.execute("""
                SELECT login, COUNT(DISTINCT ip_address) as ip_count,
                       GROUP_CONCAT(DISTINCT ip_address) as ip_addresses
                FROM user_login_logs 
                WHERE created_at > datetime('now', '-{} hour') 
                AND success = 1
                AND ip_address IS NOT NULL
                GROUP BY login
                HAVING ip_count >= 3
            """.format(hours))
            
            for row in cursor.fetchall():
                suspicious_events.append({
                    'type': 'multiple_locations',
                    'login': row['login'],
                    'ip_count': row['ip_count'],
                    'ip_addresses': row['ip_addresses'],
                    'severity': 'medium'
                })
            
            # 4. Сессии с аномально долгим временем жизни
            cursor.execute("""
                SELECT s.user_id, u.login, s.session_token,
                       s.created_at, s.expires_at,
                       (julianday(s.expires_at) - julianday(s.created_at)) * 24 * 60 as duration_minutes
                FROM user_sessions s
                JOIN users u ON s.user_id = u.id
                WHERE s.is_active = 1
                AND duration_minutes > 60 * 24 * 7  -- Более 7 дней
            """)
            
            for row in cursor.fetchall():
                suspicious_events.append({
                    'type': 'long_session',
                    'login': row['login'],
                    'session_token': row['session_token'],
                    'duration_minutes': row['duration_minutes'],
                    'severity': 'low'
                })
            
        except Exception as e:
            logger.error(f"Ошибка обнаружения подозрительной активности: {e}")
        
        return suspicious_events
    
    def cleanup_old_logs(self, days: int = 90) -> int:
        """
        Очищает старые логи.
        
        Args:
            days: Количество дней для хранения логов
            
        Returns:
            Количество удаленных записей
        """
        try:
            cursor = self.db.conn.cursor()
            
            cursor.execute("""
                DELETE FROM user_login_logs 
                WHERE created_at < datetime('now', '-{} day')
            """.format(days))
            
            deleted_count = cursor.rowcount
            self.db.conn.commit()
            
            if deleted_count > 0:
                logger.info(f"Удалено {deleted_count} старых записей логов")
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"Ошибка очистки старых логов: {e}")
            return 0


# Глобальный экземпляр для использования в приложении
_session_logger = None


def get_session_logger(db: Database = None) -> SessionLogger:
    """
    Получает глобальный экземпляр SessionLogger.
    
    Args:
        db: Экземпляр базы данных (если не передан, используется существующий)
        
    Returns:
        Экземпляр SessionLogger
    """
    global _session_logger
    
    if _session_logger is None or db is not None:
        if db is None:
            raise ValueError("Database instance required for first initialization")
        _session_logger = SessionLogger(db)
    
    return _session_logger


def log_user_login(login: str, success: bool, **kwargs):
    """
    Удобная функция для логирования входа пользователя.
    
    Args:
        login: Логин пользователя
        success: Успешность входа
        **kwargs: Дополнительные параметры
    """
    try:
        session_logger = get_session_logger()
        session_logger.log_login_attempt(login, success, **kwargs)
    except Exception as e:
        logger.error(f"Ошибка логирования входа пользователя: {e}")


def log_user_logout(user_id: int, login: str, **kwargs):
    """
    Удобная функция для логирования выхода пользователя.
    
    Args:
        user_id: ID пользователя
        login: Логин пользователя
        **kwargs: Дополнительные параметры
    """
    try:
        session_logger = get_session_logger()
        session_logger.log_logout(user_id, login, **kwargs)
    except Exception as e:
        logger.error(f"Ошибка логирования выхода пользователя: {e}")


def log_session_event(user_id: int, login: str, event_type: str, **kwargs):
    """
    Удобная функция для логирования событий сессии.
    
    Args:
        user_id: ID пользователя
        login: Логин пользователя
        event_type: Тип события
        **kwargs: Дополнительные параметры
    """
    try:
        session_logger = get_session_logger()
        session_logger.log_session_event(user_id, login, event_type, **kwargs)
    except Exception as e:
        logger.error(f"Ошибка логирования события сессии: {e}")


def generate_security_report(hours: int = 24) -> Dict[str, Any]:
    """
    Генерирует отчет по безопасности.
    
    Args:
        hours: Количество часов для анализа
        
    Returns:
        Словарь с отчетом
    """
    try:
        session_logger = get_session_logger()
        return session_logger.get_security_report(hours)
    except Exception as e:
        logger.error(f"Ошибка генерации отчета безопасности: {e}")
        return {}


def detect_threats(hours: int = 1) -> List[Dict[str, Any]]:
    """
    Обнаруживает угрозы безопасности.
    
    Args:
        hours: Количество часов для анализа
        
    Returns:
        Список угроз
    """
    try:
        session_logger = get_session_logger()
        return session_logger.detect_suspicious_activity(hours)
    except Exception as e:
        logger.error(f"Ошибка обнаружения угроз: {e}")
        return [] 
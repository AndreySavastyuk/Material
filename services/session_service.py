"""
Сервис управления сессиями пользователей.

Этот модуль предоставляет функциональность для:
- Создания и управления пользовательскими сессиями
- Проверки токенов сессий и их валидности
- Автоматического истечения и очистки сессий
- Поддержки функции "Запомнить меня"
- Логирования всех операций с сессиями
- Обеспечения безопасности сессий
"""

import secrets
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import hashlib
import json
import platform

from db.database import Database
from utils.exceptions import (
    BusinessLogicError,
    ValidationError,
    AuthenticationError,
    SecurityError
)
from utils.session_security import get_security_manager

logger = logging.getLogger(__name__)


class SessionService:
    """
    Сервис для управления пользовательскими сессиями.
    
    Обеспечивает создание, проверку, обновление и удаление сессий,
    а также контроль безопасности и автоматическую очистку.
    """
    
    def __init__(self, db: Database):
        """
        Инициализация сервиса сессий.
        
        Args:
            db: Экземпляр базы данных
        """
        self.db = db
        self._settings_cache = {}
        self._cache_timeout = 300  # 5 минут
        self._last_cache_update = None
        
        # Инициализируем менеджер безопасности
        self._security_manager = get_security_manager(db)
        
    def _get_setting(self, setting_name: str, default_value: str = None) -> str:
        """
        Получает настройку из кэша или базы данных.
        
        Args:
            setting_name: Название настройки
            default_value: Значение по умолчанию
            
        Returns:
            Значение настройки
        """
        now = datetime.now()
        
        # Обновляем кэш если он устарел
        if (self._last_cache_update is None or 
            (now - self._last_cache_update).seconds > self._cache_timeout):
            self._refresh_settings_cache()
        
        return self._settings_cache.get(setting_name, default_value)
    
    def _refresh_settings_cache(self):
        """Обновляет кэш настроек из базы данных."""
        try:
            cursor = self.db.conn.cursor()
            cursor.execute("SELECT setting_name, setting_value FROM session_settings")
            
            self._settings_cache = {
                row['setting_name']: row['setting_value'] 
                for row in cursor.fetchall()
            }
            self._last_cache_update = datetime.now()
            
        except Exception as e:
            logger.error(f"Ошибка обновления кэша настроек: {e}")
    
    def _generate_session_token(self) -> str:
        """
        Генерирует криптографически стойкий токен сессии.
        
        Returns:
            Уникальный токен сессии
        """
        token_length = int(self._get_setting('session_token_length', '64'))
        return secrets.token_urlsafe(token_length)
    
    def _get_session_timeout(self, remember_me: bool = False) -> int:
        """
        Получает таймаут сессии в секундах.
        
        Args:
            remember_me: Флаг "Запомнить меня"
            
        Returns:
            Таймаут в секундах
        """
        if remember_me:
            return int(self._get_setting('remember_me_timeout', '2592000'))  # 30 дней
        return int(self._get_setting('default_session_timeout', '3600'))  # 1 час
    
    def _get_user_agent_info(self) -> Dict[str, str]:
        """
        Получает информацию о системе и приложении.
        
        Returns:
            Словарь с информацией о системе
        """
        return {
            'platform': platform.platform(),
            'system': platform.system(),
            'release': platform.release(),
            'machine': platform.machine(),
            'application': 'Material Control Desktop App'
        }
    
    def create_session(self, user_id: int, remember_me: bool = False, 
                      ip_address: str = None, user_agent: str = None) -> Dict[str, Any]:
        """
        Создает новую сессию для пользователя.
        
        Args:
            user_id: ID пользователя
            remember_me: Флаг "Запомнить меня"
            ip_address: IP-адрес пользователя
            user_agent: Информация о браузере/приложении
            
        Returns:
            Словарь с данными сессии
            
        Raises:
            BusinessLogicError: При ошибке создания сессии
            ValidationError: При недопустимых параметрах
        """
        try:
            # Проверяем лимит сессий на пользователя
            self._enforce_session_limit(user_id)
            
            # Генерируем токен
            session_token = self._generate_session_token()
            
            # Вычисляем время истечения
            timeout_seconds = self._get_session_timeout(remember_me)
            now = datetime.now()
            expires_at = now + timedelta(seconds=timeout_seconds)
            
            # Получаем информацию о системе если user_agent не передан
            if not user_agent:
                system_info = self._get_user_agent_info()
                user_agent = json.dumps(system_info)
            
            # Создаем запись сессии
            cursor = self.db.conn.cursor()
            cursor.execute("""
                INSERT INTO user_sessions 
                (user_id, session_token, created_at, last_activity, expires_at, 
                 remember_me, ip_address, user_agent, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
            """, (
                user_id, session_token, now.isoformat(), now.isoformat(),
                expires_at.isoformat(), remember_me, ip_address, user_agent
            ))
            
            session_id = cursor.lastrowid
            self.db.conn.commit()
            
            # Логируем создание сессии
            self._log_session_action(
                user_id=user_id,
                action='session_created',
                session_token=session_token,
                ip_address=ip_address,
                user_agent=user_agent,
                success=True,
                reason=f"Remember me: {remember_me}, expires: {expires_at.isoformat()}"
            )
            
            logger.info(f"Создана сессия {session_id} для пользователя {user_id}")
            
            return {
                'session_id': session_id,
                'session_token': session_token,
                'user_id': user_id,
                'created_at': now.isoformat(),
                'expires_at': expires_at.isoformat(),
                'remember_me': remember_me,
                'is_active': True
            }
            
        except Exception as e:
            self.db.conn.rollback()
            logger.error(f"Ошибка создания сессии для пользователя {user_id}: {e}")
            
            # Логируем неудачную попытку
            self._log_session_action(
                user_id=user_id,
                action='session_create_failed',
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
                reason=str(e)
            )
            
            raise BusinessLogicError(
                message="Не удалось создать сессию",
                original_error=e,
                suggestions=["Проверьте подключение к базе данных", "Попробуйте войти снова"]
            )
    
    def _enforce_session_limit(self, user_id: int):
        """
        Проверяет и применяет лимит активных сессий на пользователя.
        
        Args:
            user_id: ID пользователя
        """
        max_sessions = int(self._get_setting('max_sessions_per_user', '5'))
        
        # Получаем активные сессии пользователя
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT id, created_at FROM user_sessions 
            WHERE user_id = ? AND is_active = 1 AND expires_at > datetime('now')
            ORDER BY last_activity ASC
        """, (user_id,))
        
        active_sessions = cursor.fetchall()
        
        # Если превышен лимит, удаляем старые сессии
        if len(active_sessions) >= max_sessions:
            sessions_to_remove = len(active_sessions) - max_sessions + 1
            
            for i in range(sessions_to_remove):
                session_id = active_sessions[i]['id']
                self._invalidate_session_by_id(session_id, reason="Session limit exceeded")
                logger.info(f"Удалена старая сессия {session_id} из-за превышения лимита")
    
    def validate_session(self, session_token: str, ip_address: str = None) -> Optional[Dict[str, Any]]:
        """
        Проверяет валидность токена сессии.
        
        Args:
            session_token: Токен сессии
            ip_address: IP-адрес для проверки
            
        Returns:
            Данные сессии если токен валиден, None если не валиден
        """
        try:
            cursor = self.db.conn.cursor()
            cursor.execute("""
                SELECT s.*, u.login, u.name 
                FROM user_sessions s
                JOIN users u ON s.user_id = u.id
                WHERE s.session_token = ? AND s.is_active = 1
            """, (session_token,))
            
            session = cursor.fetchone()
            
            if not session:
                self._log_session_action(
                    action='invalid_token',
                    session_token=session_token,
                    ip_address=ip_address,
                    success=False,
                    reason="Token not found or inactive"
                )
                return None
            
            session_dict = dict(session)
            
            # Проверяем истечение времени
            expires_at = datetime.fromisoformat(session_dict['expires_at'])
            if expires_at <= datetime.now():
                self._invalidate_session_by_id(
                    session_dict['id'], 
                    reason="Session expired"
                )
                
                self._log_session_action(
                    user_id=session_dict['user_id'],
                    action='session_expired',
                    session_token=session_token,
                    ip_address=ip_address,
                    success=False,
                    reason="Session expired"
                )
                return None
            
            # Проверяем изменение IP если включено
            if (self._get_setting('track_ip_changes', 'true').lower() == 'true' and 
                ip_address and session_dict['ip_address'] and 
                ip_address != session_dict['ip_address']):
                
                logger.warning(f"IP changed for session {session_dict['id']}: "
                             f"{session_dict['ip_address']} -> {ip_address}")
                
                if self._get_setting('invalidate_on_ip_change', 'false').lower() == 'true':
                    self._invalidate_session_by_id(
                        session_dict['id'], 
                        reason="IP address changed"
                    )
                    
                    self._log_session_action(
                        user_id=session_dict['user_id'],
                        action='session_ip_changed',
                        session_token=session_token,
                        ip_address=ip_address,
                        success=False,
                        reason=f"IP changed from {session_dict['ip_address']} to {ip_address}"
                    )
                    return None
            
            # Обновляем время последней активности
            self._update_session_activity(session_dict['id'], ip_address)
            
            return session_dict
            
        except Exception as e:
            logger.error(f"Ошибка валидации сессии {session_token}: {e}")
            return None
    
    def _update_session_activity(self, session_id: int, ip_address: str = None):
        """
        Обновляет время последней активности сессии.
        
        Args:
            session_id: ID сессии
            ip_address: Новый IP-адрес (если изменился)
        """
        try:
            cursor = self.db.conn.cursor()
            
            if ip_address:
                cursor.execute("""
                    UPDATE user_sessions 
                    SET last_activity = datetime('now'), ip_address = ?
                    WHERE id = ?
                """, (ip_address, session_id))
            else:
                cursor.execute("""
                    UPDATE user_sessions 
                    SET last_activity = datetime('now')
                    WHERE id = ?
                """, (session_id,))
            
            self.db.conn.commit()
            
        except Exception as e:
            logger.error(f"Ошибка обновления активности сессии {session_id}: {e}")
    
    def invalidate_session(self, session_token: str, reason: str = "Manual logout") -> bool:
        """
        Инвалидирует сессию по токену.
        
        Args:
            session_token: Токен сессии
            reason: Причина инвалидации
            
        Returns:
            True если сессия была инвалидирована
        """
        try:
            cursor = self.db.conn.cursor()
            
            # Получаем информацию о сессии
            cursor.execute("""
                SELECT id, user_id FROM user_sessions 
                WHERE session_token = ? AND is_active = 1
            """, (session_token,))
            
            session = cursor.fetchone()
            
            if not session:
                return False
            
            return self._invalidate_session_by_id(session['id'], reason)
            
        except Exception as e:
            logger.error(f"Ошибка инвалидации сессии {session_token}: {e}")
            return False
    
    def _invalidate_session_by_id(self, session_id: int, reason: str = "Manual logout") -> bool:
        """
        Инвалидирует сессию по ID.
        
        Args:
            session_id: ID сессии
            reason: Причина инвалидации
            
        Returns:
            True если сессия была инвалидирована
        """
        try:
            cursor = self.db.conn.cursor()
            
            # Инвалидируем сессию
            cursor.execute("""
                UPDATE user_sessions 
                SET is_active = 0
                WHERE id = ? AND is_active = 1
            """, (session_id,))
            
            success = cursor.rowcount > 0
            
            if success:
                self.db.conn.commit()
                logger.info(f"Сессия {session_id} инвалидирована: {reason}")
            
            return success
            
        except Exception as e:
            logger.error(f"Ошибка инвалидации сессии {session_id}: {e}")
            return False
    
    def invalidate_all_user_sessions(self, user_id: int, reason: str = "Security logout") -> int:
        """
        Инвалидирует все сессии пользователя.
        
        Args:
            user_id: ID пользователя
            reason: Причина инвалидации
            
        Returns:
            Количество инвалидированных сессий
        """
        try:
            cursor = self.db.conn.cursor()
            
            cursor.execute("""
                UPDATE user_sessions 
                SET is_active = 0
                WHERE user_id = ? AND is_active = 1
            """, (user_id,))
            
            count = cursor.rowcount
            self.db.conn.commit()
            
            if count > 0:
                self._log_session_action(
                    user_id=user_id,
                    action='all_sessions_invalidated',
                    success=True,
                    reason=f"{reason}, count: {count}"
                )
                
                logger.info(f"Инвалидированы все сессии пользователя {user_id}: {count} сессий")
            
            return count
            
        except Exception as e:
            logger.error(f"Ошибка инвалидации всех сессий пользователя {user_id}: {e}")
            return 0
    
    def cleanup_expired_sessions(self) -> int:
        """
        Очищает истекшие сессии.
        
        Returns:
            Количество очищенных сессий
        """
        try:
            cursor = self.db.conn.cursor()
            
            cursor.execute("""
                UPDATE user_sessions 
                SET is_active = 0
                WHERE is_active = 1 AND expires_at <= datetime('now')
            """)
            
            count = cursor.rowcount
            self.db.conn.commit()
            
            if count > 0:
                logger.info(f"Очищено {count} истекших сессий")
            
            return count
            
        except Exception as e:
            logger.error(f"Ошибка очистки истекших сессий: {e}")
            return 0
    
    def get_user_sessions(self, user_id: int, active_only: bool = True) -> List[Dict[str, Any]]:
        """
        Получает список сессий пользователя.
        
        Args:
            user_id: ID пользователя
            active_only: Только активные сессии
            
        Returns:
            Список сессий
        """
        try:
            cursor = self.db.conn.cursor()
            
            query = """
                SELECT id, session_token, created_at, last_activity, expires_at,
                       remember_me, ip_address, user_agent, is_active
                FROM user_sessions 
                WHERE user_id = ?
            """
            
            params = [user_id]
            
            if active_only:
                query += " AND is_active = 1 AND expires_at > datetime('now')"
            
            query += " ORDER BY last_activity DESC"
            
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
            
        except Exception as e:
            logger.error(f"Ошибка получения сессий пользователя {user_id}: {e}")
            return []
    
    def _log_session_action(self, action: str, user_id: int = None, login: str = None,
                           session_token: str = None, ip_address: str = None,
                           user_agent: str = None, success: bool = True, reason: str = None):
        """
        Логирует действие с сессией.
        
        Args:
            action: Тип действия
            user_id: ID пользователя
            login: Логин пользователя  
            session_token: Токен сессии
            ip_address: IP-адрес
            user_agent: User agent
            success: Успешность операции
            reason: Причина/описание
        """
        try:
            # Получаем логин если не передан
            if user_id and not login:
                cursor = self.db.conn.cursor()
                cursor.execute("SELECT login FROM users WHERE id = ?", (user_id,))
                user_row = cursor.fetchone()
                if user_row:
                    login = user_row['login']
            
            # Вставляем лог
            cursor = self.db.conn.cursor()
            cursor.execute("""
                INSERT INTO user_login_logs 
                (user_id, login, action, ip_address, user_agent, session_token, 
                 success, reason, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """, (user_id, login, action, ip_address, user_agent, 
                  session_token, success, reason))
            
            self.db.conn.commit()
            
        except Exception as e:
            logger.error(f"Ошибка логирования действия сессии: {e}")
    
    def get_session_statistics(self) -> Dict[str, Any]:
        """
        Получает статистику по сессиям.
        
        Returns:
            Словарь со статистикой
        """
        try:
            cursor = self.db.conn.cursor()
            
            # Активные сессии
            cursor.execute("""
                SELECT COUNT(*) as count FROM user_sessions 
                WHERE is_active = 1 AND expires_at > datetime('now')
            """)
            active_sessions = cursor.fetchone()['count']
            
            # Сессии с "запомнить меня"
            cursor.execute("""
                SELECT COUNT(*) as count FROM user_sessions 
                WHERE is_active = 1 AND remember_me = 1 AND expires_at > datetime('now')
            """)
            remember_me_sessions = cursor.fetchone()['count']
            
            # Всего сессий за последние 24 часа
            cursor.execute("""
                SELECT COUNT(*) as count FROM user_sessions 
                WHERE created_at > datetime('now', '-1 day')
            """)
            sessions_24h = cursor.fetchone()['count']
            
            # Уникальные пользователи с активными сессиями
            cursor.execute("""
                SELECT COUNT(DISTINCT user_id) as count FROM user_sessions 
                WHERE is_active = 1 AND expires_at > datetime('now')
            """)
            active_users = cursor.fetchone()['count']
            
            return {
                'active_sessions': active_sessions,
                'remember_me_sessions': remember_me_sessions,
                'sessions_last_24h': sessions_24h,
                'active_users': active_users,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения статистики сессий: {e}")
            return {} 
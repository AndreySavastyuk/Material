"""
Утилиты для обеспечения безопасности сессий пользователей.

Этот модуль предоставляет:
- Защиту от фиксации сессий
- Ротацию токенов сессий
- Защиту от CSRF-атак
- Мониторинг аномальной активности
- Контроль целостности сессий
"""

import secrets
import hashlib
import hmac
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import json

from db.database import Database
from utils.exceptions import SecurityError
from utils.session_logger import log_session_event

logger = logging.getLogger(__name__)


class SessionSecurityManager:
    """
    Менеджер безопасности сессий.
    
    Обеспечивает защиту от различных угроз безопасности,
    связанных с управлением сессиями.
    """
    
    def __init__(self, db: Database, secret_key: str = None):
        """
        Инициализация менеджера безопасности.
        
        Args:
            db: Экземпляр базы данных
            secret_key: Секретный ключ для подписи токенов
        """
        self.db = db
        self.secret_key = secret_key or self._generate_secret_key()
        
        # Настройки безопасности
        self.max_session_lifetime = 24 * 60 * 60  # 24 часа
        self.token_rotation_interval = 60 * 60    # 1 час
        self.max_failed_attempts = 5
        self.lockout_duration = 15 * 60           # 15 минут
        self.suspicious_activity_threshold = 10
        
        # Кэш для отслеживания подозрительной активности
        self._suspicious_ips = {}
        self._failed_attempts = {}
    
    def _generate_secret_key(self) -> str:
        """Генерирует секретный ключ для подписи токенов."""
        return secrets.token_hex(32)
    
    def _sign_token(self, token: str, additional_data: str = "") -> str:
        """
        Создает подпись для токена.
        
        Args:
            token: Токен для подписи
            additional_data: Дополнительные данные для подписи
            
        Returns:
            Подпись токена
        """
        message = f"{token}:{additional_data}"
        signature = hmac.new(
            self.secret_key.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def _verify_token_signature(self, token: str, signature: str, 
                               additional_data: str = "") -> bool:
        """
        Проверяет подпись токена.
        
        Args:
            token: Токен
            signature: Подпись токена
            additional_data: Дополнительные данные
            
        Returns:
            True если подпись валидна
        """
        expected_signature = self._sign_token(token, additional_data)
        return hmac.compare_digest(signature, expected_signature)
    
    def create_secure_token(self, user_id: int, ip_address: str = None,
                           user_agent: str = None) -> Dict[str, str]:
        """
        Создает безопасный токен сессии с подписью.
        
        Args:
            user_id: ID пользователя
            ip_address: IP-адрес пользователя
            user_agent: User agent пользователя
            
        Returns:
            Словарь с токеном и его подписью
        """
        # Генерируем базовый токен
        base_token = secrets.token_urlsafe(48)
        
        # Создаем дополнительные данные для подписи
        timestamp = str(int(time.time()))
        additional_data = f"{user_id}:{ip_address}:{timestamp}"
        
        # Создаем подпись
        signature = self._sign_token(base_token, additional_data)
        
        # Формируем финальный токен
        secure_token = f"{base_token}.{timestamp}.{signature}"
        
        return {
            'token': secure_token,
            'signature': signature,
            'timestamp': timestamp
        }
    
    def validate_secure_token(self, token: str, user_id: int, 
                             ip_address: str = None) -> bool:
        """
        Валидирует безопасный токен сессии.
        
        Args:
            token: Токен для валидации
            user_id: ID пользователя
            ip_address: IP-адрес пользователя
            
        Returns:
            True если токен валиден
        """
        try:
            # Разбираем токен
            parts = token.split('.')
            if len(parts) != 3:
                return False
            
            base_token, timestamp, signature = parts
            
            # Проверяем подпись
            additional_data = f"{user_id}:{ip_address}:{timestamp}"
            if not self._verify_token_signature(base_token, signature, additional_data):
                logger.warning(f"Недействительная подпись токена для пользователя {user_id}")
                return False
            
            # Проверяем время создания токена
            token_time = int(timestamp)
            current_time = int(time.time())
            
            if current_time - token_time > self.max_session_lifetime:
                logger.info(f"Токен истек для пользователя {user_id}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Ошибка валидации токена: {e}")
            return False
    
    def rotate_session_token(self, old_token: str, user_id: int, 
                            ip_address: str = None) -> Optional[str]:
        """
        Выполняет ротацию токена сессии.
        
        Args:
            old_token: Старый токен
            user_id: ID пользователя
            ip_address: IP-адрес пользователя
            
        Returns:
            Новый токен или None если ротация невозможна
        """
        try:
            cursor = self.db.conn.cursor()
            
            # Проверяем существование старой сессии
            cursor.execute("""
                SELECT id, last_activity FROM user_sessions 
                WHERE session_token = ? AND user_id = ? AND is_active = 1
            """, (old_token, user_id))
            
            session = cursor.fetchone()
            if not session:
                logger.warning(f"Сессия не найдена для ротации: {old_token}")
                return None
            
            # Проверяем нужна ли ротация
            last_activity = datetime.fromisoformat(session['last_activity'])
            now = datetime.now()
            
            if (now - last_activity).total_seconds() < self.token_rotation_interval:
                return old_token  # Ротация не нужна
            
            # Создаем новый токен
            new_token_data = self.create_secure_token(user_id, ip_address)
            new_token = new_token_data['token']
            
            # Обновляем сессию
            cursor.execute("""
                UPDATE user_sessions 
                SET session_token = ?, last_activity = datetime('now')
                WHERE id = ?
            """, (new_token, session['id']))
            
            self.db.conn.commit()
            
            # Логируем ротацию
            log_session_event(
                user_id=user_id,
                login="unknown",
                event_type='token_rotated',
                session_token=new_token,
                ip_address=ip_address,
                details={
                    'old_token': old_token[:16] + "...",  # Частичный токен для безопасности
                    'rotation_reason': 'scheduled_rotation'
                }
            )
            
            logger.info(f"Токен ротирован для пользователя {user_id}")
            return new_token
            
        except Exception as e:
            logger.error(f"Ошибка ротации токена: {e}")
            return None
    
    def detect_session_hijacking(self, session_token: str, current_ip: str,
                                current_user_agent: str) -> bool:
        """
        Обнаруживает попытки угона сессии.
        
        Args:
            session_token: Токен сессии
            current_ip: Текущий IP-адрес
            current_user_agent: Текущий User Agent
            
        Returns:
            True если обнаружены признаки угона
        """
        try:
            cursor = self.db.conn.cursor()
            
            # Получаем историю сессии
            cursor.execute("""
                SELECT ip_address, user_agent, last_activity
                FROM user_sessions 
                WHERE session_token = ? AND is_active = 1
            """, (session_token,))
            
            session = cursor.fetchone()
            if not session:
                return True  # Сессия не найдена - подозрительно
            
            suspicious_indicators = []
            
            # Проверяем изменение IP-адреса
            if session['ip_address'] and session['ip_address'] != current_ip:
                suspicious_indicators.append('ip_change')
                logger.warning(f"Изменение IP для сессии: {session['ip_address']} -> {current_ip}")
            
            # Проверяем изменение User Agent
            if session['user_agent'] and session['user_agent'] != current_user_agent:
                # Проверяем значительные изменения (не только версии)
                if not self._user_agents_similar(session['user_agent'], current_user_agent):
                    suspicious_indicators.append('user_agent_change')
                    logger.warning(f"Значительное изменение User Agent для сессии")
            
            # Проверяем временные аномалии
            if session['last_activity']:
                last_activity = datetime.fromisoformat(session['last_activity'])
                time_since_last = (datetime.now() - last_activity).total_seconds()
                
                # Если прошло много времени, но сессия вдруг активна
                if time_since_last > 4 * 60 * 60:  # 4 часа
                    suspicious_indicators.append('long_inactivity')
            
            # Если есть подозрительные индикаторы
            if suspicious_indicators:
                log_session_event(
                    user_id=None,
                    login="unknown",
                    event_type='hijacking_detected',
                    session_token=session_token,
                    ip_address=current_ip,
                    details={
                        'indicators': suspicious_indicators,
                        'original_ip': session['ip_address'],
                        'current_ip': current_ip
                    }
                )
                
                return len(suspicious_indicators) >= 2  # Требуем 2+ индикатора
            
            return False
            
        except Exception as e:
            logger.error(f"Ошибка обнаружения угона сессии: {e}")
            return True  # В случае ошибки считаем подозрительным
    
    def _user_agents_similar(self, ua1: str, ua2: str) -> bool:
        """
        Проверяет схожесть User Agent строк.
        
        Args:
            ua1: Первый User Agent
            ua2: Второй User Agent
            
        Returns:
            True если User Agent схожи
        """
        if not ua1 or not ua2:
            return False
        
        # Извлекаем основные компоненты
        def extract_components(ua):
            components = set()
            if 'Chrome' in ua:
                components.add('Chrome')
            if 'Firefox' in ua:
                components.add('Firefox')
            if 'Safari' in ua:
                components.add('Safari')
            if 'Windows' in ua:
                components.add('Windows')
            if 'Mac' in ua:
                components.add('Mac')
            if 'Linux' in ua:
                components.add('Linux')
            return components
        
        comp1 = extract_components(ua1)
        comp2 = extract_components(ua2)
        
        # Если основные компоненты совпадают, считаем схожими
        return len(comp1.intersection(comp2)) >= min(len(comp1), len(comp2)) * 0.8
    
    def check_brute_force_protection(self, ip_address: str, user_login: str = None) -> bool:
        """
        Проверяет защиту от brute force атак.
        
        Args:
            ip_address: IP-адрес
            user_login: Логин пользователя (опционально)
            
        Returns:
            True если запрос разрешен, False если заблокирован
        """
        current_time = time.time()
        
        # Очищаем старые записи
        self._cleanup_failed_attempts(current_time)
        
        # Проверяем по IP
        ip_key = f"ip:{ip_address}"
        if ip_key in self._failed_attempts:
            attempts, lockout_until = self._failed_attempts[ip_key]
            
            if current_time < lockout_until:
                logger.warning(f"IP {ip_address} заблокирован до {datetime.fromtimestamp(lockout_until)}")
                return False
            
            if attempts >= self.max_failed_attempts:
                # Продлеваем блокировку
                self._failed_attempts[ip_key] = (attempts, current_time + self.lockout_duration)
                return False
        
        # Проверяем по пользователю (если указан)
        if user_login:
            user_key = f"user:{user_login}"
            if user_key in self._failed_attempts:
                attempts, lockout_until = self._failed_attempts[user_key]
                
                if current_time < lockout_until:
                    logger.warning(f"Пользователь {user_login} заблокирован до {datetime.fromtimestamp(lockout_until)}")
                    return False
                
                if attempts >= self.max_failed_attempts:
                    self._failed_attempts[user_key] = (attempts, current_time + self.lockout_duration)
                    return False
        
        return True
    
    def record_failed_attempt(self, ip_address: str, user_login: str = None):
        """
        Записывает неудачную попытку входа.
        
        Args:
            ip_address: IP-адрес
            user_login: Логин пользователя (опционально)
        """
        current_time = time.time()
        
        # Записываем по IP
        ip_key = f"ip:{ip_address}"
        if ip_key in self._failed_attempts:
            attempts, _ = self._failed_attempts[ip_key]
            attempts += 1
        else:
            attempts = 1
        
        lockout_until = current_time + self.lockout_duration if attempts >= self.max_failed_attempts else 0
        self._failed_attempts[ip_key] = (attempts, lockout_until)
        
        # Записываем по пользователю
        if user_login:
            user_key = f"user:{user_login}"
            if user_key in self._failed_attempts:
                attempts, _ = self._failed_attempts[user_key]
                attempts += 1
            else:
                attempts = 1
            
            lockout_until = current_time + self.lockout_duration if attempts >= self.max_failed_attempts else 0
            self._failed_attempts[user_key] = (attempts, lockout_until)
        
        logger.info(f"Записана неудачная попытка: IP {ip_address}, пользователь {user_login}")
    
    def reset_failed_attempts(self, ip_address: str = None, user_login: str = None):
        """
        Сбрасывает счетчик неудачных попыток.
        
        Args:
            ip_address: IP-адрес
            user_login: Логин пользователя
        """
        if ip_address:
            ip_key = f"ip:{ip_address}"
            self._failed_attempts.pop(ip_key, None)
        
        if user_login:
            user_key = f"user:{user_login}"
            self._failed_attempts.pop(user_key, None)
    
    def _cleanup_failed_attempts(self, current_time: float):
        """Очищает устаревшие записи неудачных попыток."""
        keys_to_remove = []
        
        for key, (attempts, lockout_until) in self._failed_attempts.items():
            if current_time > lockout_until and attempts < self.max_failed_attempts:
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self._failed_attempts[key]
    
    def generate_csrf_token(self, session_token: str) -> str:
        """
        Генерирует CSRF токен для сессии.
        
        Args:
            session_token: Токен сессии
            
        Returns:
            CSRF токен
        """
        timestamp = str(int(time.time()))
        data = f"{session_token}:{timestamp}"
        
        token = hmac.new(
            self.secret_key.encode(),
            data.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return f"{token}.{timestamp}"
    
    def validate_csrf_token(self, csrf_token: str, session_token: str, 
                           max_age: int = 3600) -> bool:
        """
        Валидирует CSRF токен.
        
        Args:
            csrf_token: CSRF токен
            session_token: Токен сессии
            max_age: Максимальный возраст токена в секундах
            
        Returns:
            True если токен валиден
        """
        try:
            token, timestamp = csrf_token.split('.')
            token_time = int(timestamp)
            current_time = int(time.time())
            
            # Проверяем возраст токена
            if current_time - token_time > max_age:
                return False
            
            # Проверяем подпись
            data = f"{session_token}:{timestamp}"
            expected_token = hmac.new(
                self.secret_key.encode(),
                data.encode(),
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(token, expected_token)
            
        except Exception:
            return False
    
    def enforce_session_limits(self, user_id: int) -> List[str]:
        """
        Применяет лимиты сессий для пользователя.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Список инвалидированных токенов
        """
        try:
            cursor = self.db.conn.cursor()
            
            # Получаем настройку лимита
            cursor.execute("""
                SELECT setting_value FROM session_settings 
                WHERE setting_name = 'max_sessions_per_user'
            """)
            
            result = cursor.fetchone()
            max_sessions = int(result['setting_value']) if result else 5
            
            # Получаем активные сессии пользователя
            cursor.execute("""
                SELECT session_token, last_activity FROM user_sessions 
                WHERE user_id = ? AND is_active = 1 AND expires_at > datetime('now')
                ORDER BY last_activity ASC
            """, (user_id,))
            
            sessions = cursor.fetchall()
            
            if len(sessions) <= max_sessions:
                return []
            
            # Инвалидируем старые сессии
            sessions_to_remove = sessions[:-max_sessions]
            invalidated_tokens = []
            
            for session in sessions_to_remove:
                cursor.execute("""
                    UPDATE user_sessions 
                    SET is_active = 0
                    WHERE session_token = ?
                """, (session['session_token'],))
                
                invalidated_tokens.append(session['session_token'])
            
            self.db.conn.commit()
            
            if invalidated_tokens:
                logger.info(f"Инвалидированы {len(invalidated_tokens)} старых сессий для пользователя {user_id}")
            
            return invalidated_tokens
            
        except Exception as e:
            logger.error(f"Ошибка применения лимитов сессий: {e}")
            return []
    
    def get_security_metrics(self) -> Dict[str, Any]:
        """
        Получает метрики безопасности.
        
        Returns:
            Словарь с метриками безопасности
        """
        current_time = time.time()
        
        # Подсчитываем активные блокировки
        active_lockouts = 0
        for attempts, lockout_until in self._failed_attempts.values():
            if current_time < lockout_until:
                active_lockouts += 1
        
        return {
            'active_lockouts': active_lockouts,
            'failed_attempts_tracked': len(self._failed_attempts),
            'token_rotation_interval': self.token_rotation_interval,
            'max_session_lifetime': self.max_session_lifetime,
            'lockout_duration': self.lockout_duration,
            'max_failed_attempts': self.max_failed_attempts,
            'timestamp': datetime.now().isoformat()
        }


# Глобальный экземпляр менеджера безопасности
_security_manager = None


def get_security_manager(db: Database = None, secret_key: str = None) -> SessionSecurityManager:
    """
    Получает глобальный экземпляр SessionSecurityManager.
    
    Args:
        db: Экземпляр базы данных
        secret_key: Секретный ключ
        
    Returns:
        Экземпляр SessionSecurityManager
    """
    global _security_manager
    
    if _security_manager is None or db is not None:
        if db is None:
            raise ValueError("Database instance required for first initialization")
        _security_manager = SessionSecurityManager(db, secret_key)
    
    return _security_manager


def protect_session(func):
    """
    Декоратор для защиты методов, работающих с сессиями.
    
    Args:
        func: Функция для защиты
        
    Returns:
        Защищенная функция
    """
    def wrapper(*args, **kwargs):
        try:
            # Получаем параметры из аргументов
            session_token = kwargs.get('session_token')
            ip_address = kwargs.get('ip_address')
            
            if session_token and ip_address:
                security_manager = get_security_manager()
                
                # Проверяем brute force защиту
                if not security_manager.check_brute_force_protection(ip_address):
                    raise SecurityError(
                        message="IP адрес временно заблокирован",
                        details={'ip_address': ip_address}
                    )
            
            return func(*args, **kwargs)
            
        except Exception as e:
            if isinstance(e, SecurityError):
                raise
            
            # Логируем ошибку безопасности
            logger.error(f"Ошибка безопасности в {func.__name__}: {e}")
            raise SecurityError(
                message="Ошибка безопасности сессии",
                original_error=e
            )
    
    return wrapper 
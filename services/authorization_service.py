"""
Сервис авторизации для управления ролями и правами доступа.

Этот модуль предоставляет высокоуровневые методы для:
- Проверки прав доступа пользователей
- Управления ролями и правами
- Кэширования разрешений для повышения производительности
- Аудита действий пользователей
"""

from typing import Dict, List, Optional, Set, Any
import logging
import threading
import time
from functools import wraps
from datetime import datetime, timedelta

from db.database import Database
# from services.base import BaseService  # не наследуемся от BaseService, так как не нужны CRUD методы
from utils.exceptions import (
    AuthenticationError, 
    InsufficientPermissionsError,
    RecordNotFoundError,
    BusinessLogicError
)
from utils.session_logger import get_session_logger

logger = logging.getLogger(__name__)


class AuthorizationService:
    """
    Сервис для управления авторизацией и правами доступа.
    
    Обеспечивает:
    - Проверку прав доступа пользователей
    - Кэширование разрешений
    - Управление ролями и правами
    - Аудит действий пользователей
    """
    
    def __init__(self, database: Database):
        """
        Инициализация сервиса авторизации.
        
        Args:
            database: Экземпляр базы данных
        """
        self.db = database
        
        # Кэш прав пользователей {user_id: {permissions: set, expires_at: datetime}}
        self._permissions_cache: Dict[int, Dict[str, Any]] = {}
        
        # Кэш ролей пользователей {user_id: {roles: list, expires_at: datetime}}
        self._roles_cache: Dict[int, Dict[str, Any]] = {}
        
        # Время жизни кэша (в секундах)
        self._cache_ttl = 300  # 5 минут
        
        # Блокировка для потокобезопасности кэша
        self._cache_lock = threading.RLock()
        
        # Множество активных сессий пользователей
        self._active_sessions: Set[int] = set()
        
        # Инициализируем сервис сессий (ленивая инициализация)
        self._session_service = None
        
        # Инициализируем логгер сессий
        self._session_logger = get_session_logger(self.db)

    @property
    def session_service(self):
        """Ленивая инициализация сервиса сессий."""
        if self._session_service is None:
            from services.session_service import SessionService
            self._session_service = SessionService(self.db)
        return self._session_service

    def authenticate_user(self, login: str, password: str, remember_me: bool = False, 
                         ip_address: str = None, user_agent: str = None) -> Optional[Dict[str, Any]]:
        """
        Аутентифицирует пользователя и создает сессию.
        
        Args:
            login: Логин пользователя
            password: Пароль пользователя
            remember_me: Флаг "Запомнить меня"
            ip_address: IP-адрес пользователя
            user_agent: Информация о браузере/приложении
            
        Returns:
            Данные пользователя с токеном сессии или None если аутентификация не удалась
            
        Raises:
            AuthenticationError: При ошибке аутентификации
        """
        try:
            user_data = self.db.verify_user(login, password)
            if user_data:
                # Создаем сессию
                session_data = self.session_service.create_session(
                    user_id=user_data['id'],
                    remember_me=remember_me,
                    ip_address=ip_address,
                    user_agent=user_agent
                )
                
                # Добавляем пользователя в активные сессии
                with self._cache_lock:
                    self._active_sessions.add(user_data['id'])
                
                # Предварительно загружаем права в кэш
                self._load_user_permissions_to_cache(user_data['id'])
                
                # Добавляем токен сессии к данным пользователя
                user_data['session_token'] = session_data['session_token']
                user_data['session_expires_at'] = session_data['expires_at']
                
                # Логируем успешный вход
                self._session_logger.log_login_attempt(
                    login=login,
                    success=True,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    session_token=session_data['session_token'],
                    user_id=user_data['id']
                )
                
                logger.info(f"Пользователь {login} успешно аутентифицирован с сессией")
                return user_data
            else:
                # Логируем неуспешный вход
                self._session_logger.log_login_attempt(
                    login=login,
                    success=False,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    reason="Неверный логин или пароль"
                )
                
                raise AuthenticationError(
                    message="Неверный логин или пароль",
                    suggestions=["Проверьте правильность ввода логина и пароля"]
                )
                
        except Exception as e:
            if isinstance(e, AuthenticationError):
                raise
            
            # Логируем ошибку аутентификации
            self._session_logger.log_login_attempt(
                login=login,
                success=False,
                ip_address=ip_address,
                user_agent=user_agent,
                reason=f"Системная ошибка: {str(e)}"
            )
            
            raise AuthenticationError(
                message="Ошибка при аутентификации",
                original_error=e
            )

    def check_permission(self, user_id: int, permission: str) -> bool:
        """
        Проверяет наличие права у пользователя.
        
        Args:
            user_id: ID пользователя
            permission: Название права
            
        Returns:
            True если право есть, False в противном случае
        """
        try:
            # Проверяем кэш
            permissions = self._get_user_permissions_from_cache(user_id)
            if permissions is not None:
                return permission in permissions
            
            # Загружаем из БД и кэшируем
            has_permission = self.db.user_has_permission(user_id, permission)
            self._load_user_permissions_to_cache(user_id)
            
            return has_permission
            
        except Exception as e:
            logger.error(f"Ошибка при проверке права {permission} для пользователя {user_id}: {e}")
            return False

    def require_permission(self, user_id: int, permission: str) -> None:
        """
        Требует наличие права у пользователя, иначе выбрасывает исключение.
        
        Args:
            user_id: ID пользователя
            permission: Название права
            
        Raises:
            InsufficientPermissionsError: Если право отсутствует
        """
        if not self.check_permission(user_id, permission):
            user = self.db.get_user_by_id(user_id)
            user_name = user['login'] if user else f'ID:{user_id}'
            
            raise InsufficientPermissionsError(
                message=f"Недостаточно прав для выполнения операции",
                details={
                    'user_id': user_id,
                    'user_name': user_name,
                    'required_permission': permission
                },
                suggestions=[
                    "Обратитесь к администратору для получения необходимых прав",
                    f"Необходимо право: {permission}"
                ]
            )

    def get_user_roles(self, user_id: int, use_cache: bool = True) -> List[Dict[str, Any]]:
        """
        Получает роли пользователя.
        
        Args:
            user_id: ID пользователя
            use_cache: Использовать кэш или загружать из БД
            
        Returns:
            Список ролей пользователя
        """
        try:
            if use_cache:
                roles = self._get_user_roles_from_cache(user_id)
                if roles is not None:
                    return roles
            
            roles = self.db.get_user_roles(user_id)
            
            # Кэшируем результат
            with self._cache_lock:
                self._roles_cache[user_id] = {
                    'roles': roles,
                    'expires_at': datetime.now() + timedelta(seconds=self._cache_ttl)
                }
            
            return roles
            
        except Exception as e:
            logger.error(f"Ошибка при получении ролей пользователя {user_id}: {e}")
            return []

    def get_user_permissions(self, user_id: int, use_cache: bool = True) -> List[Dict[str, Any]]:
        """
        Получает права пользователя.
        
        Args:
            user_id: ID пользователя
            use_cache: Использовать кэш или загружать из БД
            
        Returns:
            Список прав пользователя
        """
        try:
            if use_cache:
                cached_permissions = self._get_user_permissions_from_cache(user_id)
                if cached_permissions is not None:
                    # Преобразуем set обратно в список словарей
                    permissions = self.db.get_user_permissions(user_id)
                    return [p for p in permissions if p['name'] in cached_permissions]
            
            permissions = self.db.get_user_permissions(user_id)
            
            # Кэшируем как множество имен прав для быстрой проверки
            permission_names = {p['name'] for p in permissions}
            with self._cache_lock:
                self._permissions_cache[user_id] = {
                    'permissions': permission_names,
                    'expires_at': datetime.now() + timedelta(seconds=self._cache_ttl)
                }
            
            return permissions
            
        except Exception as e:
            logger.error(f"Ошибка при получении прав пользователя {user_id}: {e}")
            return []

    def assign_role_to_user(self, user_id: int, role_id: int, assigned_by: int) -> bool:
        """
        Назначает роль пользователю.
        
        Args:
            user_id: ID пользователя
            role_id: ID роли
            assigned_by: ID пользователя, который назначает роль
            
        Returns:
            True если роль назначена успешно
            
        Raises:
            InsufficientPermissionsError: Если нет прав на назначение ролей
            RecordNotFoundError: Если пользователь или роль не найдены
        """
        try:
            # Проверяем права назначающего
            self.require_permission(assigned_by, 'admin.roles')
            
            # Проверяем существование пользователя и роли
            user = self.db.get_user_by_id(user_id)
            if not user:
                raise RecordNotFoundError(
                    message=f"Пользователь с ID {user_id} не найден"
                )
            
            role = self.db.get_role_by_id(role_id)
            if not role:
                raise RecordNotFoundError(
                    message=f"Роль с ID {role_id} не найдена"
                )
            
            # Назначаем роль
            result = self.db.assign_role_to_user(user_id, role_id, assigned_by)
            
            if result:
                # Очищаем кэш пользователя
                self._clear_user_cache(user_id)
                
                # Логируем действие
                assigner = self.db.get_user_by_id(assigned_by)
                logger.info(
                    f"Роль '{role['display_name']}' назначена пользователю '{user['login']}' "
                    f"пользователем '{assigner['login'] if assigner else assigned_by}'"
                )
            
            return result
            
        except (InsufficientPermissionsError, RecordNotFoundError):
            raise
        except Exception as e:
            raise BusinessLogicError(
                message="Ошибка при назначении роли",
                original_error=e
            )

    def revoke_role_from_user(self, user_id: int, role_id: int, revoked_by: int) -> bool:
        """
        Отзывает роль у пользователя.
        
        Args:
            user_id: ID пользователя
            role_id: ID роли
            revoked_by: ID пользователя, который отзывает роль
            
        Returns:
            True если роль отозвана успешно
            
        Raises:
            InsufficientPermissionsError: Если нет прав на отзыв ролей
        """
        try:
            # Проверяем права отзывающего
            self.require_permission(revoked_by, 'admin.roles')
            
            # Отзываем роль
            result = self.db.revoke_role_from_user(user_id, role_id)
            
            if result:
                # Очищаем кэш пользователя
                self._clear_user_cache(user_id)
                
                # Логируем действие
                user = self.db.get_user_by_id(user_id)
                role = self.db.get_role_by_id(role_id)
                revoker = self.db.get_user_by_id(revoked_by)
                
                logger.info(
                    f"Роль '{role['display_name'] if role else role_id}' отозвана "
                    f"у пользователя '{user['login'] if user else user_id}' "
                    f"пользователем '{revoker['login'] if revoker else revoked_by}'"
                )
            
            return result
            
        except InsufficientPermissionsError:
            raise
        except Exception as e:
            raise BusinessLogicError(
                message="Ошибка при отзыве роли",
                original_error=e
            )

    def authenticate_by_session_token(self, session_token: str, ip_address: str = None) -> Optional[Dict[str, Any]]:
        """
        Аутентифицирует пользователя по токену сессии.
        
        Args:
            session_token: Токен сессии
            ip_address: IP-адрес для проверки
            
        Returns:
            Данные пользователя если токен валиден, None если не валиден
        """
        try:
            session_data = self.session_service.validate_session(session_token, ip_address)
            
            if session_data:
                user_id = session_data['user_id']
                user_login = session_data['login']
                
                # Добавляем пользователя в активные сессии
                with self._cache_lock:
                    self._active_sessions.add(user_id)
                
                # Предварительно загружаем права в кэш
                self._load_user_permissions_to_cache(user_id)
                
                # Формируем данные пользователя
                user_data = {
                    'id': user_id,
                    'login': user_login,
                    'name': session_data['name'],
                    'session_token': session_token,
                    'session_expires_at': session_data['expires_at']
                }
                
                # Логируем успешную аутентификацию по токену
                self._session_logger.log_session_event(
                    user_id=user_id,
                    login=user_login,
                    event_type='validated',
                    session_token=session_token,
                    ip_address=ip_address,
                    details={'validation_successful': True}
                )
                
                logger.info(f"Пользователь {user_login} аутентифицирован по токену сессии")
                return user_data
            else:
                # Логируем неуспешную валидацию токена
                self._session_logger.log_session_event(
                    user_id=None,
                    login="unknown",
                    event_type='validation_failed',
                    session_token=session_token,
                    ip_address=ip_address,
                    details={'validation_successful': False, 'reason': 'Invalid or expired token'}
                )
            
            return None
            
        except Exception as e:
            # Логируем ошибку валидации
            self._session_logger.log_session_event(
                user_id=None,
                login="unknown",
                event_type='validation_error',
                session_token=session_token,
                ip_address=ip_address,
                details={'error': str(e)}
            )
            
            logger.error(f"Ошибка аутентификации по токену сессии: {e}")
            return None

    def logout_user(self, user_id: int, session_token: str = None) -> None:
        """
        Выход пользователя из системы, инвалидирует сессии и очищает кэш.
        
        Args:
            user_id: ID пользователя
            session_token: Токен сессии для инвалидации (если не указан, инвалидируются все сессии)
        """
        try:
            # Получаем данные пользователя для логирования
            user_data = self.db.get_user_by_id(user_id)
            user_login = user_data['login'] if user_data else f'ID:{user_id}'
            
            with self._cache_lock:
                # Удаляем из активных сессий
                self._active_sessions.discard(user_id)
                
                # Очищаем кэш пользователя
                self._clear_user_cache(user_id)
            
            # Инвалидируем сессии
            if session_token:
                self.session_service.invalidate_session(session_token, "Manual logout")
                logout_type = "manual"
            else:
                self.session_service.invalidate_all_user_sessions(user_id, "Manual logout")
                logout_type = "manual_all"
            
            # Логируем выход
            self._session_logger.log_logout(
                user_id=user_id,
                login=user_login,
                session_token=session_token,
                logout_type=logout_type,
                reason="Manual logout"
            )
            
            logger.info(f"Пользователь {user_login} вышел из системы")
            
        except Exception as e:
            logger.error(f"Ошибка при выходе пользователя {user_id} из системы: {e}")

    def validate_session_token(self, session_token: str, ip_address: str = None) -> bool:
        """
        Проверяет валидность токена сессии.
        
        Args:
            session_token: Токен сессии
            ip_address: IP-адрес для проверки
            
        Returns:
            True если токен валиден
        """
        try:
            session_data = self.session_service.validate_session(session_token, ip_address)
            return session_data is not None
        except Exception as e:
            logger.error(f"Ошибка проверки токена сессии: {e}")
            return False

    def get_user_sessions(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Получает активные сессии пользователя.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Список активных сессий
        """
        try:
            return self.session_service.get_user_sessions(user_id, active_only=True)
        except Exception as e:
            logger.error(f"Ошибка получения сессий пользователя {user_id}: {e}")
            return []

    def invalidate_all_sessions_except_current(self, user_id: int, current_session_token: str) -> int:
        """
        Инвалидирует все сессии пользователя кроме текущей.
        
        Args:
            user_id: ID пользователя
            current_session_token: Токен текущей сессии
            
        Returns:
            Количество инвалидированных сессий
        """
        try:
            sessions = self.session_service.get_user_sessions(user_id, active_only=True)
            invalidated_count = 0
            
            for session in sessions:
                if session['session_token'] != current_session_token:
                    if self.session_service.invalidate_session(
                        session['session_token'], 
                        "Other sessions terminated"
                    ):
                        invalidated_count += 1
            
            logger.info(f"Инвалидированы {invalidated_count} сессий пользователя {user_id}")
            return invalidated_count
            
        except Exception as e:
            logger.error(f"Ошибка инвалидации сессий пользователя {user_id}: {e}")
            return 0

    def clear_all_cache(self) -> None:
        """Очищает весь кэш авторизации."""
        with self._cache_lock:
            self._permissions_cache.clear()
            self._roles_cache.clear()
        
        logger.info("Кэш авторизации очищен")

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Получает статистику кэша.
        
        Returns:
            Статистика кэша авторизации
        """
        with self._cache_lock:
            return {
                'permissions_cache_size': len(self._permissions_cache),
                'roles_cache_size': len(self._roles_cache),
                'active_sessions': len(self._active_sessions),
                'cache_ttl_seconds': self._cache_ttl
            }

    def _get_user_permissions_from_cache(self, user_id: int) -> Optional[Set[str]]:
        """
        Получает права пользователя из кэша.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Множество имен прав или None если кэш истек
        """
        with self._cache_lock:
            cache_entry = self._permissions_cache.get(user_id)
            if cache_entry and cache_entry['expires_at'] > datetime.now():
                return cache_entry['permissions']
            
            # Удаляем истекший кэш
            if cache_entry:
                del self._permissions_cache[user_id]
            
            return None

    def _get_user_roles_from_cache(self, user_id: int) -> Optional[List[Dict[str, Any]]]:
        """
        Получает роли пользователя из кэша.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Список ролей или None если кэш истек
        """
        with self._cache_lock:
            cache_entry = self._roles_cache.get(user_id)
            if cache_entry and cache_entry['expires_at'] > datetime.now():
                return cache_entry['roles']
            
            # Удаляем истекший кэш
            if cache_entry:
                del self._roles_cache[user_id]
            
            return None

    def _load_user_permissions_to_cache(self, user_id: int) -> None:
        """
        Загружает права пользователя в кэш.
        
        Args:
            user_id: ID пользователя
        """
        try:
            permissions = self.db.get_user_permissions(user_id)
            permission_names = {p['name'] for p in permissions}
            
            with self._cache_lock:
                self._permissions_cache[user_id] = {
                    'permissions': permission_names,
                    'expires_at': datetime.now() + timedelta(seconds=self._cache_ttl)
                }
                
        except Exception as e:
            logger.error(f"Ошибка при загрузке прав пользователя {user_id} в кэш: {e}")

    def _clear_user_cache(self, user_id: int) -> None:
        """
        Очищает кэш конкретного пользователя.
        
        Args:
            user_id: ID пользователя
        """
        with self._cache_lock:
            self._permissions_cache.pop(user_id, None)
            self._roles_cache.pop(user_id, None)

    def get_permissions_by_category(self, category: str) -> List[Dict[str, Any]]:
        """
        Получает права по категории.
        
        Args:
            category: Категория прав
            
        Returns:
            Список прав в категории
        """
        try:
            return self.db.get_permissions_by_category(category)
        except Exception as e:
            logger.error(f"Ошибка при получении прав категории {category}: {e}")
            return []

    def get_all_roles(self) -> List[Dict[str, Any]]:
        """
        Получает все роли в системе.
        
        Returns:
            Список всех ролей
        """
        try:
            return self.db.get_all_roles()
        except Exception as e:
            logger.error(f"Ошибка при получении всех ролей: {e}")
            return []

    def get_all_permissions(self) -> List[Dict[str, Any]]:
        """
        Получает все права в системе.
        
        Returns:
            Список всех прав
        """
        try:
            return self.db.get_all_permissions()
        except Exception as e:
            logger.error(f"Ошибка при получении всех прав: {e}")
            return []

    def is_user_active(self, user_id: int) -> bool:
        """
        Проверяет, активен ли пользователь в системе.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            True если пользователь активен
        """
        with self._cache_lock:
            return user_id in self._active_sessions


def require_permission(permission: str):
    """
    Декоратор для проверки прав доступа к методам.
    
    Args:
        permission: Требуемое право доступа
        
    Usage:
        @require_permission('materials.create')
        def create_material(self, ...):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            # Ищем user_id в аргументах
            user_id = None
            
            # Проверяем в именованных аргументах
            if 'user_id' in kwargs:
                user_id = kwargs['user_id']
            # Проверяем в self (если это метод с user_id)
            elif hasattr(self, 'current_user_id'):
                user_id = self.current_user_id
            # Проверяем первый аргумент (если это user_id)
            elif args and isinstance(args[0], int):
                user_id = args[0]
            
            if user_id is None:
                raise AuthenticationError(
                    message="Не удалось определить пользователя для проверки прав"
                )
            
            # Получаем сервис авторизации
            auth_service = None
            if hasattr(self, 'auth_service'):
                auth_service = self.auth_service
            elif hasattr(self, 'db') and hasattr(self.db, 'authorization_service'):
                auth_service = self.db.authorization_service
            
            if not auth_service:
                # Создаем временный сервис для проверки
                from db.database import Database
                db = Database()
                db.connect()
                auth_service = AuthorizationService(db)
            
            # Проверяем права
            auth_service.require_permission(user_id, permission)
            
            return func(self, *args, **kwargs)
        
        return wrapper
    return decorator 
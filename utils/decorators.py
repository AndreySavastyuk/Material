"""
Декораторы для проверки прав доступа и авторизации.

Этот модуль содержит декораторы для:
- Проверки прав доступа к методам
- Проверки ролей пользователей
- Аудита действий пользователей
- Логирования обращений к защищенным ресурсам
"""

from functools import wraps
from typing import Union, List, Callable, Any, Optional
import logging
import time
from datetime import datetime

from utils.exceptions import (
    AuthenticationError,
    InsufficientPermissionsError,
    BusinessLogicError
)

logger = logging.getLogger(__name__)


def require_permission(permission: str, user_id_arg: str = 'user_id'):
    """
    Декоратор для проверки прав доступа к методам.
    
    Args:
        permission: Требуемое право доступа (например, 'materials.create')
        user_id_arg: Имя аргумента, содержащего user_id (по умолчанию 'user_id')
        
    Usage:
        @require_permission('materials.create')
        def create_material(self, user_id: int, material_data: dict):
            ...
            
        @require_permission('materials.edit', user_id_arg='current_user')
        def edit_material(self, current_user: int, material_id: int, data: dict):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Получаем user_id из аргументов
            user_id = _extract_user_id(args, kwargs, user_id_arg, func.__name__)
            
            # Получаем сервис авторизации
            auth_service = _get_auth_service(args)
            
            # Проверяем права
            if not auth_service.check_permission(user_id, permission):
                user = auth_service.db.get_user_by_id(user_id)
                user_name = user['login'] if user else f'ID:{user_id}'
                
                logger.warning(
                    f"Отказано в доступе: пользователь {user_name} "
                    f"попытался выполнить {func.__name__} без права {permission}"
                )
                
                raise InsufficientPermissionsError(
                    message=f"Недостаточно прав для выполнения операции",
                    details={
                        'user_id': user_id,
                        'user_name': user_name,
                        'required_permission': permission,
                        'function': func.__name__
                    },
                    suggestions=[
                        "Обратитесь к администратору для получения необходимых прав",
                        f"Необходимо право: {permission}"
                    ]
                )
            
            # Логируем успешное выполнение
            user = auth_service.db.get_user_by_id(user_id)
            user_name = user['login'] if user else f'ID:{user_id}'
            logger.info(f"Пользователь {user_name} выполнил {func.__name__} с правом {permission}")
            
            return func(*args, **kwargs)
        
        # Добавляем метаданные к функции
        wrapper._required_permission = permission
        wrapper._user_id_arg = user_id_arg
        
        return wrapper
    return decorator


def require_any_permission(permissions: List[str], user_id_arg: str = 'user_id'):
    """
    Декоратор для проверки наличия любого из указанных прав.
    
    Args:
        permissions: Список прав, любое из которых разрешает доступ
        user_id_arg: Имя аргумента, содержащего user_id
        
    Usage:
        @require_any_permission(['materials.view', 'materials.edit'])
        def get_material(self, user_id: int, material_id: int):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Получаем user_id из аргументов
            user_id = _extract_user_id(args, kwargs, user_id_arg, func.__name__)
            
            # Получаем сервис авторизации
            auth_service = _get_auth_service(args)
            
            # Проверяем любое из прав
            has_permission = any(
                auth_service.check_permission(user_id, perm) 
                for perm in permissions
            )
            
            if not has_permission:
                user = auth_service.db.get_user_by_id(user_id)
                user_name = user['login'] if user else f'ID:{user_id}'
                
                logger.warning(
                    f"Отказано в доступе: пользователь {user_name} "
                    f"попытался выполнить {func.__name__} без одного из прав {permissions}"
                )
                
                raise InsufficientPermissionsError(
                    message=f"Недостаточно прав для выполнения операции",
                    details={
                        'user_id': user_id,
                        'user_name': user_name,
                        'required_permissions': permissions,
                        'function': func.__name__
                    },
                    suggestions=[
                        "Обратитесь к администратору для получения необходимых прав",
                        f"Необходимо одно из прав: {', '.join(permissions)}"
                    ]
                )
            
            return func(*args, **kwargs)
        
        wrapper._required_permissions = permissions
        wrapper._user_id_arg = user_id_arg
        
        return wrapper
    return decorator


def require_all_permissions(permissions: List[str], user_id_arg: str = 'user_id'):
    """
    Декоратор для проверки наличия всех указанных прав.
    
    Args:
        permissions: Список прав, все из которых требуются для доступа
        user_id_arg: Имя аргумента, содержащего user_id
        
    Usage:
        @require_all_permissions(['materials.edit', 'materials.approve'])
        def approve_material(self, user_id: int, material_id: int):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Получаем user_id из аргументов
            user_id = _extract_user_id(args, kwargs, user_id_arg, func.__name__)
            
            # Получаем сервис авторизации
            auth_service = _get_auth_service(args)
            
            # Проверяем все права
            missing_permissions = []
            for permission in permissions:
                if not auth_service.check_permission(user_id, permission):
                    missing_permissions.append(permission)
            
            if missing_permissions:
                user = auth_service.db.get_user_by_id(user_id)
                user_name = user['login'] if user else f'ID:{user_id}'
                
                logger.warning(
                    f"Отказано в доступе: пользователь {user_name} "
                    f"попытался выполнить {func.__name__} без прав {missing_permissions}"
                )
                
                raise InsufficientPermissionsError(
                    message=f"Недостаточно прав для выполнения операции",
                    details={
                        'user_id': user_id,
                        'user_name': user_name,
                        'required_permissions': permissions,
                        'missing_permissions': missing_permissions,
                        'function': func.__name__
                    },
                    suggestions=[
                        "Обратитесь к администратору для получения необходимых прав",
                        f"Отсутствуют права: {', '.join(missing_permissions)}"
                    ]
                )
            
            return func(*args, **kwargs)
        
        wrapper._required_permissions = permissions
        wrapper._user_id_arg = user_id_arg
        
        return wrapper
    return decorator


def require_role(role: str, user_id_arg: str = 'user_id'):
    """
    Декоратор для проверки роли пользователя.
    
    Args:
        role: Требуемая роль (например, 'admin')
        user_id_arg: Имя аргумента, содержащего user_id
        
    Usage:
        @require_role('admin')
        def admin_function(self, user_id: int):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Получаем user_id из аргументов
            user_id = _extract_user_id(args, kwargs, user_id_arg, func.__name__)
            
            # Получаем сервис авторизации
            auth_service = _get_auth_service(args)
            
            # Получаем роли пользователя
            user_roles = auth_service.get_user_roles(user_id)
            role_names = {r['name'] for r in user_roles}
            
            if role not in role_names:
                user = auth_service.db.get_user_by_id(user_id)
                user_name = user['login'] if user else f'ID:{user_id}'
                
                logger.warning(
                    f"Отказано в доступе: пользователь {user_name} "
                    f"попытался выполнить {func.__name__} без роли {role}"
                )
                
                raise InsufficientPermissionsError(
                    message=f"Недостаточно прав для выполнения операции",
                    details={
                        'user_id': user_id,
                        'user_name': user_name,
                        'required_role': role,
                        'user_roles': list(role_names),
                        'function': func.__name__
                    },
                    suggestions=[
                        "Обратитесь к администратору для получения необходимой роли",
                        f"Необходима роль: {role}"
                    ]
                )
            
            return func(*args, **kwargs)
        
        wrapper._required_role = role
        wrapper._user_id_arg = user_id_arg
        
        return wrapper
    return decorator


def audit_action(action: str, resource_type: str = None, user_id_arg: str = 'user_id'):
    """
    Декоратор для аудита действий пользователей.
    
    Args:
        action: Тип действия (например, 'create', 'update', 'delete')
        resource_type: Тип ресурса (например, 'material', 'user')
        user_id_arg: Имя аргумента, содержащего user_id
        
    Usage:
        @audit_action('create', 'material')
        def create_material(self, user_id: int, material_data: dict):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            
            # Получаем user_id из аргументов
            user_id = _extract_user_id(args, kwargs, user_id_arg, func.__name__)
            
            # Получаем сервис авторизации для логирования
            auth_service = _get_auth_service(args)
            user = auth_service.db.get_user_by_id(user_id) if auth_service else None
            user_name = user['login'] if user else f'ID:{user_id}'
            
            # Формируем описание действия
            action_description = f"{action}"
            if resource_type:
                action_description = f"{action} {resource_type}"
            
            logger.info(
                f"AUDIT: Пользователь {user_name} начал выполнение '{action_description}' "
                f"через {func.__name__}"
            )
            
            try:
                # Выполняем функцию
                result = func(*args, **kwargs)
                
                # Логируем успешное выполнение
                duration = time.time() - start_time
                logger.info(
                    f"AUDIT: Пользователь {user_name} успешно выполнил '{action_description}' "
                    f"за {duration:.2f}с"
                )
                
                return result
                
            except Exception as e:
                # Логируем ошибку
                duration = time.time() - start_time
                logger.error(
                    f"AUDIT: Пользователь {user_name} не смог выполнить '{action_description}' "
                    f"за {duration:.2f}с. Ошибка: {e}"
                )
                raise
        
        wrapper._audit_action = action
        wrapper._audit_resource_type = resource_type
        wrapper._user_id_arg = user_id_arg
        
        return wrapper
    return decorator


def measure_performance(log_slow_threshold: float = 1.0):
    """
    Декоратор для измерения производительности методов.
    
    Args:
        log_slow_threshold: Порог в секундах, после которого операция считается медленной
        
    Usage:
        @measure_performance(log_slow_threshold=2.0)
        def slow_operation(self):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                
                if duration > log_slow_threshold:
                    logger.warning(
                        f"PERFORMANCE: Медленная операция {func.__name__} "
                        f"выполнялась {duration:.2f}с (порог: {log_slow_threshold}с)"
                    )
                else:
                    logger.debug(
                        f"PERFORMANCE: Операция {func.__name__} "
                        f"выполнена за {duration:.2f}с"
                    )
        
        return wrapper
    return decorator


def _extract_user_id(args: tuple, kwargs: dict, user_id_arg: str, func_name: str) -> int:
    """
    Извлекает user_id из аргументов функции.
    
    Args:
        args: Позиционные аргументы
        kwargs: Именованные аргументы
        user_id_arg: Имя аргумента с user_id
        func_name: Имя функции (для ошибок)
        
    Returns:
        ID пользователя
        
    Raises:
        AuthenticationError: Если user_id не найден
    """
    # Проверяем в именованных аргументах
    if user_id_arg in kwargs:
        user_id = kwargs[user_id_arg]
        if isinstance(user_id, int):
            return user_id
    
    # Проверяем в self (если это метод с атрибутом current_user_id)
    if args and hasattr(args[0], 'current_user_id'):
        return args[0].current_user_id
    
    # Проверяем, есть ли user_id в первых аргументах
    for i, arg in enumerate(args):
        if isinstance(arg, int) and i > 0:  # Пропускаем self
            return arg
    
    raise AuthenticationError(
        message=f"Не удалось определить пользователя для проверки прав в функции {func_name}",
        details={
            'function': func_name,
            'user_id_arg': user_id_arg,
            'available_kwargs': list(kwargs.keys())
        },
        suggestions=[
            f"Убедитесь, что функция принимает аргумент '{user_id_arg}'",
            "Или установите атрибут 'current_user_id' в объекте",
            "Или передайте user_id как именованный аргумент"
        ]
    )


def _get_auth_service(args: tuple):
    """
    Получает сервис авторизации из аргументов.
    
    Args:
        args: Позиционные аргументы функции
        
    Returns:
        Сервис авторизации
        
    Raises:
        BusinessLogicError: Если сервис не найден
    """
    # Проверяем в self
    if args and hasattr(args[0], 'auth_service'):
        return args[0].auth_service
    
    # Проверяем в db объекте
    if args and hasattr(args[0], 'db'):
        # Создаем временный сервис авторизации
        from services.authorization_service import AuthorizationService
        return AuthorizationService(args[0].db)
    
    # Создаем новый сервис авторизации
    try:
        from db.database import Database
        from services.authorization_service import AuthorizationService
        
        db = Database()
        db.connect()
        return AuthorizationService(db)
    except Exception as e:
        raise BusinessLogicError(
            message="Не удалось получить сервис авторизации",
            original_error=e,
            suggestions=[
                "Убедитесь, что объект имеет атрибут 'auth_service' или 'db'",
                "Или инициализируйте сервис авторизации вручную"
            ]
        )


def get_function_permissions(func: Callable) -> dict:
    """
    Получает информацию о правах, требуемых функцией.
    
    Args:
        func: Функция для анализа
        
    Returns:
        Словарь с информацией о правах
    """
    permissions_info = {
        'has_permission_check': False,
        'required_permission': None,
        'required_permissions': None,
        'required_role': None,
        'user_id_arg': None,
        'audit_action': None,
        'audit_resource_type': None
    }
    
    # Проверяем метаданные декораторов
    if hasattr(func, '_required_permission'):
        permissions_info['has_permission_check'] = True
        permissions_info['required_permission'] = func._required_permission
        permissions_info['user_id_arg'] = getattr(func, '_user_id_arg', 'user_id')
    
    if hasattr(func, '_required_permissions'):
        permissions_info['has_permission_check'] = True
        permissions_info['required_permissions'] = func._required_permissions
        permissions_info['user_id_arg'] = getattr(func, '_user_id_arg', 'user_id')
    
    if hasattr(func, '_required_role'):
        permissions_info['has_permission_check'] = True
        permissions_info['required_role'] = func._required_role
        permissions_info['user_id_arg'] = getattr(func, '_user_id_arg', 'user_id')
    
    if hasattr(func, '_audit_action'):
        permissions_info['audit_action'] = func._audit_action
        permissions_info['audit_resource_type'] = getattr(func, '_audit_resource_type', None)
    
    return permissions_info 
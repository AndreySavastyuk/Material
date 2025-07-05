"""
Тесты для системы ролей и прав доступа.

Этот модуль содержит тесты для:
- Миграции системы ролей
- Методов работы с ролями и правами в базе данных
- Сервиса авторизации
- Декораторов проверки прав
- Интеграции с GUI
"""

import pytest
import os
import tempfile
import sqlite3
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, List, Any

from db.database import Database
from services.authorization_service import AuthorizationService
from utils.decorators import require_permission, require_any_permission, require_all_permissions
from utils.exceptions import (
    AuthenticationError, 
    InsufficientPermissionsError, 
    RecordNotFoundError,
    BusinessLogicError
)


class TestRolesPermissionsMigration:
    """Тесты миграции системы ролей и прав доступа."""
    
    def test_migration_creates_tables(self, temp_db):
        """Тест создания таблиц миграцией."""
        # Импортируем и выполняем миграцию
        from migrations import migration_003_roles_permissions
        up = migration_003_roles_permissions.up
        
        connection = temp_db.conn
        up(connection)
        
        # Проверяем, что таблицы созданы
        cursor = connection.cursor()
        
        # Проверяем таблицу roles
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='roles'")
        assert cursor.fetchone() is not None
        
        # Проверяем таблицу permissions
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='permissions'")
        assert cursor.fetchone() is not None
        
        # Проверяем таблицу role_permissions
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='role_permissions'")
        assert cursor.fetchone() is not None
        
        # Проверяем таблицу user_roles
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_roles'")
        assert cursor.fetchone() is not None

    def test_migration_creates_default_roles(self, temp_db):
        """Тест создания базовых ролей."""
        from migrations import migration_003_roles_permissions
        up = migration_003_roles_permissions.up
        
        connection = temp_db.conn
        up(connection)
        
        cursor = connection.cursor()
        cursor.execute("SELECT name, display_name FROM roles ORDER BY name")
        roles = cursor.fetchall()
        
        expected_roles = {
            'admin': 'Администратор',
            'lab_technician': 'Лаборант',
            'operator': 'Оператор',
            'otk_master': 'Мастер ОТК',
            'viewer': 'Наблюдатель'
        }
        
        assert len(roles) == len(expected_roles)
        for role in roles:
            assert role['name'] in expected_roles
            assert role['display_name'] == expected_roles[role['name']]

    def test_migration_creates_default_permissions(self, temp_db):
        """Тест создания базовых прав."""
        from migrations import migration_003_roles_permissions
        up = migration_003_roles_permissions.up
        
        connection = temp_db.conn
        up(connection)
        
        cursor = connection.cursor()
        cursor.execute("SELECT name, category FROM permissions ORDER BY category, name")
        permissions = cursor.fetchall()
        
        # Проверяем, что созданы права для основных категорий
        categories = {p['category'] for p in permissions}
        expected_categories = {
            'materials', 'lab', 'quality', 'documents', 
            'reports', 'admin', 'suppliers'
        }
        
        assert expected_categories.issubset(categories)
        
        # Проверяем наличие ключевых прав
        permission_names = {p['name'] for p in permissions}
        key_permissions = {
            'materials.view', 'materials.create', 'materials.edit', 'materials.delete',
            'lab.view', 'lab.create', 'lab.edit', 'lab.approve',
            'quality.view', 'quality.create', 'admin.users', 'admin.roles'
        }
        
        assert key_permissions.issubset(permission_names)

    def test_migration_assigns_permissions_to_roles(self, temp_db):
        """Тест назначения прав ролям."""
        from migrations import migration_003_roles_permissions
        up = migration_003_roles_permissions.up
        
        connection = temp_db.conn
        up(connection)
        
        cursor = connection.cursor()
        
        # Проверяем, что у администратора есть все права
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM role_permissions rp
            JOIN roles r ON rp.role_id = r.id
            WHERE r.name = 'admin'
        """)
        admin_permissions_count = cursor.fetchone()['count']
        
        # У администратора должно быть много прав
        assert admin_permissions_count > 20
        
        # Проверяем, что у наблюдателя есть только права на просмотр
        cursor.execute("""
            SELECT p.name
            FROM role_permissions rp
            JOIN roles r ON rp.role_id = r.id
            JOIN permissions p ON rp.permission_id = p.id
            WHERE r.name = 'viewer'
        """)
        viewer_permissions = [row['name'] for row in cursor.fetchall()]
        
        # У наблюдателя должны быть только права на просмотр
        assert 'materials.view' in viewer_permissions
        assert 'lab.view' in viewer_permissions
        assert 'materials.create' not in viewer_permissions
        assert 'admin.users' not in viewer_permissions


class TestDatabaseRolesMethods:
    """Тесты методов работы с ролями в базе данных."""
    
    def test_get_user_roles(self, temp_db_with_roles):
        """Тест получения ролей пользователя."""
        # Создаем пользователя
        user_id = temp_db_with_roles.create_user('testuser', 'password123', 'user', 'Test User')
        
        # Получаем роль viewer
        viewer_role = temp_db_with_roles.get_role_by_name('viewer')
        
        # Назначаем роль пользователю
        temp_db_with_roles.assign_role_to_user(user_id, viewer_role['id'])
        
        # Получаем роли пользователя
        roles = temp_db_with_roles.get_user_roles(user_id)
        
        assert len(roles) == 1
        assert roles[0]['name'] == 'viewer'
        assert roles[0]['display_name'] == 'Наблюдатель'

    def test_get_user_permissions(self, temp_db_with_roles):
        """Тест получения прав пользователя."""
        # Создаем пользователя
        user_id = temp_db_with_roles.create_user('testuser', 'password123', 'user', 'Test User')
        
        # Получаем роль viewer
        viewer_role = temp_db_with_roles.get_role_by_name('viewer')
        
        # Назначаем роль пользователю
        temp_db_with_roles.assign_role_to_user(user_id, viewer_role['id'])
        
        # Получаем права пользователя
        permissions = temp_db_with_roles.get_user_permissions(user_id)
        
        assert len(permissions) > 0
        permission_names = {p['name'] for p in permissions}
        assert 'materials.view' in permission_names
        assert 'lab.view' in permission_names

    def test_user_has_permission(self, temp_db_with_roles):
        """Тест проверки права пользователя."""
        # Создаем пользователя
        user_id = temp_db_with_roles.create_user('testuser', 'password123', 'user', 'Test User')
        
        # Получаем роль viewer
        viewer_role = temp_db_with_roles.get_role_by_name('viewer')
        
        # Назначаем роль пользователю
        temp_db_with_roles.assign_role_to_user(user_id, viewer_role['id'])
        
        # Проверяем права
        assert temp_db_with_roles.user_has_permission(user_id, 'materials.view')
        assert not temp_db_with_roles.user_has_permission(user_id, 'materials.create')
        assert not temp_db_with_roles.user_has_permission(user_id, 'admin.users')

    def test_assign_role_to_user(self, temp_db_with_roles):
        """Тест назначения роли пользователю."""
        # Создаем пользователя
        user_id = temp_db_with_roles.create_user('testuser', 'password123', 'user', 'Test User')
        
        # Получаем роль
        operator_role = temp_db_with_roles.get_role_by_name('operator')
        
        # Назначаем роль
        result = temp_db_with_roles.assign_role_to_user(user_id, operator_role['id'])
        assert result is True
        
        # Проверяем, что роль назначена
        roles = temp_db_with_roles.get_user_roles(user_id)
        assert len(roles) == 1
        assert roles[0]['name'] == 'operator'

    def test_revoke_role_from_user(self, temp_db_with_roles):
        """Тест отзыва роли у пользователя."""
        # Создаем пользователя
        user_id = temp_db_with_roles.create_user('testuser', 'password123', 'user', 'Test User')
        
        # Получаем роль
        operator_role = temp_db_with_roles.get_role_by_name('operator')
        
        # Назначаем роль
        temp_db_with_roles.assign_role_to_user(user_id, operator_role['id'])
        
        # Отзываем роль
        result = temp_db_with_roles.revoke_role_from_user(user_id, operator_role['id'])
        assert result is True
        
        # Проверяем, что роль отозвана
        roles = temp_db_with_roles.get_user_roles(user_id)
        assert len(roles) == 0

    def test_create_role(self, temp_db_with_roles):
        """Тест создания новой роли."""
        role_id = temp_db_with_roles.create_role(
            'custom_role', 
            'Пользовательская роль', 
            'Описание роли'
        )
        
        assert role_id is not None
        
        # Проверяем, что роль создана
        role = temp_db_with_roles.get_role_by_id(role_id)
        assert role['name'] == 'custom_role'
        assert role['display_name'] == 'Пользовательская роль'
        assert role['description'] == 'Описание роли'

    def test_create_permission(self, temp_db_with_roles):
        """Тест создания нового права."""
        permission_id = temp_db_with_roles.create_permission(
            'custom.permission',
            'Пользовательское право',
            'Описание права',
            'custom'
        )
        
        assert permission_id is not None
        
        # Проверяем, что право создано
        cursor = temp_db_with_roles.conn.cursor()
        cursor.execute('SELECT * FROM permissions WHERE id = ?', (permission_id,))
        permission = cursor.fetchone()
        
        assert permission['name'] == 'custom.permission'
        assert permission['display_name'] == 'Пользовательское право'
        assert permission['category'] == 'custom'


class TestAuthorizationService:
    """Тесты сервиса авторизации."""
    
    def test_authenticate_user_success(self, temp_db_with_roles):
        """Тест успешной аутентификации пользователя."""
        # Создаем пользователя
        user_id = temp_db_with_roles.create_user('testuser', 'password123', 'user', 'Test User')
        
        # Создаем сервис
        auth_service = AuthorizationService(temp_db_with_roles)
        
        # Аутентифицируем пользователя
        user_data = auth_service.authenticate_user('testuser', 'password123')
        
        assert user_data is not None
        assert user_data['id'] == user_id
        assert user_data['login'] == 'testuser'
        assert auth_service.is_user_active(user_id)

    def test_authenticate_user_failure(self, temp_db_with_roles):
        """Тест неуспешной аутентификации."""
        # Создаем сервис
        auth_service = AuthorizationService(temp_db_with_roles)
        
        # Пытаемся аутентифицировать несуществующего пользователя
        with pytest.raises(AuthenticationError):
            auth_service.authenticate_user('nonexistent', 'password')

    def test_check_permission(self, temp_db_with_roles):
        """Тест проверки прав."""
        # Создаем пользователя с ролью
        user_id = temp_db_with_roles.create_user('testuser', 'password123', 'user', 'Test User')
        viewer_role = temp_db_with_roles.get_role_by_name('viewer')
        temp_db_with_roles.assign_role_to_user(user_id, viewer_role['id'])
        
        # Создаем сервис
        auth_service = AuthorizationService(temp_db_with_roles)
        
        # Проверяем права
        assert auth_service.check_permission(user_id, 'materials.view')
        assert not auth_service.check_permission(user_id, 'materials.create')

    def test_require_permission_success(self, temp_db_with_roles):
        """Тест успешной проверки требуемого права."""
        # Создаем пользователя с ролью
        user_id = temp_db_with_roles.create_user('testuser', 'password123', 'user', 'Test User')
        viewer_role = temp_db_with_roles.get_role_by_name('viewer')
        temp_db_with_roles.assign_role_to_user(user_id, viewer_role['id'])
        
        # Создаем сервис
        auth_service = AuthorizationService(temp_db_with_roles)
        
        # Не должно быть исключения
        auth_service.require_permission(user_id, 'materials.view')

    def test_require_permission_failure(self, temp_db_with_roles):
        """Тест неуспешной проверки требуемого права."""
        # Создаем пользователя с ролью
        user_id = temp_db_with_roles.create_user('testuser', 'password123', 'user', 'Test User')
        viewer_role = temp_db_with_roles.get_role_by_name('viewer')
        temp_db_with_roles.assign_role_to_user(user_id, viewer_role['id'])
        
        # Создаем сервис
        auth_service = AuthorizationService(temp_db_with_roles)
        
        # Должно быть исключение
        with pytest.raises(InsufficientPermissionsError):
            auth_service.require_permission(user_id, 'materials.create')

    def test_assign_role_to_user_with_permissions(self, temp_db_with_roles):
        """Тест назначения роли с проверкой прав."""
        # Получаем существующего администратора (создается автоматически)
        admin_user = temp_db_with_roles.get_user_by_login('admin')
        admin_id = admin_user['id']
        admin_role = temp_db_with_roles.get_role_by_name('admin')
        temp_db_with_roles.assign_role_to_user(admin_id, admin_role['id'])
        
        # Создаем обычного пользователя
        user_id = temp_db_with_roles.create_user('testuser', 'password123', 'user', 'Test User')
        
        # Создаем сервис
        auth_service = AuthorizationService(temp_db_with_roles)
        
        # Администратор назначает роль пользователю
        operator_role = temp_db_with_roles.get_role_by_name('operator')
        result = auth_service.assign_role_to_user(user_id, operator_role['id'], admin_id)
        
        assert result is True
        
        # Проверяем, что роль назначена
        roles = temp_db_with_roles.get_user_roles(user_id)
        assert len(roles) == 1
        assert roles[0]['name'] == 'operator'

    def test_assign_role_insufficient_permissions(self, temp_db_with_roles):
        """Тест назначения роли без достаточных прав."""
        # Создаем обычного пользователя
        user_id = temp_db_with_roles.create_user('testuser', 'password123', 'user', 'Test User')
        viewer_role = temp_db_with_roles.get_role_by_name('viewer')
        temp_db_with_roles.assign_role_to_user(user_id, viewer_role['id'])
        
        # Создаем другого пользователя
        target_user_id = temp_db_with_roles.create_user('target', 'password123', 'user', 'Target User')
        
        # Создаем сервис
        auth_service = AuthorizationService(temp_db_with_roles)
        
        # Обычный пользователь пытается назначить роль
        operator_role = temp_db_with_roles.get_role_by_name('operator')
        
        with pytest.raises(InsufficientPermissionsError):
            auth_service.assign_role_to_user(target_user_id, operator_role['id'], user_id)

    def test_cache_functionality(self, temp_db_with_roles):
        """Тест работы кэша."""
        # Создаем пользователя с ролью
        user_id = temp_db_with_roles.create_user('testuser', 'password123', 'user', 'Test User')
        viewer_role = temp_db_with_roles.get_role_by_name('viewer')
        temp_db_with_roles.assign_role_to_user(user_id, viewer_role['id'])
        
        # Создаем сервис
        auth_service = AuthorizationService(temp_db_with_roles)
        
        # Первый запрос - загрузка в кэш
        permissions1 = auth_service.get_user_permissions(user_id)
        
        # Второй запрос - из кэша
        permissions2 = auth_service.get_user_permissions(user_id)
        
        # Результаты должны совпадать
        assert len(permissions1) == len(permissions2)
        assert {p['name'] for p in permissions1} == {p['name'] for p in permissions2}
        
        # Проверяем статистику кэша
        cache_stats = auth_service.get_cache_stats()
        assert cache_stats['permissions_cache_size'] > 0

    def test_logout_user(self, temp_db_with_roles):
        """Тест выхода пользователя."""
        # Создаем пользователя
        user_id = temp_db_with_roles.create_user('testuser', 'password123', 'user', 'Test User')
        
        # Создаем сервис
        auth_service = AuthorizationService(temp_db_with_roles)
        
        # Аутентифицируем пользователя
        auth_service.authenticate_user('testuser', 'password123')
        assert auth_service.is_user_active(user_id)
        
        # Выходим
        auth_service.logout_user(user_id)
        assert not auth_service.is_user_active(user_id)


class TestPermissionDecorators:
    """Тесты декораторов проверки прав."""
    
    def test_require_permission_decorator_success(self, temp_db_with_roles):
        """Тест успешного декоратора проверки прав."""
        # Создаем пользователя с правами
        user_id = temp_db_with_roles.create_user('testuser', 'password123', 'user', 'Test User')
        viewer_role = temp_db_with_roles.get_role_by_name('viewer')
        temp_db_with_roles.assign_role_to_user(user_id, viewer_role['id'])
        
        # Создаем реальный сервис авторизации
        auth_service = AuthorizationService(temp_db_with_roles)
        
        # Создаем класс с сервисом авторизации
        class TestService:
            def __init__(self, auth_service):
                self.auth_service = auth_service
                
            @require_permission('materials.view')
            def test_method(self, user_id: int):
                return "success"
        
        # Создаем экземпляр сервиса
        test_service = TestService(auth_service)
        
        # Выполняем функцию
        result = test_service.test_method(user_id)
        assert result == "success"

    def test_require_permission_decorator_failure(self, temp_db_with_roles):
        """Тест неуспешного декоратора проверки прав."""
        # Создаем пользователя с ограниченными правами
        user_id = temp_db_with_roles.create_user('testuser', 'password123', 'user', 'Test User')
        viewer_role = temp_db_with_roles.get_role_by_name('viewer')
        temp_db_with_roles.assign_role_to_user(user_id, viewer_role['id'])
        
        # Создаем реальный сервис авторизации
        auth_service = AuthorizationService(temp_db_with_roles)
        
        # Создаем класс с сервисом авторизации
        class TestService:
            def __init__(self, auth_service):
                self.auth_service = auth_service
                
            @require_permission('materials.create')
            def test_method(self, user_id: int):
                return "success"
        
        # Создаем экземпляр сервиса
        test_service = TestService(auth_service)
        
        # Выполняем функцию - должно быть исключение
        with pytest.raises(InsufficientPermissionsError):
            test_service.test_method(user_id)

    def test_require_any_permission_decorator(self, temp_db_with_roles):
        """Тест декоратора проверки любого из прав."""
        # Создаем пользователя с правами
        user_id = temp_db_with_roles.create_user('testuser', 'password123', 'user', 'Test User')
        viewer_role = temp_db_with_roles.get_role_by_name('viewer')
        temp_db_with_roles.assign_role_to_user(user_id, viewer_role['id'])
        
        # Создаем реальный сервис авторизации
        auth_service = AuthorizationService(temp_db_with_roles)
        
        # Создаем класс с сервисом авторизации
        class TestService:
            def __init__(self, auth_service):
                self.auth_service = auth_service
                
            @require_any_permission(['materials.view', 'materials.create'])
            def test_method(self, user_id: int):
                return "success"
        
        # Создаем экземпляр сервиса
        test_service = TestService(auth_service)
        
        # Выполняем функцию - должно пройти, т.к. есть materials.view
        result = test_service.test_method(user_id)
        assert result == "success"

    def test_require_all_permissions_decorator(self, temp_db_with_roles):
        """Тест декоратора проверки всех прав."""
        # Создаем пользователя с правами
        user_id = temp_db_with_roles.create_user('testuser', 'password123', 'user', 'Test User')
        viewer_role = temp_db_with_roles.get_role_by_name('viewer')
        temp_db_with_roles.assign_role_to_user(user_id, viewer_role['id'])
        
        # Создаем реальный сервис авторизации
        auth_service = AuthorizationService(temp_db_with_roles)
        
        # Создаем класс с сервисом авторизации
        class TestService:
            def __init__(self, auth_service):
                self.auth_service = auth_service
                
            @require_all_permissions(['materials.view', 'materials.create'])
            def test_method(self, user_id: int):
                return "success"
        
        # Создаем экземпляр сервиса
        test_service = TestService(auth_service)
        
        # Выполняем функцию - должно упасть, т.к. нет materials.create
        with pytest.raises(InsufficientPermissionsError):
            test_service.test_method(user_id)


class TestRolePermissionIntegration:
    """Интеграционные тесты системы ролей и прав."""
    
    def test_complete_workflow(self, temp_db_with_roles):
        """Тест полного рабочего процесса с ролями и правами."""
        # Получаем существующего администратора (создается автоматически)
        admin_user = temp_db_with_roles.get_user_by_login('admin')
        admin_id = admin_user['id']
        admin_role = temp_db_with_roles.get_role_by_name('admin')
        temp_db_with_roles.assign_role_to_user(admin_id, admin_role['id'])
        
        # Создаем обычного пользователя
        user_id = temp_db_with_roles.create_user('user', 'user123', 'user', 'User')
        
        # Создаем сервис
        auth_service = AuthorizationService(temp_db_with_roles)
        
        # Администратор создает новую роль
        new_role_id = temp_db_with_roles.create_role('manager', 'Менеджер', 'Роль менеджера')
        assert new_role_id is not None
        
        # Администратор создает новое право
        new_permission_id = temp_db_with_roles.create_permission(
            'reports.manage', 'Управление отчетами', 'Управление отчетами', 'reports'
        )
        assert new_permission_id is not None
        
        # Администратор назначает право роли
        result = temp_db_with_roles.assign_permission_to_role(new_role_id, new_permission_id)
        assert result is True
        
        # Администратор назначает роль пользователю
        result = auth_service.assign_role_to_user(user_id, new_role_id, admin_id)
        assert result is True
        
        # Проверяем, что пользователь получил новое право
        assert temp_db_with_roles.user_has_permission(user_id, 'reports.manage')
        
        # Проверяем через сервис
        assert auth_service.check_permission(user_id, 'reports.manage')
        
        # Пользователь может выполнить операцию, требующую нового права
        auth_service.require_permission(user_id, 'reports.manage')  # Не должно быть исключения

    def test_permission_inheritance(self, temp_db_with_roles):
        """Тест наследования прав через роли."""
        # Создаем пользователя с несколькими ролями
        user_id = temp_db_with_roles.create_user('testuser', 'password123', 'user', 'Test User')
        
        # Назначаем роль viewer
        viewer_role = temp_db_with_roles.get_role_by_name('viewer')
        temp_db_with_roles.assign_role_to_user(user_id, viewer_role['id'])
        
        # Назначаем роль operator (дополнительно)
        operator_role = temp_db_with_roles.get_role_by_name('operator')
        temp_db_with_roles.assign_role_to_user(user_id, operator_role['id'])
        
        # Пользователь должен иметь права от обеих ролей
        user_permissions = temp_db_with_roles.get_user_permissions(user_id)
        permission_names = {p['name'] for p in user_permissions}
        
        # Права от viewer
        assert 'materials.view' in permission_names
        assert 'lab.view' in permission_names
        
        # Права от operator
        assert 'materials.create' in permission_names
        assert 'lab.create' in permission_names

    def test_role_expiration(self, temp_db_with_roles):
        """Тест истечения срока действия ролей."""
        from datetime import datetime, timedelta
        
        # Создаем пользователя
        user_id = temp_db_with_roles.create_user('testuser', 'password123', 'user', 'Test User')
        
        # Назначаем роль с истекшим сроком
        operator_role = temp_db_with_roles.get_role_by_name('operator')
        expired_date = (datetime.now() - timedelta(days=1)).isoformat()
        
        temp_db_with_roles.assign_role_to_user(user_id, operator_role['id'], expires_at=expired_date)
        
        # Проверяем, что роль не активна
        roles = temp_db_with_roles.get_user_roles(user_id)
        assert len(roles) == 0
        
        # Проверяем, что права не действуют
        permissions = temp_db_with_roles.get_user_permissions(user_id)
        assert len(permissions) == 0


# Фикстуры для тестов

@pytest.fixture
def temp_db():
    """Временная база данных для тестов."""
    fd, path = tempfile.mkstemp()
    os.close(fd)
    
    try:
        db = Database(path)
        db.connect()
        yield db
    finally:
        db.close()
        os.unlink(path)


@pytest.fixture
def temp_db_with_roles(temp_db):
    """Временная база данных с применённой миграцией ролей."""
    # Применяем миграцию
    from migrations import migration_003_roles_permissions
    up = migration_003_roles_permissions.up
    up(temp_db.conn)
    
    return temp_db


if __name__ == '__main__':
    pytest.main([__file__, '-v']) 
"""
Миграция 003: Создание системы ролей и прав доступа.
"""

from typing import List
import sqlite3
import logging

logger = logging.getLogger(__name__)


def up(connection: sqlite3.Connection) -> None:
    """
    Применение миграции - создание системы ролей и прав доступа.
    
    Args:
        connection: Подключение к БД
    """
    logger.info("Применение миграции 003: Создание системы ролей и прав доступа")
    
    cursor = connection.cursor()
    
    # Создаем таблицы для системы ролей и прав
    connection.executescript('''
        -- Роли в системе
        CREATE TABLE IF NOT EXISTS roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            display_name TEXT NOT NULL,
            description TEXT,
            is_system INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        
        -- Права доступа
        CREATE TABLE IF NOT EXISTS permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            display_name TEXT NOT NULL,
            description TEXT,
            category TEXT NOT NULL,
            is_system INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        
        -- Связь между ролями и правами (many-to-many)
        CREATE TABLE IF NOT EXISTS role_permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role_id INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
            permission_id INTEGER NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(role_id, permission_id)
        );
        
        -- Связь между пользователями и ролями (many-to-many)
        CREATE TABLE IF NOT EXISTS user_roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES Users(id) ON DELETE CASCADE,
            role_id INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
            assigned_by INTEGER REFERENCES Users(id),
            assigned_at TEXT NOT NULL DEFAULT (datetime('now')),
            expires_at TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            UNIQUE(user_id, role_id)
        );
        
        -- Индексы для быстрого поиска
        CREATE INDEX IF NOT EXISTS idx_roles_name ON roles(name);
        CREATE INDEX IF NOT EXISTS idx_permissions_name ON permissions(name);
        CREATE INDEX IF NOT EXISTS idx_permissions_category ON permissions(category);
        CREATE INDEX IF NOT EXISTS idx_role_permissions_role ON role_permissions(role_id);
        CREATE INDEX IF NOT EXISTS idx_role_permissions_permission ON role_permissions(permission_id);
        CREATE INDEX IF NOT EXISTS idx_user_roles_user ON user_roles(user_id);
        CREATE INDEX IF NOT EXISTS idx_user_roles_role ON user_roles(role_id);
        CREATE INDEX IF NOT EXISTS idx_user_roles_active ON user_roles(is_active);
    ''')
    
    # Создаем базовые роли
    roles_data = [
        ('admin', 'Администратор', 'Полный доступ к системе', 1),
        ('otk_master', 'Мастер ОТК', 'Контроль качества материалов', 1),
        ('lab_technician', 'Лаборант', 'Проведение лабораторных испытаний', 1),
        ('operator', 'Оператор', 'Работа с материалами', 1),
        ('viewer', 'Наблюдатель', 'Просмотр данных', 1),
    ]
    
    for name, display_name, description, is_system in roles_data:
        cursor.execute('''
            INSERT OR IGNORE INTO roles (name, display_name, description, is_system)
            VALUES (?, ?, ?, ?)
        ''', (name, display_name, description, is_system))
    
    # Создаем базовые права доступа
    permissions_data = [
        # Материалы
        ('materials.view', 'Просмотр материалов', 'Просмотр списка материалов', 'materials', 1),
        ('materials.create', 'Создание материалов', 'Добавление новых материалов', 'materials', 1),
        ('materials.edit', 'Редактирование материалов', 'Изменение данных материалов', 'materials', 1),
        ('materials.delete', 'Удаление материалов', 'Удаление материалов', 'materials', 1),
        ('materials.import', 'Импорт материалов', 'Импорт данных о материалах', 'materials', 1),
        ('materials.export', 'Экспорт материалов', 'Экспорт данных о материалах', 'materials', 1),
        
        # Лаборатория
        ('lab.view', 'Просмотр лабораторных данных', 'Просмотр заявок и результатов', 'lab', 1),
        ('lab.create', 'Создание лабораторных заявок', 'Создание новых заявок', 'lab', 1),
        ('lab.edit', 'Редактирование лабораторных данных', 'Изменение заявок и результатов', 'lab', 1),
        ('lab.approve', 'Утверждение результатов', 'Утверждение лабораторных результатов', 'lab', 1),
        ('lab.archive', 'Архивация заявок', 'Архивация лабораторных заявок', 'lab', 1),
        
        # Контроль качества
        ('quality.view', 'Просмотр данных ОТК', 'Просмотр данных контроля качества', 'quality', 1),
        ('quality.create', 'Создание записей ОТК', 'Создание записей контроля качества', 'quality', 1),
        ('quality.edit', 'Редактирование данных ОТК', 'Изменение данных контроля качества', 'quality', 1),
        ('quality.approve', 'Утверждение ОТК', 'Утверждение результатов контроля качества', 'quality', 1),
        
        # Документы
        ('documents.view', 'Просмотр документов', 'Просмотр прикрепленных документов', 'documents', 1),
        ('documents.upload', 'Загрузка документов', 'Загрузка новых документов', 'documents', 1),
        ('documents.delete', 'Удаление документов', 'Удаление документов', 'documents', 1),
        
        # Отчеты
        ('reports.view', 'Просмотр отчетов', 'Просмотр существующих отчетов', 'reports', 1),
        ('reports.create', 'Создание отчетов', 'Создание новых отчетов', 'reports', 1),
        ('reports.export', 'Экспорт отчетов', 'Экспорт отчетов в файлы', 'reports', 1),
        
        # Администрирование
        ('admin.users', 'Управление пользователями', 'Создание и управление пользователями', 'admin', 1),
        ('admin.roles', 'Управление ролями', 'Создание и управление ролями', 'admin', 1),
        ('admin.permissions', 'Управление правами', 'Управление правами доступа', 'admin', 1),
        ('admin.settings', 'Настройки системы', 'Изменение настроек системы', 'admin', 1),
        ('admin.backup', 'Резервное копирование', 'Создание резервных копий', 'admin', 1),
        ('admin.logs', 'Просмотр логов', 'Просмотр логов системы', 'admin', 1),
        
        # Поставщики
        ('suppliers.view', 'Просмотр поставщиков', 'Просмотр списка поставщиков', 'suppliers', 1),
        ('suppliers.create', 'Создание поставщиков', 'Добавление новых поставщиков', 'suppliers', 1),
        ('suppliers.edit', 'Редактирование поставщиков', 'Изменение данных поставщиков', 'suppliers', 1),
        ('suppliers.delete', 'Удаление поставщиков', 'Удаление поставщиков', 'suppliers', 1),
    ]
    
    for name, display_name, description, category, is_system in permissions_data:
        cursor.execute('''
            INSERT OR IGNORE INTO permissions (name, display_name, description, category, is_system)
            VALUES (?, ?, ?, ?, ?)
        ''', (name, display_name, description, category, is_system))
    
    # Назначаем права ролям
    role_permissions_data = [
        # Администратор - все права
        ('admin', [
            'materials.view', 'materials.create', 'materials.edit', 'materials.delete', 
            'materials.import', 'materials.export',
            'lab.view', 'lab.create', 'lab.edit', 'lab.approve', 'lab.archive',
            'quality.view', 'quality.create', 'quality.edit', 'quality.approve',
            'documents.view', 'documents.upload', 'documents.delete',
            'reports.view', 'reports.create', 'reports.export',
            'admin.users', 'admin.roles', 'admin.permissions', 'admin.settings', 
            'admin.backup', 'admin.logs',
            'suppliers.view', 'suppliers.create', 'suppliers.edit', 'suppliers.delete'
        ]),
        
        # Мастер ОТК - контроль качества и материалы
        ('otk_master', [
            'materials.view', 'materials.create', 'materials.edit',
            'materials.export',
            'lab.view', 'lab.create',
            'quality.view', 'quality.create', 'quality.edit', 'quality.approve',
            'documents.view', 'documents.upload',
            'reports.view', 'reports.create', 'reports.export',
            'suppliers.view'
        ]),
        
        # Лаборант - лабораторные испытания
        ('lab_technician', [
            'materials.view',
            'lab.view', 'lab.create', 'lab.edit', 'lab.approve',
            'quality.view',
            'documents.view', 'documents.upload',
            'reports.view', 'reports.create',
            'suppliers.view'
        ]),
        
        # Оператор - работа с материалами
        ('operator', [
            'materials.view', 'materials.create', 'materials.edit',
            'lab.view', 'lab.create',
            'quality.view',
            'documents.view', 'documents.upload',
            'reports.view',
            'suppliers.view'
        ]),
        
        # Наблюдатель - только просмотр
        ('viewer', [
            'materials.view',
            'lab.view',
            'quality.view',
            'documents.view',
            'reports.view',
            'suppliers.view'
        ]),
    ]
    
    for role_name, permission_names in role_permissions_data:
        # Получаем ID роли
        cursor.execute('SELECT id FROM roles WHERE name = ?', (role_name,))
        role_row = cursor.fetchone()
        if not role_row:
            continue
        role_id = role_row[0]
        
        # Назначаем права
        for permission_name in permission_names:
            cursor.execute('SELECT id FROM permissions WHERE name = ?', (permission_name,))
            permission_row = cursor.fetchone()
            if not permission_row:
                continue
            permission_id = permission_row[0]
            
            cursor.execute('''
                INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
                VALUES (?, ?)
            ''', (role_id, permission_id))
    
    # Назначаем роль администратора существующим пользователям с ролью 'Администратор'
    cursor.execute('''
        INSERT OR IGNORE INTO user_roles (user_id, role_id, assigned_by)
        SELECT u.id, r.id, u.id
        FROM Users u, roles r
        WHERE u.role = 'Администратор' AND r.name = 'admin'
    ''')
    
    # Назначаем роль наблюдателя остальным пользователям
    cursor.execute('''
        INSERT OR IGNORE INTO user_roles (user_id, role_id, assigned_by)
        SELECT u.id, r.id, u.id
        FROM Users u, roles r
        WHERE u.role != 'Администратор' AND r.name = 'viewer'
        AND u.id NOT IN (SELECT user_id FROM user_roles)
    ''')
    
    connection.commit()
    logger.info("Миграция 003 успешно применена")


def down(connection: sqlite3.Connection) -> None:
    """
    Откат миграции - удаление системы ролей и прав доступа.
    
    Args:
        connection: Подключение к БД
    """
    logger.info("Откат миграции 003: Удаление системы ролей и прав доступа")
    
    # Удаляем таблицы в обратном порядке
    connection.executescript('''
        DROP TABLE IF EXISTS user_roles;
        DROP TABLE IF EXISTS role_permissions;
        DROP TABLE IF EXISTS permissions;
        DROP TABLE IF EXISTS roles;
    ''')
    
    connection.commit()
    logger.info("Миграция 003 успешно откачена")


def get_version() -> str:
    """
    Возвращает версию миграции.
    
    Returns:
        Версия миграции
    """
    return "003"


def get_description() -> str:
    """
    Возвращает описание миграции.
    
    Returns:
        Описание миграции
    """
    return "Создание системы ролей и прав доступа"


def get_dependencies() -> List[str]:
    """
    Возвращает список зависимостей миграции.
    
    Returns:
        Список версий миграций, которые должны быть применены перед этой
    """
    return ["001", "002"] 
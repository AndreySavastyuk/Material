#!/usr/bin/env python3
"""
Скрипт для инициализации базы данных и применения миграций.
"""

import os
import sys
import sqlite3
import logging
from pathlib import Path

# Добавляем корневую папку в sys.path
sys.path.insert(0, str(Path(__file__).parent))

from db.database import Database
from utils.logger import get_logger, setup_development_logging


def setup_database():
    """Инициализация базы данных и применение миграций."""
    
    # Настраиваем логирование
    setup_development_logging()
    logger = get_logger('setup_database')
    
    logger.info("🚀 Начинаем инициализацию базы данных")
    
    try:
        # Создаем объект базы данных
        db = Database()
        db.connect()
        
        logger.info("✅ Подключение к базе данных установлено")
        
        # Применяем миграции по порядку
        migrations = [
            ('001', 'migrations.001_initial_schema'),
            ('002', 'migrations.bcrypt_passwords_migration'),
            ('003', 'migrations.migration_003_roles_permissions'),
            ('004', 'migrations.migration_004_user_sessions'),
        ]
        
        for migration_id, migration_module in migrations:
            try:
                logger.info(f"🔄 Применяем миграцию {migration_id}...")
                
                # Импортируем модуль миграции
                module = __import__(migration_module, fromlist=['up'])
                up_func = getattr(module, 'up')
                
                # Применяем миграцию
                up_func(db.conn)
                
                logger.info(f"✅ Миграция {migration_id} успешно применена")
                
            except Exception as e:
                logger.error(f"❌ Ошибка при применении миграции {migration_id}: {e}")
                if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                    logger.warning(f"⚠️  Миграция {migration_id} уже была применена")
                else:
                    raise
        
        # Создаем администратора
        logger.info("🔄 Создаем администратора...")
        
        # Проверяем, есть ли уже пользователь admin
        cursor = db.conn.cursor()
        cursor.execute("SELECT id FROM Users WHERE login = 'admin'")
        if cursor.fetchone():
            logger.info("⚠️  Пользователь admin уже существует")
        else:
            db.create_admin_user()
            logger.info("✅ Администратор создан")
        
        # Проверяем, что пользователь admin может авторизоваться
        logger.info("🔄 Проверяем авторизацию администратора...")
        user_data = db.verify_user('admin', 'admin')
        if user_data:
            logger.info("✅ Администратор может авторизоваться")
        else:
            logger.error("❌ Ошибка авторизации администратора")
            
        # Проверяем структуру базы данных
        logger.info("🔄 Проверяем структуру базы данных...")
        check_database_structure(db)
        
        db.close()
        
        logger.info("🎉 Инициализация базы данных успешно завершена!")
        print("\n" + "="*60)
        print("🎉 БАЗА ДАННЫХ ГОТОВА К ИСПОЛЬЗОВАНИЮ!")
        print("="*60)
        print("📊 Создан пользователь: admin")
        print("🔐 Пароль: admin")
        print("👤 Роль: Администратор")
        print("="*60)
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка при инициализации: {e}")
        raise


def check_database_structure(db):
    """Проверка структуры базы данных."""
    
    logger = get_logger('setup_database')
    
    required_tables = [
        'Users', 'Suppliers', 'Grades', 'RollingTypes', 'Materials',
        'roles', 'permissions', 'role_permissions', 'user_roles',
        'user_sessions', 'user_login_logs', 'session_settings'
    ]
    
    cursor = db.conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    existing_tables = [row[0] for row in cursor.fetchall()]
    
    missing_tables = []
    for table in required_tables:
        if table not in existing_tables:
            missing_tables.append(table)
    
    if missing_tables:
        logger.error(f"❌ Отсутствуют таблицы: {', '.join(missing_tables)}")
        raise Exception(f"Отсутствуют таблицы: {', '.join(missing_tables)}")
    
    logger.info(f"✅ Все {len(required_tables)} таблиц присутствуют")
    
    # Проверяем количество базовых ролей
    cursor.execute("SELECT COUNT(*) FROM roles")
    roles_count = cursor.fetchone()[0]
    logger.info(f"📊 Ролей в системе: {roles_count}")
    
    # Проверяем количество базовых прав
    cursor.execute("SELECT COUNT(*) FROM permissions")
    permissions_count = cursor.fetchone()[0]
    logger.info(f"📊 Прав доступа в системе: {permissions_count}")
    
    # Проверяем количество пользователей
    cursor.execute("SELECT COUNT(*) FROM Users")
    users_count = cursor.fetchone()[0]
    logger.info(f"📊 Пользователей в системе: {users_count}")
    
    # Проверяем настройки сессий
    cursor.execute("SELECT COUNT(*) FROM session_settings")
    settings_count = cursor.fetchone()[0]
    logger.info(f"📊 Настроек сессий: {settings_count}")


if __name__ == '__main__':
    setup_database() 
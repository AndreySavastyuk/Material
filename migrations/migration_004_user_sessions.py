"""
Миграция 004: Система управления сессиями пользователей

Добавляет:
- Таблицу user_sessions для хранения сессий пользователей
- Поддержку токенов сессий с автоматическим истечением
- Функциональность "Запомнить меня"
- Отслеживание IP-адресов и браузеров
- Контроль активности и безопасности сессий
"""

import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def up(connection):
    """Применение миграции - создание системы управления сессиями."""
    
    cursor = connection.cursor()
    
    try:
        logger.info("Начало миграции 004: Система управления сессиями")
        
        # Создаем таблицу user_sessions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                session_token TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                last_activity TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                remember_me BOOLEAN NOT NULL DEFAULT 0,
                ip_address TEXT,
                user_agent TEXT,
                is_active BOOLEAN NOT NULL DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        """)
        
        # Создаем индексы для оптимизации
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON user_sessions(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_token ON user_sessions(session_token)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_expires ON user_sessions(expires_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_active ON user_sessions(is_active)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_last_activity ON user_sessions(last_activity)")
        
        # Создаем таблицу для логирования входов/выходов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_login_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                login TEXT NOT NULL,
                action TEXT NOT NULL,  -- 'login', 'logout', 'session_expired', 'invalid_token'
                ip_address TEXT,
                user_agent TEXT,
                session_token TEXT,
                success BOOLEAN NOT NULL,
                reason TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
            )
        """)
        
        # Индексы для логов
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_login_logs_user_id ON user_login_logs(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_login_logs_action ON user_login_logs(action)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_login_logs_created_at ON user_login_logs(created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_login_logs_success ON user_login_logs(success)")
        
        # Создаем таблицу настроек сессий
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS session_settings (
                id INTEGER PRIMARY KEY,
                setting_name TEXT NOT NULL UNIQUE,
                setting_value TEXT NOT NULL,
                description TEXT,
                updated_at TEXT NOT NULL
            )
        """)
        
        # Добавляем базовые настройки сессий
        session_settings = [
            ('default_session_timeout', '3600', 'Таймаут сессии по умолчанию (секунды)', datetime.now().isoformat()),
            ('remember_me_timeout', '2592000', 'Таймаут для "Запомнить меня" (секунды, 30 дней)', datetime.now().isoformat()),
            ('max_sessions_per_user', '5', 'Максимальное количество активных сессий на пользователя', datetime.now().isoformat()),
            ('session_token_length', '64', 'Длина токена сессии', datetime.now().isoformat()),
            ('auto_cleanup_expired', 'true', 'Автоматическая очистка истекших сессий', datetime.now().isoformat()),
            ('cleanup_interval_hours', '24', 'Интервал очистки истекших сессий (часы)', datetime.now().isoformat()),
            ('session_rotation_enabled', 'true', 'Включить ротацию токенов сессий', datetime.now().isoformat()),
            ('rotation_interval_hours', '24', 'Интервал ротации токенов (часы)', datetime.now().isoformat()),
            ('track_ip_changes', 'true', 'Отслеживать изменения IP-адреса', datetime.now().isoformat()),
            ('invalidate_on_ip_change', 'false', 'Инвалидировать сессию при смене IP', datetime.now().isoformat()),
        ]
        
        for setting_name, setting_value, description, updated_at in session_settings:
            cursor.execute("""
                INSERT OR IGNORE INTO session_settings 
                (setting_name, setting_value, description, updated_at)
                VALUES (?, ?, ?, ?)
            """, (setting_name, setting_value, description, updated_at))
        
        # Создаем триггер для автоматического обновления last_activity
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS update_session_activity
            AFTER UPDATE ON user_sessions
            FOR EACH ROW
            BEGIN
                UPDATE user_sessions 
                SET last_activity = datetime('now') 
                WHERE id = NEW.id AND OLD.last_activity != NEW.last_activity;
            END
        """)
        
        # Проверяем, что таблицы созданы корректно
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_sessions'")
        if not cursor.fetchone():
            raise Exception("Таблица user_sessions не была создана")
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_login_logs'")
        if not cursor.fetchone():
            raise Exception("Таблица user_login_logs не была создана")
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='session_settings'")
        if not cursor.fetchone():
            raise Exception("Таблица session_settings не была создана")
        
        # Подсчитываем количество созданных настроек
        cursor.execute("SELECT COUNT(*) FROM session_settings")
        settings_count = cursor.fetchone()[0]
        
        logger.info(f"✅ Создана таблица user_sessions с индексами")
        logger.info(f"✅ Создана таблица user_login_logs с индексами")
        logger.info(f"✅ Создана таблица session_settings с {settings_count} настройками")
        logger.info(f"✅ Создан триггер update_session_activity")
        
        connection.commit()
        logger.info("✅ Миграция 004 успешно применена")
        
    except Exception as e:
        connection.rollback()
        logger.error(f"❌ Ошибка при применении миграции 004: {e}")
        raise


def down(connection):
    """Откат миграции - удаление системы управления сессиями."""
    
    cursor = connection.cursor()
    
    try:
        logger.info("Начало отката миграции 004: Система управления сессиями")
        
        # Удаляем триггер
        cursor.execute("DROP TRIGGER IF EXISTS update_session_activity")
        
        # Удаляем таблицы в обратном порядке
        cursor.execute("DROP TABLE IF EXISTS session_settings")
        cursor.execute("DROP TABLE IF EXISTS user_login_logs")
        cursor.execute("DROP TABLE IF EXISTS user_sessions")
        
        connection.commit()
        logger.info("✅ Откат миграции 004 успешно выполнен")
        
    except Exception as e:
        connection.rollback()
        logger.error(f"❌ Ошибка при откате миграции 004: {e}")
        raise


def get_migration_info():
    """Информация о миграции."""
    return {
        'version': '004',
        'name': 'user_sessions',
        'description': 'Система управления сессиями пользователей',
        'tables_created': ['user_sessions', 'user_login_logs', 'session_settings'],
        'dependencies': ['003_roles_permissions'],
        'reversible': True
    }


if __name__ == '__main__':
    # Тестирование миграции
    import sqlite3
    import tempfile
    import os
    
    # Создаем временную базу данных
    fd, db_path = tempfile.mkstemp()
    os.close(fd)
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        
        # Создаем базовую структуру пользователей (упрощенно)
        conn.execute("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                login TEXT UNIQUE,
                password TEXT,
                role TEXT,
                name TEXT
            )
        """)
        
        # Применяем миграцию
        up(conn)
        
        # Проверяем результат
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        expected_tables = ['users', 'user_sessions', 'user_login_logs', 'session_settings']
        for table in expected_tables:
            assert table in tables, f"Таблица {table} не найдена"
        
        # Проверяем настройки
        cursor.execute("SELECT COUNT(*) FROM session_settings")
        settings_count = cursor.fetchone()[0]
        assert settings_count > 0, "Настройки сессий не созданы"
        
        print("✅ Миграция 004 протестирована успешно")
        
        # Тестируем откат
        down(conn)
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        assert 'user_sessions' not in tables, "Таблица user_sessions не удалена"
        assert 'user_login_logs' not in tables, "Таблица user_login_logs не удалена"
        assert 'session_settings' not in tables, "Таблица session_settings не удалена"
        
        print("✅ Откат миграции 004 протестирован успешно")
        
        conn.close()
        
    finally:
        os.unlink(db_path) 
"""
Миграция 002: Обновление паролей пользователей с SHA256 на bcrypt.
"""

from typing import List
import sqlite3
import logging
import hashlib
import bcrypt

logger = logging.getLogger(__name__)


def up(connection: sqlite3.Connection) -> None:
    """
    Применение миграции - обновление паролей на bcrypt.
    
    Args:
        connection: Подключение к БД
    """
    logger.info("Применение миграции 002: Обновление паролей на bcrypt")
    
    cursor = connection.cursor()
    
    # Добавляем новые поля для работы с bcrypt
    try:
        cursor.execute("ALTER TABLE Users ADD COLUMN password_bcrypt TEXT")
        logger.info("Добавлено поле password_bcrypt")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            logger.info("Поле password_bcrypt уже существует")
        else:
            raise
    
    try:
        cursor.execute("ALTER TABLE Users ADD COLUMN password_type TEXT DEFAULT 'sha256'")
        logger.info("Добавлено поле password_type")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            logger.info("Поле password_type уже существует")
        else:
            raise
    
    # Обновляем тип пароля для существующих пользователей
    cursor.execute("UPDATE Users SET password_type = 'sha256' WHERE password_type IS NULL")
    
    # Получаем всех пользователей для обновления паролей
    cursor.execute("SELECT id, login, password_hash, password_type FROM Users")
    users = cursor.fetchall()
    
    updated_count = 0
    for user in users:
        user_id, login, password_hash, password_type = user
        
        # Если пароль уже в bcrypt формате - пропускаем
        if password_type == 'bcrypt':
            continue
            
        # Для тестового администратора обновляем пароль
        if login == 'admin' and password_type == 'sha256':
            # Пароль по умолчанию для админа - 'admin'
            # Проверяем, что это действительно дефолтный пароль
            expected_sha256 = hashlib.sha256('admin'.encode('utf-8')).hexdigest()
            if password_hash == expected_sha256:
                # Генерируем bcrypt хеш для пароля 'admin'
                bcrypt_hash = bcrypt.hashpw('admin'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                
                cursor.execute("""
                    UPDATE Users 
                    SET password_bcrypt = ?, password_type = 'bcrypt'
                    WHERE id = ?
                """, (bcrypt_hash, user_id))
                
                updated_count += 1
                logger.info(f"Обновлен пароль для пользователя {login}")
            else:
                logger.warning(f"Пароль пользователя {login} не является дефолтным, требуется ручное обновление")
        else:
            logger.info(f"Пользователь {login} не требует автоматического обновления пароля")
    
    connection.commit()
    logger.info(f"Миграция 002 успешно применена. Обновлено паролей: {updated_count}")


def down(connection: sqlite3.Connection) -> None:
    """
    Откат миграции - удаление полей bcrypt.
    
    Args:
        connection: Подключение к БД
    """
    logger.info("Откат миграции 002: Удаление полей bcrypt")
    
    cursor = connection.cursor()
    
    # Сбрасываем тип пароля для всех пользователей
    cursor.execute("UPDATE Users SET password_type = 'sha256'")
    
    # Очищаем bcrypt пароли
    cursor.execute("UPDATE Users SET password_bcrypt = NULL")
    
    # Примечание: SQLite не поддерживает DROP COLUMN, поэтому оставляем поля
    # но очищаем их содержимое
    
    connection.commit()
    logger.info("Миграция 002 успешно откачена")


def get_version() -> str:
    """
    Возвращает версию миграции.
    
    Returns:
        Версия миграции
    """
    return "002"


def get_description() -> str:
    """
    Возвращает описание миграции.
    
    Returns:
        Описание миграции
    """
    return "Обновление паролей пользователей с SHA256 на bcrypt"


def get_dependencies() -> List[str]:
    """
    Возвращает список зависимостей миграции.
    
    Returns:
        Список версий миграций, которые должны быть применены перед этой
    """
    return ["001"] 
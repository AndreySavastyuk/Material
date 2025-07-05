"""
Тесты для системы авторизации с обратной совместимостью bcrypt.
"""

import pytest
import sqlite3
import hashlib
import bcrypt
import tempfile
import os
from unittest.mock import patch, MagicMock

from db.database import Database


@pytest.fixture
def temp_db():
    """Создает временную базу данных для тестов."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    # Создаем базу данных
    db = Database(db_path)
    db.connect()
    
    yield db
    
    # Очищаем
    db.close()
    os.unlink(db_path)


@pytest.fixture
def db_with_sha256_user(temp_db):
    """Создает базу данных со старым SHA256 пользователем."""
    # Создаем пользователя со старым SHA256 паролем
    cursor = temp_db.conn.cursor()
    sha256_hash = hashlib.sha256('testpass'.encode('utf-8')).hexdigest()
    cursor.execute(
        """INSERT INTO Users(login, password_hash, password_type, role, name, salt) 
           VALUES(?,?,?,?,?,?)""",
        ('testuser', sha256_hash, 'sha256', 'Пользователь', 'Тестовый пользователь', '')
    )
    temp_db.conn.commit()
    
    return temp_db


@pytest.fixture
def db_with_bcrypt_user(temp_db):
    """Создает базу данных с bcrypt пользователем."""
    # Создаем пользователя с bcrypt паролем
    cursor = temp_db.conn.cursor()
    bcrypt_hash = bcrypt.hashpw('testpass'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    cursor.execute(
        """INSERT INTO Users(login, password_hash, password_bcrypt, password_type, role, name, salt) 
           VALUES(?,?,?,?,?,?,?)""",
        ('testuser', '', bcrypt_hash, 'bcrypt', 'Пользователь', 'Тестовый пользователь', '')
    )
    temp_db.conn.commit()
    
    return temp_db


class TestAuthCompatibility:
    """Тесты обратной совместимости авторизации."""
    
    def test_verify_user_sha256_password(self, db_with_sha256_user):
        """Тест проверки пароля SHA256."""
        db = db_with_sha256_user
        
        # Успешная авторизация
        user_data = db.verify_user('testuser', 'testpass')
        assert user_data is not None
        assert user_data['login'] == 'testuser'
        assert user_data['role'] == 'Пользователь'
        assert user_data['name'] == 'Тестовый пользователь'
        
        # Неверный пароль
        user_data = db.verify_user('testuser', 'wrongpass')
        assert user_data is None
        
        # Несуществующий пользователь
        user_data = db.verify_user('nonexistent', 'testpass')
        assert user_data is None
    
    def test_verify_user_bcrypt_password(self, db_with_bcrypt_user):
        """Тест проверки пароля bcrypt."""
        db = db_with_bcrypt_user
        
        # Успешная авторизация
        user_data = db.verify_user('testuser', 'testpass')
        assert user_data is not None
        assert user_data['login'] == 'testuser'
        assert user_data['role'] == 'Пользователь'
        assert user_data['name'] == 'Тестовый пользователь'
        
        # Неверный пароль
        user_data = db.verify_user('testuser', 'wrongpass')
        assert user_data is None
    
    def test_automatic_password_upgrade(self, db_with_sha256_user):
        """Тест автоматического обновления пароля с SHA256 на bcrypt."""
        db = db_with_sha256_user
        
        # Проверяем, что пароль в формате SHA256
        cursor = db.conn.cursor()
        cursor.execute("SELECT password_type, password_bcrypt FROM Users WHERE login=?", ('testuser',))
        row = cursor.fetchone()
        assert row['password_type'] == 'sha256'
        assert row['password_bcrypt'] is None
        
        # Авторизуемся со старым паролем
        user_data = db.verify_user('testuser', 'testpass')
        assert user_data is not None
        
        # Проверяем, что пароль был обновлен на bcrypt
        cursor.execute("SELECT password_type, password_bcrypt FROM Users WHERE login=?", ('testuser',))
        row = cursor.fetchone()
        assert row['password_type'] == 'bcrypt'
        assert row['password_bcrypt'] is not None
        
        # Проверяем, что новый bcrypt пароль работает
        user_data = db.verify_user('testuser', 'testpass')
        assert user_data is not None
    
    def test_change_password_from_sha256(self, db_with_sha256_user):
        """Тест смены пароля с SHA256."""
        db = db_with_sha256_user
        
        # Получаем ID пользователя
        cursor = db.conn.cursor()
        cursor.execute("SELECT id FROM Users WHERE login=?", ('testuser',))
        user_id = cursor.fetchone()['id']
        
        # Меняем пароль
        result = db.change_password(user_id, 'testpass', 'newpass')
        assert result is True
        
        # Проверяем, что старый пароль больше не работает
        user_data = db.verify_user('testuser', 'testpass')
        assert user_data is None
        
        # Проверяем, что новый пароль работает
        user_data = db.verify_user('testuser', 'newpass')
        assert user_data is not None
        
        # Проверяем, что пароль теперь в формате bcrypt
        cursor.execute("SELECT password_type FROM Users WHERE login=?", ('testuser',))
        row = cursor.fetchone()
        assert row['password_type'] == 'bcrypt'
    
    def test_change_password_from_bcrypt(self, db_with_bcrypt_user):
        """Тест смены пароля с bcrypt."""
        db = db_with_bcrypt_user
        
        # Получаем ID пользователя
        cursor = db.conn.cursor()
        cursor.execute("SELECT id FROM Users WHERE login=?", ('testuser',))
        user_id = cursor.fetchone()['id']
        
        # Меняем пароль
        result = db.change_password(user_id, 'testpass', 'newpass')
        assert result is True
        
        # Проверяем, что старый пароль больше не работает
        user_data = db.verify_user('testuser', 'testpass')
        assert user_data is None
        
        # Проверяем, что новый пароль работает
        user_data = db.verify_user('testuser', 'newpass')
        assert user_data is not None
    
    def test_change_password_wrong_old_password(self, db_with_bcrypt_user):
        """Тест смены пароля с неверным старым паролем."""
        db = db_with_bcrypt_user
        
        # Получаем ID пользователя
        cursor = db.conn.cursor()
        cursor.execute("SELECT id FROM Users WHERE login=?", ('testuser',))
        user_id = cursor.fetchone()['id']
        
        # Пытаемся сменить пароль с неверным старым паролем
        result = db.change_password(user_id, 'wrongpass', 'newpass')
        assert result is False
        
        # Проверяем, что пароль не изменился
        user_data = db.verify_user('testuser', 'testpass')
        assert user_data is not None
    
    def test_change_password_nonexistent_user(self, temp_db):
        """Тест смены пароля для несуществующего пользователя."""
        db = temp_db
        
        # Пытаемся сменить пароль для несуществующего пользователя
        result = db.change_password(999, 'oldpass', 'newpass')
        assert result is False
    
    def test_create_user_with_bcrypt(self, temp_db):
        """Тест создания пользователя с bcrypt паролем."""
        db = temp_db
        
        # Создаем пользователя
        user_id = db.create_user('newuser', 'newpass', 'Пользователь', 'Новый пользователь')
        assert user_id is not None
        
        # Проверяем, что пользователь создан с bcrypt паролем
        cursor = db.conn.cursor()
        cursor.execute("SELECT password_type, password_bcrypt FROM Users WHERE id=?", (user_id,))
        row = cursor.fetchone()
        assert row['password_type'] == 'bcrypt'
        assert row['password_bcrypt'] is not None
        
        # Проверяем авторизацию
        user_data = db.verify_user('newuser', 'newpass')
        assert user_data is not None
        assert user_data['login'] == 'newuser'
        assert user_data['role'] == 'Пользователь'
        assert user_data['name'] == 'Новый пользователь'
    
    def test_create_user_duplicate_login(self, db_with_bcrypt_user):
        """Тест создания пользователя с уже существующим логином."""
        db = db_with_bcrypt_user
        
        # Пытаемся создать пользователя с уже существующим логином
        user_id = db.create_user('testuser', 'newpass', 'Пользователь')
        assert user_id is None
    
    def test_get_user_by_login(self, db_with_bcrypt_user):
        """Тест получения данных пользователя по логину."""
        db = db_with_bcrypt_user
        
        # Получаем существующего пользователя
        user_data = db.get_user_by_login('testuser')
        assert user_data is not None
        assert user_data['login'] == 'testuser'
        assert user_data['role'] == 'Пользователь'
        assert user_data['name'] == 'Тестовый пользователь'
        
        # Получаем несуществующего пользователя
        user_data = db.get_user_by_login('nonexistent')
        assert user_data is None
    
    def test_admin_user_creation(self, temp_db):
        """Тест создания администратора при инициализации."""
        db = temp_db
        
        # Проверяем, что администратор создан
        user_data = db.get_user_by_login('admin')
        assert user_data is not None
        assert user_data['login'] == 'admin'
        assert user_data['role'] == 'Администратор'
        assert user_data['name'] == 'Админ'
        
        # Проверяем авторизацию администратора
        user_data = db.verify_user('admin', 'admin')
        assert user_data is not None
        
        # Проверяем, что пароль администратора в формате bcrypt
        cursor = db.conn.cursor()
        cursor.execute("SELECT password_type FROM Users WHERE login=?", ('admin',))
        row = cursor.fetchone()
        assert row['password_type'] == 'bcrypt'
    
    def test_mixed_password_types(self, temp_db):
        """Тест работы с разными типами паролей в одной базе."""
        db = temp_db
        
        # Создаем пользователя с SHA256 паролем
        cursor = db.conn.cursor()
        sha256_hash = hashlib.sha256('sha256pass'.encode('utf-8')).hexdigest()
        cursor.execute(
            """INSERT INTO Users(login, password_hash, password_type, role, name, salt) 
               VALUES(?,?,?,?,?,?)""",
            ('sha256user', sha256_hash, 'sha256', 'Пользователь', 'SHA256 пользователь', '')
        )
        
        # Создаем пользователя с bcrypt паролем
        bcrypt_hash = bcrypt.hashpw('bcryptpass'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        cursor.execute(
            """INSERT INTO Users(login, password_hash, password_bcrypt, password_type, role, name, salt) 
               VALUES(?,?,?,?,?,?,?)""",
            ('bcryptuser', '', bcrypt_hash, 'bcrypt', 'Пользователь', 'Bcrypt пользователь', '')
        )
        db.conn.commit()
        
        # Проверяем авторизацию SHA256 пользователя
        user_data = db.verify_user('sha256user', 'sha256pass')
        assert user_data is not None
        assert user_data['login'] == 'sha256user'
        
        # Проверяем авторизацию bcrypt пользователя
        user_data = db.verify_user('bcryptuser', 'bcryptpass')
        assert user_data is not None
        assert user_data['login'] == 'bcryptuser'
        
        # Проверяем авторизацию администратора
        user_data = db.verify_user('admin', 'admin')
        assert user_data is not None
        assert user_data['login'] == 'admin'
    
    @patch('db.database.logger')
    def test_logging_on_authentication(self, mock_logger, db_with_bcrypt_user):
        """Тест логирования при авторизации."""
        db = db_with_bcrypt_user
        
        # Успешная авторизация
        db.verify_user('testuser', 'testpass')
        mock_logger.info.assert_called_with('Успешная авторизация пользователя testuser (bcrypt)')
        
        # Неуспешная авторизация
        db.verify_user('testuser', 'wrongpass')
        mock_logger.warning.assert_called_with('Неверный пароль для пользователя testuser')
    
    def test_password_verification_internal_method(self, db_with_sha256_user):
        """Тест внутреннего метода проверки пароля."""
        db = db_with_sha256_user
        
        # Получаем данные пользователя
        cursor = db.conn.cursor()
        cursor.execute("SELECT * FROM Users WHERE login=?", ('testuser',))
        user_row = cursor.fetchone()
        
        # Проверяем правильный пароль
        assert db._verify_password(user_row, 'testpass') is True
        
        # Проверяем неправильный пароль
        assert db._verify_password(user_row, 'wrongpass') is False
    
    def test_password_upgrade_internal_method(self, db_with_sha256_user):
        """Тест внутреннего метода обновления пароля."""
        db = db_with_sha256_user
        
        # Получаем ID пользователя
        cursor = db.conn.cursor()
        cursor.execute("SELECT id FROM Users WHERE login=?", ('testuser',))
        user_id = cursor.fetchone()['id']
        
        # Обновляем пароль
        db._upgrade_password_to_bcrypt(user_id, 'testpass')
        
        # Проверяем, что пароль обновлен
        cursor.execute("SELECT password_type, password_bcrypt FROM Users WHERE id=?", (user_id,))
        row = cursor.fetchone()
        assert row['password_type'] == 'bcrypt'
        assert row['password_bcrypt'] is not None
        
        # Проверяем, что новый пароль работает
        user_data = db.verify_user('testuser', 'testpass')
        assert user_data is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v']) 
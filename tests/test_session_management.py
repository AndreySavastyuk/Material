"""
Тесты для системы управления сессиями пользователей.

Покрывает:
- SessionService
- Интеграцию с AuthorizationService
- Логирование сессий
- Автоматическое истечение сессий
- Функциональность "Запомнить меня"
- Безопасность сессий
"""

import pytest
import tempfile
import os
import sqlite3
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
import time

from db.database import Database
from services.session_service import SessionService
from services.authorization_service import AuthorizationService
from utils.session_logger import SessionLogger, get_session_logger
from migrations.migration_004_user_sessions import up as apply_sessions_migration
from migrations.migration_003_roles_permissions import up as apply_roles_migration


class TestSessionService:
    """Тесты для SessionService."""
    
    @pytest.fixture
    def db(self):
        """Создает тестовую базу данных."""
        fd, db_path = tempfile.mkstemp()
        os.close(fd)
        
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        
        # Создаем базовую структуру
        conn.execute("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                login TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                name TEXT NOT NULL,
                role TEXT DEFAULT 'user'
            )
        """)
        
        # Добавляем тестового пользователя
        conn.execute("""
            INSERT INTO users (login, password, name, role)
            VALUES ('testuser', 'hashedpassword', 'Test User', 'user')
        """)
        
        # Применяем миграции для ролей и сессий
        try:
            apply_roles_migration(conn)
        except Exception:
            pass  # Могут быть ошибки если структура уже создана
        
        apply_sessions_migration(conn)
        
        conn.commit()
        
        # Создаем экземпляр Database
        db = Database()
        db.conn = conn
        db.db_path = db_path
        
        yield db
        
        conn.close()
        os.unlink(db_path)
    
    @pytest.fixture
    def session_service(self, db):
        """Создает экземпляр SessionService."""
        return SessionService(db)
    
    def test_create_session_basic(self, session_service):
        """Тест создания базовой сессии."""
        user_id = 1
        
        session_data = session_service.create_session(
            user_id=user_id,
            remember_me=False,
            ip_address="192.168.1.100",
            user_agent="Test Agent"
        )
        
        assert session_data['user_id'] == user_id
        assert 'session_token' in session_data
        assert 'session_id' in session_data
        assert 'expires_at' in session_data
        assert session_data['remember_me'] is False
        assert session_data['is_active'] is True
        
        # Проверяем что токен уникальный и достаточно длинный
        assert len(session_data['session_token']) >= 32
    
    def test_create_session_remember_me(self, session_service):
        """Тест создания сессии с "Запомнить меня"."""
        user_id = 1
        
        session_data = session_service.create_session(
            user_id=user_id,
            remember_me=True,
            ip_address="192.168.1.100"
        )
        
        assert session_data['remember_me'] is True
        
        # Проверяем что время истечения больше для "запомнить меня"
        expires_at = datetime.fromisoformat(session_data['expires_at'])
        now = datetime.now()
        duration = expires_at - now
        
        # Должно быть больше 24 часов (для remember_me)
        assert duration.total_seconds() > 24 * 60 * 60
    
    def test_validate_session_valid(self, session_service):
        """Тест валидации действительной сессии."""
        user_id = 1
        
        # Создаем сессию
        session_data = session_service.create_session(
            user_id=user_id,
            ip_address="192.168.1.100"
        )
        
        token = session_data['session_token']
        
        # Валидируем сессию
        validated_session = session_service.validate_session(token, "192.168.1.100")
        
        assert validated_session is not None
        assert validated_session['user_id'] == user_id
        assert validated_session['session_token'] == token
        assert validated_session['is_active'] == 1
    
    def test_validate_session_invalid_token(self, session_service):
        """Тест валидации несуществующего токена."""
        invalid_token = "invalid_token_12345"
        
        validated_session = session_service.validate_session(invalid_token)
        
        assert validated_session is None
    
    def test_validate_session_expired(self, session_service, db):
        """Тест валидации истекшей сессии."""
        user_id = 1
        
        # Создаем сессию
        session_data = session_service.create_session(user_id=user_id)
        token = session_data['session_token']
        
        # Принудительно делаем сессию истекшей
        cursor = db.conn.cursor()
        cursor.execute("""
            UPDATE user_sessions 
            SET expires_at = datetime('now', '-1 hour')
            WHERE session_token = ?
        """, (token,))
        db.conn.commit()
        
        # Пытаемся валидировать истекшую сессию
        validated_session = session_service.validate_session(token)
        
        assert validated_session is None
        
        # Проверяем что сессия была инвалидирована
        cursor.execute("""
            SELECT is_active FROM user_sessions WHERE session_token = ?
        """, (token,))
        result = cursor.fetchone()
        assert result['is_active'] == 0
    
    def test_invalidate_session(self, session_service):
        """Тест инвалидации сессии."""
        user_id = 1
        
        # Создаем сессию
        session_data = session_service.create_session(user_id=user_id)
        token = session_data['session_token']
        
        # Инвалидируем сессию
        result = session_service.invalidate_session(token, "Test invalidation")
        
        assert result is True
        
        # Проверяем что сессия больше не валидна
        validated_session = session_service.validate_session(token)
        assert validated_session is None
    
    def test_invalidate_all_user_sessions(self, session_service):
        """Тест инвалидации всех сессий пользователя."""
        user_id = 1
        
        # Создаем несколько сессий
        session1 = session_service.create_session(user_id=user_id)
        session2 = session_service.create_session(user_id=user_id)
        session3 = session_service.create_session(user_id=user_id)
        
        # Инвалидируем все сессии пользователя
        count = session_service.invalidate_all_user_sessions(user_id, "Test cleanup")
        
        assert count == 3
        
        # Проверяем что все сессии инвалидированы
        for session in [session1, session2, session3]:
            validated = session_service.validate_session(session['session_token'])
            assert validated is None
    
    def test_session_limit_enforcement(self, session_service, db):
        """Тест соблюдения лимита сессий на пользователя."""
        user_id = 1
        
        # Устанавливаем лимит в 3 сессии
        cursor = db.conn.cursor()
        cursor.execute("""
            UPDATE session_settings 
            SET setting_value = '3' 
            WHERE setting_name = 'max_sessions_per_user'
        """)
        db.conn.commit()
        
        # Создаем больше сессий чем лимит
        sessions = []
        for i in range(5):
            session = session_service.create_session(user_id=user_id)
            sessions.append(session)
        
        # Проверяем что активно только 3 последние сессии
        active_sessions = session_service.get_user_sessions(user_id, active_only=True)
        assert len(active_sessions) == 3
        
        # Проверяем что старые сессии инвалидированы
        for session in sessions[:2]:  # Первые 2 должны быть инвалидированы
            validated = session_service.validate_session(session['session_token'])
            assert validated is None
    
    def test_cleanup_expired_sessions(self, session_service, db):
        """Тест очистки истекших сессий."""
        user_id = 1
        
        # Создаем сессии
        active_session = session_service.create_session(user_id=user_id)
        expired_session = session_service.create_session(user_id=user_id)
        
        # Делаем одну сессию истекшей
        cursor = db.conn.cursor()
        cursor.execute("""
            UPDATE user_sessions 
            SET expires_at = datetime('now', '-1 hour')
            WHERE session_token = ?
        """, (expired_session['session_token'],))
        db.conn.commit()
        
        # Запускаем очистку
        cleaned_count = session_service.cleanup_expired_sessions()
        
        assert cleaned_count == 1
        
        # Проверяем результат
        active_sessions = session_service.get_user_sessions(user_id, active_only=True)
        assert len(active_sessions) == 1
        assert active_sessions[0]['session_token'] == active_session['session_token']
    
    def test_get_session_statistics(self, session_service):
        """Тест получения статистики сессий."""
        user_id = 1
        
        # Создаем разные типы сессий
        session_service.create_session(user_id=user_id, remember_me=False)
        session_service.create_session(user_id=user_id, remember_me=True)
        session_service.create_session(user_id=user_id, remember_me=True)
        
        stats = session_service.get_session_statistics()
        
        assert 'active_sessions' in stats
        assert 'remember_me_sessions' in stats
        assert 'active_users' in stats
        assert stats['active_sessions'] == 3
        assert stats['remember_me_sessions'] == 2
        assert stats['active_users'] == 1


class TestAuthorizationServiceIntegration:
    """Тесты интеграции AuthorizationService с сессиями."""
    
    @pytest.fixture
    def db(self):
        """Создает тестовую базу данных."""
        fd, db_path = tempfile.mkstemp()
        os.close(fd)
        
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        
        # Создаем базовую структуру
        conn.execute("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                login TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                name TEXT NOT NULL,
                role TEXT DEFAULT 'user'
            )
        """)
        
        # Добавляем тестового пользователя
        conn.execute("""
            INSERT INTO users (login, password, name, role)
            VALUES ('testuser', 'hashedpassword', 'Test User', 'user')
        """)
        
        # Применяем миграции
        try:
            apply_roles_migration(conn)
        except Exception:
            pass
        
        apply_sessions_migration(conn)
        conn.commit()
        
        # Создаем экземпляр Database
        db = Database()
        db.conn = conn
        db.db_path = db_path
        
        yield db
        
        conn.close()
        os.unlink(db_path)
    
    @pytest.fixture
    def auth_service(self, db):
        """Создает экземпляр AuthorizationService."""
        return AuthorizationService(db)
    
    def test_authenticate_user_with_session(self, auth_service, db):
        """Тест аутентификации пользователя с созданием сессии."""
        # Мокаем verify_user
        with patch.object(db, 'verify_user') as mock_verify:
            mock_verify.return_value = {
                'id': 1,
                'login': 'testuser',
                'name': 'Test User',
                'role': 'user'
            }
            
            # Аутентифицируем пользователя
            user_data = auth_service.authenticate_user(
                login='testuser',
                password='password',
                remember_me=True,
                ip_address='192.168.1.100',
                user_agent='Test Agent'
            )
            
            assert user_data is not None
            assert 'session_token' in user_data
            assert 'session_expires_at' in user_data
            assert user_data['id'] == 1
            assert user_data['login'] == 'testuser'
    
    def test_authenticate_by_session_token(self, auth_service, db):
        """Тест аутентификации по токену сессии."""
        # Сначала создаем сессию напрямую
        session_service = SessionService(db)
        session_data = session_service.create_session(
            user_id=1,
            ip_address='192.168.1.100'
        )
        
        # Сессия уже создана с правильным user_id, просто коммитим
        db.conn.commit()
        
        # Теперь аутентифицируемся по токену
        user_data = auth_service.authenticate_by_session_token(
            session_data['session_token'],
            '192.168.1.100'
        )
        
        assert user_data is not None
        assert user_data['id'] == 1
        assert user_data['session_token'] == session_data['session_token']
    
    def test_logout_user_with_session(self, auth_service, db):
        """Тест выхода пользователя с инвалидацией сессии."""
        # Создаем сессию
        session_service = SessionService(db)
        session_data = session_service.create_session(user_id=1)
        
        # Выходим из системы
        auth_service.logout_user(1, session_data['session_token'])
        
        # Проверяем что сессия инвалидирована
        validated_session = session_service.validate_session(session_data['session_token'])
        assert validated_session is None


class TestSessionLogger:
    """Тесты для SessionLogger."""
    
    @pytest.fixture
    def db(self):
        """Создает тестовую базу данных."""
        fd, db_path = tempfile.mkstemp()
        os.close(fd)
        
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        
        # Создаем базовую структуру
        conn.execute("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                login TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                name TEXT NOT NULL
            )
        """)
        
        apply_sessions_migration(conn)
        conn.commit()
        
        db = Database()
        db.conn = conn
        db.db_path = db_path
        
        yield db
        
        conn.close()
        os.unlink(db_path)
    
    @pytest.fixture
    def session_logger(self, db):
        """Создает экземпляр SessionLogger."""
        return SessionLogger(db)
    
    def test_log_login_attempt_success(self, session_logger, db):
        """Тест логирования успешной попытки входа."""
        session_logger.log_login_attempt(
            login='testuser',
            success=True,
            ip_address='192.168.1.100',
            user_agent='Test Agent',
            session_token='test_token_123',
            user_id=1
        )
        
        # Проверяем что запись создана
        cursor = db.conn.cursor()
        cursor.execute("""
            SELECT * FROM user_login_logs 
            WHERE login = 'testuser' AND action = 'login_success'
        """)
        
        log_entry = cursor.fetchone()
        assert log_entry is not None
        assert log_entry['success'] == 1
        assert log_entry['ip_address'] == '192.168.1.100'
        assert log_entry['session_token'] == 'test_token_123'
    
    def test_log_login_attempt_failure(self, session_logger, db):
        """Тест логирования неуспешной попытки входа."""
        session_logger.log_login_attempt(
            login='testuser',
            success=False,
            ip_address='192.168.1.100',
            reason='Invalid password'
        )
        
        # Проверяем что запись создана
        cursor = db.conn.cursor()
        cursor.execute("""
            SELECT * FROM user_login_logs 
            WHERE login = 'testuser' AND action = 'login_failed'
        """)
        
        log_entry = cursor.fetchone()
        assert log_entry is not None
        assert log_entry['success'] == 0
        assert 'Invalid password' in log_entry['reason']
    
    def test_get_security_report(self, session_logger, db):
        """Тест генерации отчета безопасности."""
        # Создаем тестовые логи
        cursor = db.conn.cursor()
        
        # Успешные входы
        for i in range(5):
            cursor.execute("""
                INSERT INTO user_login_logs 
                (login, action, success, ip_address, created_at)
                VALUES (?, 'login_success', 1, '192.168.1.100', datetime('now'))
            """, (f'user{i}',))
        
        # Неуспешные входы
        for i in range(3):
            cursor.execute("""
                INSERT INTO user_login_logs 
                (login, action, success, ip_address, created_at)
                VALUES ('hacker', 'login_failed', 0, '10.0.0.1', datetime('now'))
            """)
        
        db.conn.commit()
        
        # Генерируем отчет
        report = session_logger.get_security_report(hours=24)
        
        assert 'statistics' in report
        assert 'suspicious_ips' in report
        assert 'suspicious_users' in report
        
        stats = report['statistics']
        assert stats['total_attempts'] == 8
        assert stats['successful_logins'] == 5
        assert stats['failed_logins'] == 3
    
    def test_detect_suspicious_activity(self, session_logger, db):
        """Тест обнаружения подозрительной активности."""
        cursor = db.conn.cursor()
        
        # Создаем множественные неудачные попытки с одного IP
        for i in range(10):
            cursor.execute("""
                INSERT INTO user_login_logs 
                (login, action, success, ip_address, created_at)
                VALUES (?, 'login_failed', 0, '10.0.0.1', datetime('now'))
            """, (f'user{i}',))
        
        db.conn.commit()
        
        # Обнаруживаем подозрительную активность
        threats = session_logger.detect_suspicious_activity(hours=1)
        
        assert len(threats) > 0
        
        # Должна быть обнаружена атака brute force с IP
        brute_force_threats = [t for t in threats if t['type'] == 'brute_force_ip']
        assert len(brute_force_threats) > 0
        assert brute_force_threats[0]['ip_address'] == '10.0.0.1'
        assert brute_force_threats[0]['failed_count'] == 10


class TestSessionIntegration:
    """Интеграционные тесты всей системы сессий."""
    
    @pytest.fixture
    def app_components(self):
        """Создает все компоненты приложения для интеграционного тестирования."""
        # Создаем временную БД
        fd, db_path = tempfile.mkstemp()
        os.close(fd)
        
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        
        # Создаем структуру
        conn.execute("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                login TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                name TEXT NOT NULL,
                role TEXT DEFAULT 'user'
            )
        """)
        
        conn.execute("""
            INSERT INTO users (login, password, name, role)
            VALUES ('testuser', 'hashedpassword', 'Test User', 'user')
        """)
        
        # Применяем миграции
        try:
            apply_roles_migration(conn)
        except Exception:
            pass
        
        apply_sessions_migration(conn)
        conn.commit()
        
        # Создаем компоненты
        db = Database()
        db.conn = conn
        db.db_path = db_path
        
        auth_service = AuthorizationService(db)
        session_service = SessionService(db)
        session_logger = SessionLogger(db)
        
        yield {
            'db': db,
            'auth_service': auth_service,
            'session_service': session_service,
            'session_logger': session_logger
        }
        
        conn.close()
        os.unlink(db_path)
    
    def test_full_login_logout_cycle(self, app_components):
        """Тест полного цикла вход-выход с логированием."""
        auth_service = app_components['auth_service']
        session_logger = app_components['session_logger']
        db = app_components['db']
        
        # Мокаем verify_user
        with patch.object(db, 'verify_user') as mock_verify:
            mock_verify.return_value = {
                'id': 1,
                'login': 'testuser',
                'name': 'Test User',
                'role': 'user'
            }
            
            # 1. Вход в систему
            user_data = auth_service.authenticate_user(
                login='testuser',
                password='password',
                remember_me=False,
                ip_address='192.168.1.100',
                user_agent='Test Agent'
            )
            
            assert user_data is not None
            session_token = user_data['session_token']
            
            # 2. Проверяем что вход залогирован
            login_logs = session_logger.get_login_history(user_id=1, hours=1)
            login_entries = [log for log in login_logs if log['action'] == 'login_success']
            assert len(login_entries) > 0
            
            # 3. Валидация сессии
            validated_user = auth_service.authenticate_by_session_token(
                session_token, '192.168.1.100'
            )
            assert validated_user is not None
            assert validated_user['id'] == 1
            
            # 4. Выход из системы
            auth_service.logout_user(1, session_token)
            
            # 5. Проверяем что выход залогирован
            logout_logs = session_logger.get_login_history(user_id=1, hours=1)
            logout_entries = [log for log in logout_logs if 'logout' in log['action']]
            assert len(logout_entries) > 0
            
            # 6. Проверяем что сессия больше не валидна
            invalid_user = auth_service.authenticate_by_session_token(
                session_token, '192.168.1.100'
            )
            assert invalid_user is None
    
    def test_remember_me_functionality(self, app_components):
        """Тест функциональности 'Запомнить меня'."""
        auth_service = app_components['auth_service']
        session_service = app_components['session_service']
        db = app_components['db']
        
        with patch.object(db, 'verify_user') as mock_verify:
            mock_verify.return_value = {
                'id': 1,
                'login': 'testuser',
                'name': 'Test User',
                'role': 'user'
            }
            
            # Создаем сессию с "запомнить меня"
            user_data = auth_service.authenticate_user(
                login='testuser',
                password='password',
                remember_me=True,
                ip_address='192.168.1.100'
            )
            
            session_token = user_data['session_token']
            
            # Проверяем что сессия имеет длительное время жизни
            sessions = session_service.get_user_sessions(1)
            assert len(sessions) == 1
            
            session = sessions[0]
            assert session['remember_me'] == 1
            
            expires_at = datetime.fromisoformat(session['expires_at'])
            now = datetime.now()
            duration = expires_at - now
            
            # Должно быть больше суток
            assert duration.total_seconds() > 24 * 60 * 60
    
    def test_security_monitoring(self, app_components):
        """Тест системы мониторинга безопасности."""
        auth_service = app_components['auth_service']
        session_logger = app_components['session_logger']
        db = app_components['db']
        
        # Симулируем атаку brute force
        for i in range(10):
            with patch.object(db, 'verify_user') as mock_verify:
                mock_verify.return_value = None  # Неуспешная аутентификация
                
                try:
                    auth_service.authenticate_user(
                        login='admin',
                        password=f'wrong_password_{i}',
                        ip_address='10.0.0.1'
                    )
                except Exception:
                    pass  # Ожидаемая ошибка
        
        # Проверяем обнаружение угроз
        threats = session_logger.detect_suspicious_activity(hours=1)
        
        # Должна быть обнаружена brute force атака
        brute_force_threats = [t for t in threats if t['type'] == 'brute_force_ip']
        assert len(brute_force_threats) > 0
        
        # Генерируем отчет безопасности
        report = session_logger.get_security_report(hours=1)
        assert report['statistics']['failed_logins'] >= 10


if __name__ == '__main__':
    pytest.main([__file__, '-v']) 
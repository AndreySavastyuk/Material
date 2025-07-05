"""
Конфигурация pytest и фикстуры для тестов.
"""

import pytest
import sqlite3
import tempfile
import os
from typing import Generator, Dict, Any
from unittest.mock import patch

from db.database import Database
from repositories.base import BaseRepository
from services.base import BaseService


@pytest.fixture(scope="session")
def test_db_path() -> Generator[str, None, None]:
    """
    Фикстура для создания временной тестовой БД.
    
    Yields:
        Путь к временной БД
    """
    # Создаем временный файл для БД
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_file:
        db_path = tmp_file.name
    
    yield db_path
    
    # Удаляем временный файл после тестов
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture(scope="session")
def test_db_connection(test_db_path: str) -> Generator[sqlite3.Connection, None, None]:
    """
    Фикстура для создания подключения к тестовой БД.
    
    Args:
        test_db_path: Путь к тестовой БД
        
    Yields:
        Подключение к БД
    """
    # Создаем подключение к тестовой БД
    connection = sqlite3.connect(test_db_path)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA foreign_keys = ON')
    
    yield connection
    
    # Закрываем подключение
    connection.close()


@pytest.fixture(scope="session")
def test_database(test_db_path: str) -> Generator[Database, None, None]:
    """
    Фикстура для создания экземпляра Database с тестовой БД.
    
    Args:
        test_db_path: Путь к тестовой БД
        
    Yields:
        Экземпляр Database
    """
    # Создаем экземпляр Database с тестовой БД
    database = Database(test_db_path)
    database.connect()
    
    yield database
    
    # Закрываем подключение
    database.close()


@pytest.fixture
def clean_db(test_db_connection: sqlite3.Connection) -> Generator[sqlite3.Connection, None, None]:
    """
    Фикстура для очистки БД перед каждым тестом.
    
    Args:
        test_db_connection: Подключение к тестовой БД
        
    Yields:
        Подключение к чистой БД
    """
    # Получаем список всех таблиц
    cursor = test_db_connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    )
    tables = [row[0] for row in cursor.fetchall()]
    
    # Очищаем все таблицы
    for table in tables:
        test_db_connection.execute(f"DELETE FROM {table}")
    
    test_db_connection.commit()
    
    yield test_db_connection
    
    # Очищаем после теста
    for table in tables:
        test_db_connection.execute(f"DELETE FROM {table}")
    
    test_db_connection.commit()


@pytest.fixture
def sample_material_data() -> Dict[str, Any]:
    """
    Фикстура с примерными данными материала.
    
    Returns:
        Словарь с данными материала
    """
    return {
        'arrival_date': '2024-01-15',
        'supplier_id': 1,
        'order_num': 'ORDER-001',
        'grade_id': 1,
        'rolling_type_id': 1,
        'size': '20x100',
        'cert_num': 'CERT-001',
        'cert_date': '2024-01-10',
        'batch': 'BATCH-001',
        'heat_num': 'HEAT-001',
        'volume_length_mm': 1000.0,
        'volume_weight_kg': 50.0,
        'otk_remarks': 'Все в порядке',
        'needs_lab': 0,
        'to_delete': 0
    }


@pytest.fixture
def sample_supplier_data() -> Dict[str, Any]:
    """
    Фикстура с примерными данными поставщика.
    
    Returns:
        Словарь с данными поставщика
    """
    return {
        'name': 'ООО "Металлургия"'
    }


@pytest.fixture
def sample_grade_data() -> Dict[str, Any]:
    """
    Фикстура с примерными данными марки.
    
    Returns:
        Словарь с данными марки
    """
    return {
        'grade': 'Ст3',
        'density': 7.85,
        'standard': 'ГОСТ 380-2005'
    }


@pytest.fixture
def sample_user_data() -> Dict[str, Any]:
    """
    Фикстура с примерными данными пользователя.
    
    Returns:
        Словарь с данными пользователя
    """
    return {
        'login': 'test_user',
        'password_hash': 'test_hash',
        'role': 'Оператор',
        'name': 'Тестовый пользователь',
        'salt': 'test_salt'
    }


@pytest.fixture
def mock_logger():
    """
    Фикстура для мокирования логгера.
    
    Returns:
        Мок логгера
    """
    with patch('logging.getLogger') as mock_get_logger:
        mock_logger = mock_get_logger.return_value
        mock_logger.info.return_value = None
        mock_logger.warning.return_value = None
        mock_logger.error.return_value = None
        mock_logger.debug.return_value = None
        yield mock_logger


class TestRepository(BaseRepository):
    """
    Тестовый репозиторий для unit тестов.
    """
    
    @property
    def table_name(self) -> str:
        return "test_table"
    
    @property
    def primary_key(self) -> str:
        return "id"


class TestService(BaseService):
    """
    Тестовый сервис для unit тестов.
    """
    
    def create(self, data: Dict[str, Any]) -> int:
        """Создание тестовой записи."""
        # Валидация обязательных полей
        self.validate_required_fields(data, ['name'])
        
        # Валидация типов данных
        self.validate_data_types(data, {'name': str})
        
        # Валидация длины строк
        self.validate_string_length(data, {'name': 100})
        
        try:
            return self._repository.create(data)
        except Exception as e:
            self.handle_db_error(e, "создании тестовой записи")
    
    def update(self, record_id: int, data: Dict[str, Any]) -> bool:
        """Обновление тестовой записи."""
        # Валидация данных
        if 'name' in data:
            self.validate_data_types(data, {'name': str})
            self.validate_string_length(data, {'name': 100})
        
        try:
            return self._repository.update(record_id, data)
        except Exception as e:
            self.handle_db_error(e, f"обновлении тестовой записи ID: {record_id}")


@pytest.fixture
def test_repository(clean_db: sqlite3.Connection) -> TestRepository:
    """
    Фикстура для создания тестового репозитория.
    
    Args:
        clean_db: Подключение к чистой БД
        
    Returns:
        Экземпляр тестового репозитория
    """
    # Создаем тестовую таблицу
    clean_db.execute('''
        CREATE TABLE IF NOT EXISTS test_table (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            to_delete INTEGER DEFAULT 0
        )
    ''')
    clean_db.commit()
    
    return TestRepository(clean_db)


@pytest.fixture
def test_service(test_repository: TestRepository) -> TestService:
    """
    Фикстура для создания тестового сервиса.
    
    Args:
        test_repository: Тестовый репозиторий
        
    Returns:
        Экземпляр тестового сервиса
    """
    return TestService(test_repository)


# Маркеры для категоризации тестов
pytest_plugins = []

def pytest_configure(config):
    """Настройка pytest."""
    config.addinivalue_line(
        "markers", "unit: unit тесты"
    )
    config.addinivalue_line(
        "markers", "integration: integration тесты"
    )
    config.addinivalue_line(
        "markers", "slow: медленные тесты"
    )
    config.addinivalue_line(
        "markers", "database: тесты с базой данных"
    )
    config.addinivalue_line(
        "markers", "gui: тесты GUI"
    ) 
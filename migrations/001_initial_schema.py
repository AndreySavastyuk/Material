"""
Миграция 001: Создание начальной схемы БД.
"""

from typing import List
import sqlite3
import logging

logger = logging.getLogger(__name__)


def up(connection: sqlite3.Connection) -> None:
    """
    Применение миграции - создание начальной схемы.
    
    Args:
        connection: Подключение к БД
    """
    logger.info("Применение миграции 001: Создание начальной схемы")
    
    # Создаем базовые таблицы
    connection.executescript('''
        -- Поставщики
        CREATE TABLE IF NOT EXISTS Suppliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        
        -- Марки металла
        CREATE TABLE IF NOT EXISTS Grades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            grade TEXT UNIQUE NOT NULL,
            density REAL NOT NULL,
            standard TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        
        -- Виды проката
        CREATE TABLE IF NOT EXISTS RollingTypes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT UNIQUE NOT NULL,
            icon_path TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        
        -- Пользователи
        CREATE TABLE IF NOT EXISTS Users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            login TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            name TEXT,
            salt TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        
        -- Материалы
        CREATE TABLE IF NOT EXISTS Materials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            arrival_date TEXT NOT NULL,
            supplier_id INTEGER NOT NULL REFERENCES Suppliers(id),
            order_num TEXT NOT NULL,
            grade_id INTEGER NOT NULL REFERENCES Grades(id),
            rolling_type_id INTEGER NOT NULL REFERENCES RollingTypes(id),
            size TEXT NOT NULL,
            cert_num TEXT NOT NULL,
            cert_date TEXT NOT NULL,
            batch TEXT NOT NULL,
            heat_num TEXT NOT NULL,
            volume_length_mm REAL NOT NULL,
            volume_weight_kg REAL NOT NULL,
            otk_remarks TEXT,
            needs_lab INTEGER NOT NULL DEFAULT 0,
            to_delete INTEGER NOT NULL DEFAULT 0,
            cert_saved_at TEXT,
            cert_scan_path TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        
        -- Документы
        CREATE TABLE IF NOT EXISTS Documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            material_id INTEGER NOT NULL REFERENCES Materials(id),
            doc_type TEXT NOT NULL,
            file_path TEXT NOT NULL,
            upload_date TEXT NOT NULL,
            uploaded_by TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        
        -- Блокировки записей
        CREATE TABLE IF NOT EXISTS RecordLocks (
            material_id INTEGER PRIMARY KEY REFERENCES Materials(id),
            locked_by TEXT NOT NULL,
            locked_at TEXT NOT NULL
        );
        
        -- Дефекты
        CREATE TABLE IF NOT EXISTS defects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            material_id INTEGER NOT NULL REFERENCES Materials(id),
            defect_type TEXT NOT NULL,
            description TEXT,
            reported_by TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            to_delete INTEGER DEFAULT 0
        );
        
        -- Лабораторные заявки
        CREATE TABLE IF NOT EXISTS lab_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            creation_date TEXT NOT NULL,
            request_number TEXT NOT NULL,
            material_id INTEGER NOT NULL REFERENCES Materials(id),
            tests_json TEXT NOT NULL,
            results_json TEXT NOT NULL DEFAULT '[]',
            status TEXT NOT NULL,
            archived INTEGER NOT NULL DEFAULT 0,
            last_pdf_path TEXT DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        
        -- Сценарии испытаний
        CREATE TABLE IF NOT EXISTS test_scenarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            material_id INTEGER NOT NULL REFERENCES Grades(id),
            name TEXT NOT NULL,
            tests_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        
        -- Комментарии к лабораторным заявкам
        CREATE TABLE IF NOT EXISTS lab_comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER NOT NULL REFERENCES lab_requests(id),
            author TEXT NOT NULL,
            body TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            to_delete INTEGER NOT NULL DEFAULT 0
        );
        
        -- Журнал изменений лабораторных заявок
        CREATE TABLE IF NOT EXISTS lab_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER NOT NULL REFERENCES lab_requests(id),
            author TEXT NOT NULL,
            action TEXT NOT NULL,
            payload TEXT,
            at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        
        -- Образцы
        CREATE TABLE IF NOT EXISTS Specimens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            pdf_path TEXT NOT NULL,
            test_type TEXT DEFAULT '',
            length_mm REAL DEFAULT 0,
            standard TEXT DEFAULT '',
            sample_number TEXT DEFAULT '',
            specimen_type TEXT DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
    ''')
    
    # Создаем индексы
    connection.executescript('''
        -- Индексы для быстрого поиска
        CREATE INDEX IF NOT EXISTS idx_materials_arrival_date ON Materials(arrival_date);
        CREATE INDEX IF NOT EXISTS idx_materials_supplier ON Materials(supplier_id);
        CREATE INDEX IF NOT EXISTS idx_materials_grade ON Materials(grade_id);
        CREATE INDEX IF NOT EXISTS idx_materials_to_delete ON Materials(to_delete);
        
        CREATE INDEX IF NOT EXISTS idx_defects_material ON defects(material_id);
        CREATE INDEX IF NOT EXISTS idx_defects_type ON defects(defect_type);
        CREATE INDEX IF NOT EXISTS idx_defects_time ON defects(timestamp);
        
        CREATE INDEX IF NOT EXISTS idx_lab_requests_material ON lab_requests(material_id);
        CREATE INDEX IF NOT EXISTS idx_lab_requests_status ON lab_requests(status);
        CREATE INDEX IF NOT EXISTS idx_lab_requests_archived ON lab_requests(archived);
        
        CREATE INDEX IF NOT EXISTS idx_lab_comments_req ON lab_comments(request_id);
        CREATE INDEX IF NOT EXISTS idx_lab_logs_req ON lab_logs(request_id);
        
        CREATE INDEX IF NOT EXISTS idx_documents_material ON Documents(material_id);
    ''')
    
    connection.commit()
    logger.info("Миграция 001 успешно применена")


def down(connection: sqlite3.Connection) -> None:
    """
    Откат миграции - удаление таблиц.
    
    Args:
        connection: Подключение к БД
    """
    logger.info("Откат миграции 001: Удаление таблиц")
    
    # Список таблиц для удаления (в порядке, учитывающем внешние ключи)
    tables_to_drop = [
        'lab_logs',
        'lab_comments',
        'test_scenarios',
        'lab_requests',
        'defects',
        'RecordLocks',
        'Documents',
        'Materials',
        'Specimens',
        'Users',
        'RollingTypes',
        'Grades',
        'Suppliers'
    ]
    
    for table in tables_to_drop:
        connection.execute(f"DROP TABLE IF EXISTS {table}")
    
    connection.commit()
    logger.info("Миграция 001 успешно откачена")


def get_version() -> str:
    """
    Получение версии миграции.
    
    Returns:
        Версия миграции
    """
    return "001"


def get_description() -> str:
    """
    Получение описания миграции.
    
    Returns:
        Описание миграции
    """
    return "Создание начальной схемы БД"


def get_dependencies() -> List[str]:
    """
    Получение зависимостей миграции.
    
    Returns:
        Список зависимостей (версий миграций)
    """
    return []  # Начальная миграция не имеет зависимостей 
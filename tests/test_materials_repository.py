"""
Тесты для MaterialsRepository.
"""

import pytest
import sqlite3
import tempfile
import os
from datetime import datetime
from unittest.mock import patch, MagicMock

from repositories.materials_repository import MaterialsRepository


class TestMaterialsRepository:
    """Тесты для MaterialsRepository."""

    @pytest.fixture
    def db_connection(self):
        """Создает временную БД для тестов."""
        conn = sqlite3.connect(':memory:')
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys = ON')
        
        # Создаем необходимые таблицы
        conn.executescript('''
            CREATE TABLE Materials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                arrival_date TEXT DEFAULT '',
                supplier_id INTEGER,
                order_num TEXT DEFAULT '',
                grade_id INTEGER,
                rolling_type_id INTEGER,
                size TEXT DEFAULT '',
                cert_num TEXT DEFAULT '',
                cert_date TEXT DEFAULT '',
                batch TEXT DEFAULT '',
                heat_num TEXT DEFAULT '',
                volume_length_mm REAL DEFAULT 0,
                volume_weight_kg REAL DEFAULT 0,
                otk_remarks TEXT DEFAULT '',
                needs_lab INTEGER DEFAULT 0,
                cert_scan_path TEXT,
                cert_saved_at TEXT,
                to_delete INTEGER DEFAULT 0
            );

            CREATE TABLE Suppliers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            );

            CREATE TABLE Grades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                grade TEXT UNIQUE NOT NULL,
                density REAL NOT NULL,
                standard TEXT
            );

            CREATE TABLE RollingTypes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT UNIQUE NOT NULL,
                icon_path TEXT
            );

            CREATE TABLE Documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                material_id INTEGER NOT NULL REFERENCES Materials(id),
                doc_type TEXT,
                file_path TEXT,
                upload_date TEXT,
                uploaded_by TEXT
            );

            CREATE TABLE RecordLocks (
                material_id INTEGER PRIMARY KEY REFERENCES Materials(id),
                locked_by TEXT NOT NULL,
                locked_at TEXT NOT NULL
            );

            CREATE TABLE defects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                material_id INTEGER NOT NULL REFERENCES Materials(id),
                defect_type TEXT NOT NULL,
                description TEXT,
                reported_by TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                to_delete INTEGER DEFAULT 0
            );

            CREATE TABLE lab_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                creation_date TEXT NOT NULL,
                request_number TEXT NOT NULL,
                material_id INTEGER NOT NULL REFERENCES Materials(id),
                tests_json TEXT NOT NULL,
                results_json TEXT NOT NULL DEFAULT '[]',
                status TEXT NOT NULL,
                archived INTEGER NOT NULL DEFAULT 0
            );
        ''')
        
        # Добавляем тестовые данные
        conn.executescript('''
            INSERT INTO Suppliers (id, name) VALUES (1, 'Тестовый поставщик');
            INSERT INTO Grades (id, grade, density, standard) VALUES (1, 'Тестовая марка', 7.85, 'ГОСТ 1234');
            INSERT INTO RollingTypes (id, type) VALUES (1, 'Лист');
        ''')
        
        conn.commit()
        yield conn
        conn.close()

    @pytest.fixture
    def temp_docs_dir(self):
        """Создает временную папку для документов."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def materials_repo(self, db_connection, temp_docs_dir):
        """Создает экземпляр MaterialsRepository."""
        return MaterialsRepository(db_connection, temp_docs_dir)

    def test_table_name_and_primary_key(self, materials_repo):
        """Тест свойств table_name и primary_key."""
        assert materials_repo.table_name == 'Materials'
        assert materials_repo.primary_key == 'id'

    def test_create_material_success(self, materials_repo):
        """Тест успешного создания материала."""
        material_data = {
            'arrival_date': '2024-01-01',
            'supplier_id': 1,
            'grade_id': 1,
            'rolling_type_id': 1,
            'size': '10x100x1000',
            'cert_num': 'CERT001',
            'cert_date': '2024-01-01',
            'batch': 'BATCH001',
            'heat_num': 'HEAT001',
            'volume_length_mm': 1000.0,
            'volume_weight_kg': 78.5,
            'needs_lab': 1
        }
        
        material_id = materials_repo.create_material(material_data)
        
        assert material_id > 0
        
        # Проверяем, что материал создан
        created_material = materials_repo.get_by_id(material_id)
        assert created_material is not None
        assert created_material['arrival_date'] == '2024-01-01'
        assert created_material['supplier_id'] == 1
        assert created_material['grade_id'] == 1

    def test_create_material_missing_required_fields(self, materials_repo):
        """Тест создания материала без обязательных полей."""
        material_data = {
            'size': '10x100x1000',
            'cert_num': 'CERT001'
        }
        
        with pytest.raises(ValueError) as exc_info:
            materials_repo.create_material(material_data)
        
        assert "Обязательное поле" in str(exc_info.value)

    def test_get_materials_with_relations(self, materials_repo):
        """Тест получения материалов с данными из связанных таблиц."""
        # Создаем материал
        material_data = {
            'arrival_date': '2024-01-01',
            'supplier_id': 1,
            'grade_id': 1,
            'rolling_type_id': 1,
            'size': '10x100x1000'
        }
        materials_repo.create_material(material_data)
        
        materials = materials_repo.get_materials_with_relations()
        
        assert len(materials) == 1
        assert materials[0]['supplier'] == 'Тестовый поставщик'
        assert materials[0]['grade'] == 'Тестовая марка'
        assert materials[0]['rolling_type'] == 'Лист'

    def test_get_materials_with_relations_exclude_deleted(self, materials_repo):
        """Тест исключения помеченных на удаление материалов."""
        # Создаем обычный материал
        material_data = {
            'arrival_date': '2024-01-01',
            'supplier_id': 1,
            'grade_id': 1,
        }
        normal_id = materials_repo.create_material(material_data)
        
        # Создаем помеченный на удаление материал
        deleted_material_data = {
            'arrival_date': '2024-01-02',
            'supplier_id': 1,
            'grade_id': 1,
            'to_delete': 1
        }
        deleted_id = materials_repo.create_material(deleted_material_data)
        
        # Получаем без удаленных
        materials = materials_repo.get_materials_with_relations(include_deleted=False)
        assert len(materials) == 1
        assert materials[0]['id'] == normal_id
        
        # Получаем с удаленными
        materials_with_deleted = materials_repo.get_materials_with_relations(include_deleted=True)
        assert len(materials_with_deleted) == 2

    def test_update_material_success(self, materials_repo):
        """Тест успешного обновления материала."""
        # Создаем материал
        material_data = {
            'arrival_date': '2024-01-01',
            'supplier_id': 1,
            'grade_id': 1,
            'size': '10x100x1000'
        }
        material_id = materials_repo.create_material(material_data)
        
        # Обновляем материал
        update_data = {
            'size': '20x200x2000',
            'otk_remarks': 'Обновленные заметки'
        }
        
        result = materials_repo.update_material(material_id, update_data)
        
        assert result is True
        
        # Проверяем обновление
        updated_material = materials_repo.get_by_id(material_id)
        assert updated_material['size'] == '20x200x2000'
        assert updated_material['otk_remarks'] == 'Обновленные заметки'

    def test_update_material_not_found(self, materials_repo):
        """Тест обновления несуществующего материала."""
        update_data = {'size': '20x200x2000'}
        
        result = materials_repo.update_material(999, update_data)
        
        assert result is False

    def test_mark_for_deletion(self, materials_repo):
        """Тест пометки материала на удаление."""
        # Создаем материал
        material_data = {
            'arrival_date': '2024-01-01',
            'supplier_id': 1,
            'grade_id': 1,
        }
        material_id = materials_repo.create_material(material_data)
        
        # Помечаем на удаление
        result = materials_repo.mark_for_deletion(material_id)
        
        assert result is True
        
        # Проверяем пометку
        material = materials_repo.get_by_id(material_id)
        assert material['to_delete'] == 1

    def test_unmark_for_deletion(self, materials_repo):
        """Тест снятия пометки удаления."""
        # Создаем материал, помеченный на удаление
        material_data = {
            'arrival_date': '2024-01-01',
            'supplier_id': 1,
            'grade_id': 1,
            'to_delete': 1
        }
        material_id = materials_repo.create_material(material_data)
        
        # Снимаем пометку
        result = materials_repo.unmark_for_deletion(material_id)
        
        assert result is True
        
        # Проверяем снятие пометки
        material = materials_repo.get_by_id(material_id)
        assert material['to_delete'] == 0

    def test_get_marked_for_deletion(self, materials_repo):
        """Тест получения материалов, помеченных на удаление."""
        # Создаем обычный материал
        normal_material_data = {
            'arrival_date': '2024-01-01',
            'supplier_id': 1,
            'grade_id': 1,
        }
        materials_repo.create_material(normal_material_data)
        
        # Создаем помеченный на удаление материал
        deleted_material_data = {
            'arrival_date': '2024-01-02',
            'supplier_id': 1,
            'grade_id': 1,
            'to_delete': 1
        }
        deleted_id = materials_repo.create_material(deleted_material_data)
        
        marked_materials = materials_repo.get_marked_for_deletion()
        
        assert len(marked_materials) == 1
        assert marked_materials[0]['id'] == deleted_id

    def test_permanently_delete_material(self, materials_repo):
        """Тест физического удаления материала."""
        # Создаем материал
        material_data = {
            'arrival_date': '2024-01-01',
            'supplier_id': 1,
            'grade_id': 1,
        }
        material_id = materials_repo.create_material(material_data)
        
        # Добавляем связанные данные
        db_conn = materials_repo._connection
        db_conn.execute(
            "INSERT INTO Documents (material_id, doc_type, file_path, upload_date, uploaded_by) VALUES (?, ?, ?, ?, ?)",
            (material_id, 'certificate', '/path/to/cert.pdf', '2024-01-01T12:00:00', 'admin')
        )
        db_conn.execute(
            "INSERT INTO defects (material_id, defect_type, description) VALUES (?, ?, ?)",
            (material_id, 'surface', 'Царапина')
        )
        db_conn.execute(
            "INSERT INTO RecordLocks (material_id, locked_by, locked_at) VALUES (?, ?, ?)",
            (material_id, 'admin', '2024-01-01T12:00:00')
        )
        db_conn.commit()
        
        # Удаляем физически
        result = materials_repo.permanently_delete_material(material_id)
        
        assert result is True
        
        # Проверяем удаление
        assert materials_repo.get_by_id(material_id) is None
        
        # Проверяем удаление связанных данных
        cursor = db_conn.execute("SELECT COUNT(*) as count FROM Documents WHERE material_id = ?", (material_id,))
        assert cursor.fetchone()['count'] == 0
        
        cursor = db_conn.execute("SELECT COUNT(*) as count FROM defects WHERE material_id = ?", (material_id,))
        assert cursor.fetchone()['count'] == 0
        
        cursor = db_conn.execute("SELECT COUNT(*) as count FROM RecordLocks WHERE material_id = ?", (material_id,))
        assert cursor.fetchone()['count'] == 0

    def test_acquire_lock_success(self, materials_repo):
        """Тест успешного захвата блокировки."""
        # Создаем материал
        material_data = {
            'arrival_date': '2024-01-01',
            'supplier_id': 1,
            'grade_id': 1,
        }
        material_id = materials_repo.create_material(material_data)
        
        # Захватываем блокировку
        result = materials_repo.acquire_lock(material_id, 'admin')
        
        assert result is True
        
        # Проверяем блокировку
        is_locked, locked_by = materials_repo.is_locked(material_id)
        assert is_locked is True
        assert locked_by == 'admin'

    def test_acquire_lock_already_locked(self, materials_repo):
        """Тест захвата блокировки уже заблокированного материала."""
        # Создаем материал
        material_data = {
            'arrival_date': '2024-01-01',
            'supplier_id': 1,
            'grade_id': 1,
        }
        material_id = materials_repo.create_material(material_data)
        
        # Захватываем блокировку первым пользователем
        materials_repo.acquire_lock(material_id, 'admin')
        
        # Пытаемся захватить блокировку вторым пользователем
        result = materials_repo.acquire_lock(material_id, 'user')
        
        assert result is False

    def test_release_lock_success(self, materials_repo):
        """Тест успешного освобождения блокировки."""
        # Создаем материал
        material_data = {
            'arrival_date': '2024-01-01',
            'supplier_id': 1,
            'grade_id': 1,
        }
        material_id = materials_repo.create_material(material_data)
        
        # Захватываем и освобождаем блокировку
        materials_repo.acquire_lock(material_id, 'admin')
        result = materials_repo.release_lock(material_id, 'admin')
        
        assert result is True
        
        # Проверяем освобождение
        is_locked, locked_by = materials_repo.is_locked(material_id)
        assert is_locked is False
        assert locked_by == ''

    def test_release_lock_not_found(self, materials_repo):
        """Тест освобождения несуществующей блокировки."""
        # Создаем материал
        material_data = {
            'arrival_date': '2024-01-01',
            'supplier_id': 1,
            'grade_id': 1,
        }
        material_id = materials_repo.create_material(material_data)
        
        # Пытаемся освободить несуществующую блокировку
        result = materials_repo.release_lock(material_id, 'admin')
        
        assert result is False

    def test_is_locked_not_locked(self, materials_repo):
        """Тест проверки незаблокированного материала."""
        # Создаем материал
        material_data = {
            'arrival_date': '2024-01-01',
            'supplier_id': 1,
            'grade_id': 1,
        }
        material_id = materials_repo.create_material(material_data)
        
        # Проверяем блокировку
        is_locked, locked_by = materials_repo.is_locked(material_id)
        
        assert is_locked is False
        assert locked_by == ''

    def test_get_documents(self, materials_repo):
        """Тест получения документов материала."""
        # Создаем материал
        material_data = {
            'arrival_date': '2024-01-01',
            'supplier_id': 1,
            'grade_id': 1,
        }
        material_id = materials_repo.create_material(material_data)
        
        # Добавляем документы
        db_conn = materials_repo._connection
        db_conn.execute(
            "INSERT INTO Documents (material_id, doc_type, file_path, upload_date, uploaded_by) VALUES (?, ?, ?, ?, ?)",
            (material_id, 'certificate', '/path/to/cert.pdf', '2024-01-01T12:00:00', 'admin')
        )
        db_conn.execute(
            "INSERT INTO Documents (material_id, doc_type, file_path, upload_date, uploaded_by) VALUES (?, ?, ?, ?, ?)",
            (material_id, 'photo', '/path/to/photo.jpg', '2024-01-01T13:00:00', 'admin')
        )
        db_conn.commit()
        
        documents = materials_repo.get_documents(material_id)
        
        assert len(documents) == 2
        assert documents[0]['doc_type'] == 'photo'  # Последний добавленный (по убыванию даты)
        assert documents[1]['doc_type'] == 'certificate'

    @patch('shutil.copy2')
    @patch('os.makedirs')
    def test_add_document_success(self, mock_makedirs, mock_copy, materials_repo):
        """Тест успешного добавления документа."""
        # Создаем материал
        material_data = {
            'arrival_date': '2024-01-01',
            'supplier_id': 1,
            'grade_id': 1,
        }
        material_id = materials_repo.create_material(material_data)
        
        # Добавляем документ
        document_id = materials_repo.add_document(
            material_id=material_id,
            doc_type='certificate',
            src_path='/path/to/source.pdf',
            uploaded_by='admin'
        )
        
        assert document_id > 0
        
        # Проверяем вызовы
        mock_makedirs.assert_called_once()
        mock_copy.assert_called_once()
        
        # Проверяем сохранение в БД
        documents = materials_repo.get_documents(material_id)
        assert len(documents) == 1
        assert documents[0]['doc_type'] == 'certificate'
        assert documents[0]['uploaded_by'] == 'admin'

    def test_get_materials_by_supplier(self, materials_repo):
        """Тест получения материалов по поставщику."""
        # Создаем материалы для разных поставщиков
        db_conn = materials_repo._connection
        db_conn.execute("INSERT INTO Suppliers (id, name) VALUES (2, 'Поставщик 2')")
        db_conn.commit()
        
        material1_data = {
            'arrival_date': '2024-01-01',
            'supplier_id': 1,
            'grade_id': 1,
        }
        material2_data = {
            'arrival_date': '2024-01-02',
            'supplier_id': 2,
            'grade_id': 1,
        }
        material3_data = {
            'arrival_date': '2024-01-03',
            'supplier_id': 1,
            'grade_id': 1,
        }
        
        materials_repo.create_material(material1_data)
        materials_repo.create_material(material2_data)
        materials_repo.create_material(material3_data)
        
        # Получаем материалы поставщика 1
        supplier1_materials = materials_repo.get_materials_by_supplier(1)
        
        assert len(supplier1_materials) == 2
        for material in supplier1_materials:
            assert material['supplier_id'] == 1

    def test_get_materials_by_grade(self, materials_repo):
        """Тест получения материалов по марке."""
        # Создаем материалы для разных марок
        db_conn = materials_repo._connection
        db_conn.execute("INSERT INTO Grades (id, grade, density) VALUES (2, 'Марка 2', 7.8)")
        db_conn.commit()
        
        material1_data = {
            'arrival_date': '2024-01-01',
            'supplier_id': 1,
            'grade_id': 1,
        }
        material2_data = {
            'arrival_date': '2024-01-02',
            'supplier_id': 1,
            'grade_id': 2,
        }
        material3_data = {
            'arrival_date': '2024-01-03',
            'supplier_id': 1,
            'grade_id': 1,
        }
        
        materials_repo.create_material(material1_data)
        materials_repo.create_material(material2_data)
        materials_repo.create_material(material3_data)
        
        # Получаем материалы марки 1
        grade1_materials = materials_repo.get_materials_by_grade(1)
        
        assert len(grade1_materials) == 2
        for material in grade1_materials:
            assert material['grade_id'] == 1

    def test_get_materials_needing_lab_tests(self, materials_repo):
        """Тест получения материалов для лабораторных испытаний."""
        # Создаем материалы с разными значениями needs_lab
        material1_data = {
            'arrival_date': '2024-01-01',
            'supplier_id': 1,
            'grade_id': 1,
            'needs_lab': 1
        }
        material2_data = {
            'arrival_date': '2024-01-02',
            'supplier_id': 1,
            'grade_id': 1,
            'needs_lab': 0
        }
        material3_data = {
            'arrival_date': '2024-01-03',
            'supplier_id': 1,
            'grade_id': 1,
            'needs_lab': 1
        }
        
        materials_repo.create_material(material1_data)
        materials_repo.create_material(material2_data)
        materials_repo.create_material(material3_data)
        
        # Получаем материалы для лабораторных испытаний
        lab_materials = materials_repo.get_materials_needing_lab_tests()
        
        assert len(lab_materials) == 2
        for material in lab_materials:
            assert material['needs_lab'] == 1

    def test_search_materials(self, materials_repo):
        """Тест поиска материалов."""
        # Создаем материалы с разными данными
        material1_data = {
            'arrival_date': '2024-01-01',
            'supplier_id': 1,
            'grade_id': 1,
            'order_num': 'ORD-001',
            'cert_num': 'CERT-001',
            'batch': 'BATCH-001',
            'size': '10x100x1000'
        }
        material2_data = {
            'arrival_date': '2024-01-02',
            'supplier_id': 1,
            'grade_id': 1,
            'order_num': 'ORD-002',
            'cert_num': 'CERT-002',
            'batch': 'BATCH-002',
            'size': '20x200x2000'
        }
        
        materials_repo.create_material(material1_data)
        materials_repo.create_material(material2_data)
        
        # Поиск по номеру заказа
        results = materials_repo.search_materials('ORD-001')
        assert len(results) == 1
        assert results[0]['order_num'] == 'ORD-001'
        
        # Поиск по размеру
        results = materials_repo.search_materials('20x200')
        assert len(results) == 1
        assert results[0]['size'] == '20x200x2000'
        
        # Поиск по частичному совпадению
        results = materials_repo.search_materials('CERT')
        assert len(results) == 2
        
        # Поиск слишком коротким запросом
        results = materials_repo.search_materials('O')
        assert len(results) == 0

    def test_get_materials_statistics(self, materials_repo):
        """Тест получения статистики по материалам."""
        # Создаем материалы с разными статусами
        material1_data = {
            'arrival_date': '2024-01-01',
            'supplier_id': 1,
            'grade_id': 1,
            'needs_lab': 1
        }
        material2_data = {
            'arrival_date': '2024-01-02',
            'supplier_id': 1,
            'grade_id': 1,
            'to_delete': 1
        }
        material3_data = {
            'arrival_date': '2024-01-03',
            'supplier_id': 1,
            'grade_id': 1,
        }
        
        id1 = materials_repo.create_material(material1_data)
        materials_repo.create_material(material2_data)
        materials_repo.create_material(material3_data)
        
        # Добавляем блокировку
        materials_repo.acquire_lock(id1, 'admin')
        
        # Получаем статистику
        stats = materials_repo.get_materials_statistics()
        
        assert stats['total_materials'] == 2  # Без помеченных на удаление
        assert stats['deleted_materials'] == 1
        assert stats['lab_needed'] == 1
        assert stats['locked_materials'] == 1
        assert len(stats['top_suppliers']) == 1
        assert stats['top_suppliers'][0]['name'] == 'Тестовый поставщик'
        assert stats['top_suppliers'][0]['count'] == 2 
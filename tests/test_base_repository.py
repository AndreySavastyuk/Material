"""
Тесты для BaseRepository.
"""

import pytest
import sqlite3
from typing import Dict, Any

from repositories.base import BaseRepository
from services.base import ValidationError, NotFoundError


@pytest.mark.unit
@pytest.mark.database
class TestBaseRepository:
    """Тесты для BaseRepository."""
    
    def test_create_record(self, test_repository):
        """Тест создания записи."""
        data = {'name': 'Test Record'}
        
        record_id = test_repository.create(data)
        
        assert record_id is not None
        assert record_id > 0
    
    def test_get_by_id_existing(self, test_repository):
        """Тест получения существующей записи."""
        data = {'name': 'Test Record'}
        record_id = test_repository.create(data)
        
        result = test_repository.get_by_id(record_id)
        
        assert result is not None
        assert result['id'] == record_id
        assert result['name'] == 'Test Record'
    
    def test_get_by_id_not_existing(self, test_repository):
        """Тест получения несуществующей записи."""
        result = test_repository.get_by_id(999)
        
        assert result is None
    
    def test_get_all_empty(self, test_repository):
        """Тест получения всех записей из пустой таблицы."""
        result = test_repository.get_all()
        
        assert result == []
    
    def test_get_all_with_records(self, test_repository):
        """Тест получения всех записей."""
        # Создаем несколько записей
        test_repository.create({'name': 'Record 1'})
        test_repository.create({'name': 'Record 2'})
        test_repository.create({'name': 'Record 3'})
        
        result = test_repository.get_all()
        
        assert len(result) == 3
        assert all('name' in record for record in result)
    
    def test_get_all_with_filters(self, test_repository):
        """Тест получения записей с фильтрами."""
        # Создаем записи
        test_repository.create({'name': 'Record 1'})
        test_repository.create({'name': 'Record 2'})
        
        # Применяем фильтр
        result = test_repository.get_all({'name': 'Record 1'})
        
        assert len(result) == 1
        assert result[0]['name'] == 'Record 1'
    
    def test_update_existing_record(self, test_repository):
        """Тест обновления существующей записи."""
        data = {'name': 'Original Name'}
        record_id = test_repository.create(data)
        
        success = test_repository.update(record_id, {'name': 'Updated Name'})
        
        assert success is True
        
        # Проверяем, что запись обновилась
        result = test_repository.get_by_id(record_id)
        assert result['name'] == 'Updated Name'
    
    def test_update_non_existing_record(self, test_repository):
        """Тест обновления несуществующей записи."""
        success = test_repository.update(999, {'name': 'Updated Name'})
        
        assert success is False
    
    def test_delete_existing_record(self, test_repository):
        """Тест удаления существующей записи."""
        data = {'name': 'Test Record'}
        record_id = test_repository.create(data)
        
        success = test_repository.delete(record_id)
        
        assert success is True
        
        # Проверяем, что запись удалена
        result = test_repository.get_by_id(record_id)
        assert result is None
    
    def test_delete_non_existing_record(self, test_repository):
        """Тест удаления несуществующей записи."""
        success = test_repository.delete(999)
        
        assert success is False
    
    def test_soft_delete_record(self, test_repository):
        """Тест мягкого удаления записи."""
        data = {'name': 'Test Record'}
        record_id = test_repository.create(data)
        
        success = test_repository.soft_delete(record_id)
        
        assert success is True
        
        # Проверяем, что запись помечена как удаленная
        result = test_repository.get_by_id(record_id)
        assert result is not None
        assert result['to_delete'] == 1
    
    def test_restore_record(self, test_repository):
        """Тест восстановления записи."""
        data = {'name': 'Test Record'}
        record_id = test_repository.create(data)
        
        # Сначала помечаем на удаление
        test_repository.soft_delete(record_id)
        
        # Затем восстанавливаем
        success = test_repository.restore(record_id)
        
        assert success is True
        
        # Проверяем, что запись восстановлена
        result = test_repository.get_by_id(record_id)
        assert result is not None
        assert result['to_delete'] == 0
    
    def test_count_empty_table(self, test_repository):
        """Тест подсчета записей в пустой таблице."""
        count = test_repository.count()
        
        assert count == 0
    
    def test_count_with_records(self, test_repository):
        """Тест подсчета записей."""
        # Создаем несколько записей
        test_repository.create({'name': 'Record 1'})
        test_repository.create({'name': 'Record 2'})
        test_repository.create({'name': 'Record 3'})
        
        count = test_repository.count()
        
        assert count == 3
    
    def test_count_with_filters(self, test_repository):
        """Тест подсчета записей с фильтрами."""
        # Создаем записи
        test_repository.create({'name': 'Record 1'})
        test_repository.create({'name': 'Record 2'})
        test_repository.create({'name': 'Record 1'})
        
        count = test_repository.count({'name': 'Record 1'})
        
        assert count == 2
    
    def test_exists_existing_record(self, test_repository):
        """Тест проверки существования записи."""
        data = {'name': 'Test Record'}
        record_id = test_repository.create(data)
        
        exists = test_repository.exists(record_id)
        
        assert exists is True
    
    def test_exists_non_existing_record(self, test_repository):
        """Тест проверки несуществующей записи."""
        exists = test_repository.exists(999)
        
        assert exists is False
    
    def test_execute_custom_query(self, test_repository):
        """Тест выполнения кастомного запроса."""
        # Создаем записи
        test_repository.create({'name': 'Record 1'})
        test_repository.create({'name': 'Record 2'})
        
        # Выполняем кастомный запрос
        result = test_repository.execute_custom_query(
            "SELECT COUNT(*) as count FROM test_table WHERE name LIKE ?",
            ('Record%',)
        )
        
        assert len(result) == 1
        assert result[0]['count'] == 2 
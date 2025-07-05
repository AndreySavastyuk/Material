"""
Тесты для MaterialsService.
"""

import pytest
import sqlite3
import tempfile
import os
from unittest.mock import Mock, patch

from services.materials_service import MaterialsService
from repositories.materials_repository import MaterialsRepository
from utils.exceptions import (
    ValidationError, RequiredFieldError, InvalidFormatError,
    ValueOutOfRangeError, RecordNotFoundError, BusinessLogicError
)


class TestMaterialsService:
    """Тесты для MaterialsService."""

    @pytest.fixture
    def mock_materials_repo(self):
        """Создает мок-репозиторий материалов."""
        return Mock(spec=MaterialsRepository)

    @pytest.fixture
    def materials_service(self, mock_materials_repo):
        """Создает экземпляр MaterialsService."""
        return MaterialsService(mock_materials_repo)

    @pytest.fixture
    def valid_material_data(self):
        """Возвращает валидные данные материала."""
        return {
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
            'needs_lab': 1,
            'otk_remarks': 'Хорошее качество'
        }

    def test_create_material_success(self, materials_service, mock_materials_repo, valid_material_data):
        """Тест успешного создания материала."""
        mock_materials_repo.create_material.return_value = 123
        
        result = materials_service.create(valid_material_data)
        
        assert result == 123
        mock_materials_repo.create_material.assert_called_once_with(valid_material_data)

    def test_create_material_missing_required_fields(self, materials_service, valid_material_data):
        """Тест создания материала без обязательных полей."""
        # Удаляем обязательное поле
        del valid_material_data['arrival_date']
        
        with pytest.raises(RequiredFieldError) as exc_info:
            materials_service.create(valid_material_data)
        
        assert "arrival_date" in str(exc_info.value)

    def test_create_material_invalid_date_format(self, materials_service, valid_material_data):
        """Тест создания материала с неверным форматом даты."""
        valid_material_data['arrival_date'] = '01.01.2024'
        
        with pytest.raises(InvalidFormatError) as exc_info:
            materials_service.create(valid_material_data)
        
        assert "YYYY-MM-DD" in str(exc_info.value)

    def test_create_material_invalid_string_length(self, materials_service, valid_material_data):
        """Тест создания материала со слишком длинной строкой."""
        valid_material_data['order_num'] = 'X' * 100  # Превышает лимит в 50
        
        with pytest.raises(ValueOutOfRangeError) as exc_info:
            materials_service.create(valid_material_data)
        
        assert "order_num" in str(exc_info.value)

    def test_create_material_invalid_numeric_range(self, materials_service, valid_material_data):
        """Тест создания материала с неверным числовым диапазоном."""
        valid_material_data['volume_length_mm'] = -10  # Отрицательное значение
        
        with pytest.raises(ValueOutOfRangeError) as exc_info:
            materials_service.create(valid_material_data)
        
        assert "volume_length_mm" in str(exc_info.value)

    def test_update_material_success(self, materials_service, mock_materials_repo):
        """Тест успешного обновления материала."""
        mock_materials_repo.exists.return_value = True
        mock_materials_repo.update_material.return_value = True
        
        update_data = {'size': '20x200x2000', 'otk_remarks': 'Обновлено'}
        result = materials_service.update(123, update_data)
        
        assert result is True
        mock_materials_repo.exists.assert_called_once_with(123)
        mock_materials_repo.update_material.assert_called_once_with(123, update_data)

    def test_update_material_not_found(self, materials_service, mock_materials_repo):
        """Тест обновления несуществующего материала."""
        mock_materials_repo.exists.return_value = False
        
        with pytest.raises(RecordNotFoundError) as exc_info:
            materials_service.update(999, {'size': '20x200x2000'})
        
        assert "999" in str(exc_info.value)

    def test_get_all_materials(self, materials_service, mock_materials_repo):
        """Тест получения всех материалов."""
        expected_materials = [{'id': 1, 'supplier': 'Test'}, {'id': 2, 'supplier': 'Test2'}]
        mock_materials_repo.get_materials_with_relations.return_value = expected_materials
        
        result = materials_service.get_all_materials()
        
        assert result == expected_materials
        mock_materials_repo.get_materials_with_relations.assert_called_once_with(False)

    def test_get_all_materials_include_deleted(self, materials_service, mock_materials_repo):
        """Тест получения всех материалов включая удаленные."""
        expected_materials = [{'id': 1, 'supplier': 'Test', 'to_delete': 1}]
        mock_materials_repo.get_materials_with_relations.return_value = expected_materials
        
        result = materials_service.get_all_materials(include_deleted=True)
        
        assert result == expected_materials
        mock_materials_repo.get_materials_with_relations.assert_called_once_with(True)

    def test_get_material_by_id_success(self, materials_service, mock_materials_repo):
        """Тест получения материала по ID."""
        expected_material = {'id': 123, 'supplier': 'Test'}
        mock_materials_repo.get_by_id.return_value = expected_material
        
        result = materials_service.get_material_by_id(123)
        
        assert result == expected_material
        mock_materials_repo.get_by_id.assert_called_once_with(123)

    def test_get_material_by_id_not_found(self, materials_service, mock_materials_repo):
        """Тест получения несуществующего материала."""
        mock_materials_repo.get_by_id.return_value = None
        
        result = materials_service.get_material_by_id(999)
        
        assert result is None

    def test_mark_for_deletion_success(self, materials_service, mock_materials_repo):
        """Тест успешной пометки на удаление."""
        mock_materials_repo.exists.return_value = True
        mock_materials_repo.is_locked.return_value = (False, '')
        mock_materials_repo.mark_for_deletion.return_value = True
        
        result = materials_service.mark_for_deletion(123, 'admin')
        
        assert result is True
        mock_materials_repo.exists.assert_called_once_with(123)
        mock_materials_repo.is_locked.assert_called_once_with(123)
        mock_materials_repo.mark_for_deletion.assert_called_once_with(123)

    def test_mark_for_deletion_material_not_found(self, materials_service, mock_materials_repo):
        """Тест пометки на удаление несуществующего материала."""
        mock_materials_repo.exists.return_value = False
        
        with pytest.raises(RecordNotFoundError):
            materials_service.mark_for_deletion(999, 'admin')

    def test_mark_for_deletion_material_locked(self, materials_service, mock_materials_repo):
        """Тест пометки на удаление заблокированного материала."""
        mock_materials_repo.exists.return_value = True
        mock_materials_repo.is_locked.return_value = (True, 'other_user')
        
        with pytest.raises(BusinessLogicError) as exc_info:
            materials_service.mark_for_deletion(123, 'admin')
        
        assert "other_user" in str(exc_info.value)

    def test_mark_for_deletion_own_lock(self, materials_service, mock_materials_repo):
        """Тест пометки на удаление собственного заблокированного материала."""
        mock_materials_repo.exists.return_value = True
        mock_materials_repo.is_locked.return_value = (True, 'admin')
        mock_materials_repo.mark_for_deletion.return_value = True
        
        result = materials_service.mark_for_deletion(123, 'admin')
        
        assert result is True

    def test_unmark_for_deletion_success(self, materials_service, mock_materials_repo):
        """Тест снятия пометки удаления."""
        mock_materials_repo.exists.return_value = True
        mock_materials_repo.unmark_for_deletion.return_value = True
        
        result = materials_service.unmark_for_deletion(123, 'admin')
        
        assert result is True
        mock_materials_repo.exists.assert_called_once_with(123)
        mock_materials_repo.unmark_for_deletion.assert_called_once_with(123)

    def test_permanently_delete_success(self, materials_service, mock_materials_repo):
        """Тест физического удаления материала."""
        mock_materials_repo.get_by_id.return_value = {'id': 123, 'to_delete': 1}
        mock_materials_repo.permanently_delete_material.return_value = True
        
        result = materials_service.permanently_delete(123, 'admin')
        
        assert result is True
        mock_materials_repo.get_by_id.assert_called_once_with(123)
        mock_materials_repo.permanently_delete_material.assert_called_once_with(123)

    def test_permanently_delete_not_marked(self, materials_service, mock_materials_repo):
        """Тест физического удаления не помеченного материала."""
        mock_materials_repo.get_by_id.return_value = {'id': 123, 'to_delete': 0}
        
        with pytest.raises(BusinessLogicError) as exc_info:
            materials_service.permanently_delete(123, 'admin')
        
        assert "помечен на удаление" in str(exc_info.value)

    def test_acquire_material_lock_success(self, materials_service, mock_materials_repo):
        """Тест захвата блокировки материала."""
        mock_materials_repo.acquire_lock.return_value = True
        
        result = materials_service.acquire_material_lock(123, 'admin')
        
        assert result is True
        mock_materials_repo.acquire_lock.assert_called_once_with(123, 'admin')

    def test_acquire_material_lock_failed(self, materials_service, mock_materials_repo):
        """Тест неудачного захвата блокировки."""
        mock_materials_repo.acquire_lock.return_value = False
        
        result = materials_service.acquire_material_lock(123, 'admin')
        
        assert result is False

    def test_release_material_lock_success(self, materials_service, mock_materials_repo):
        """Тест освобождения блокировки материала."""
        mock_materials_repo.release_lock.return_value = True
        
        result = materials_service.release_material_lock(123, 'admin')
        
        assert result is True
        mock_materials_repo.release_lock.assert_called_once_with(123, 'admin')

    def test_get_material_lock_status(self, materials_service, mock_materials_repo):
        """Тест получения статуса блокировки."""
        mock_materials_repo.is_locked.return_value = (True, 'admin')
        
        is_locked, locked_by = materials_service.get_material_lock_status(123)
        
        assert is_locked is True
        assert locked_by == 'admin'
        mock_materials_repo.is_locked.assert_called_once_with(123)

    def test_search_materials_success(self, materials_service, mock_materials_repo):
        """Тест поиска материалов."""
        expected_results = [{'id': 1, 'supplier': 'Test'}]
        mock_materials_repo.search_materials.return_value = expected_results
        
        result = materials_service.search_materials('Test')
        
        assert result == expected_results
        mock_materials_repo.search_materials.assert_called_once_with('Test')

    def test_search_materials_short_query(self, materials_service, mock_materials_repo):
        """Тест поиска с коротким запросом."""
        with pytest.raises(ValidationError) as exc_info:
            materials_service.search_materials('X')
        
        assert "минимум 2 символа" in str(exc_info.value)

    def test_get_materials_by_supplier(self, materials_service, mock_materials_repo):
        """Тест получения материалов по поставщику."""
        expected_materials = [{'id': 1, 'supplier_id': 1}]
        mock_materials_repo.get_materials_by_supplier.return_value = expected_materials
        
        result = materials_service.get_materials_by_supplier(1)
        
        assert result == expected_materials
        mock_materials_repo.get_materials_by_supplier.assert_called_once_with(1)

    def test_get_materials_by_grade(self, materials_service, mock_materials_repo):
        """Тест получения материалов по марке."""
        expected_materials = [{'id': 1, 'grade_id': 1}]
        mock_materials_repo.get_materials_by_grade.return_value = expected_materials
        
        result = materials_service.get_materials_by_grade(1)
        
        assert result == expected_materials
        mock_materials_repo.get_materials_by_grade.assert_called_once_with(1)

    def test_get_materials_needing_lab_tests(self, materials_service, mock_materials_repo):
        """Тест получения материалов для лабораторных испытаний."""
        expected_materials = [{'id': 1, 'needs_lab': 1}]
        mock_materials_repo.get_materials_needing_lab_tests.return_value = expected_materials
        
        result = materials_service.get_materials_needing_lab_tests()
        
        assert result == expected_materials
        mock_materials_repo.get_materials_needing_lab_tests.assert_called_once()

    def test_get_materials_statistics(self, materials_service, mock_materials_repo):
        """Тест получения статистики материалов."""
        expected_stats = {
            'total_materials': 100,
            'deleted_materials': 5,
            'lab_needed': 10,
            'locked_materials': 2
        }
        mock_materials_repo.get_materials_statistics.return_value = expected_stats
        
        result = materials_service.get_materials_statistics()
        
        assert result == expected_stats
        mock_materials_repo.get_materials_statistics.assert_called_once()

    @patch('os.path.exists')
    def test_add_document_success(self, mock_exists, materials_service, mock_materials_repo):
        """Тест добавления документа."""
        mock_exists.return_value = True
        mock_materials_repo.exists.return_value = True
        mock_materials_repo.add_document.return_value = 456
        
        result = materials_service.add_document(123, 'certificate', '/path/to/file.pdf', 'admin')
        
        assert result == 456
        mock_materials_repo.exists.assert_called_once_with(123)
        mock_materials_repo.add_document.assert_called_once_with(123, 'certificate', '/path/to/file.pdf', 'admin')

    @patch('os.path.exists')
    def test_add_document_file_not_found(self, mock_exists, materials_service, mock_materials_repo):
        """Тест добавления несуществующего документа."""
        mock_exists.return_value = False
        mock_materials_repo.exists.return_value = True
        
        with pytest.raises(ValidationError) as exc_info:
            materials_service.add_document(123, 'certificate', '/path/to/missing.pdf', 'admin')
        
        assert "Файл не найден" in str(exc_info.value)

    def test_add_document_invalid_type(self, materials_service, mock_materials_repo):
        """Тест добавления документа с неверным типом."""
        mock_materials_repo.exists.return_value = True
        
        with patch('os.path.exists', return_value=True):
            with pytest.raises(ValidationError) as exc_info:
                materials_service.add_document(123, 'invalid_type', '/path/to/file.pdf', 'admin')
        
        assert "Недопустимый тип документа" in str(exc_info.value)

    def test_get_material_documents(self, materials_service, mock_materials_repo):
        """Тест получения документов материала."""
        expected_documents = [
            {'id': 1, 'doc_type': 'certificate', 'file_path': '/path/to/cert.pdf'},
            {'id': 2, 'doc_type': 'photo', 'file_path': '/path/to/photo.jpg'}
        ]
        mock_materials_repo.get_documents.return_value = expected_documents
        
        result = materials_service.get_material_documents(123)
        
        assert result == expected_documents
        mock_materials_repo.get_documents.assert_called_once_with(123) 
"""
Тесты для BaseService.
"""

import pytest
from typing import Dict, Any

from services.base import BaseService, ValidationError, NotFoundError, BusinessLogicError


@pytest.mark.unit
@pytest.mark.database
class TestBaseService:
    """Тесты для BaseService."""
    
    def test_create_valid_data(self, test_service):
        """Тест создания записи с валидными данными."""
        data = {'name': 'Test Service'}
        
        record_id = test_service.create(data)
        
        assert record_id is not None
        assert record_id > 0
    
    def test_create_missing_required_field(self, test_service):
        """Тест создания записи без обязательного поля."""
        data = {}  # Отсутствует обязательное поле 'name'
        
        # Теперь для одного поля выбрасывается RequiredFieldError
        from utils.exceptions import RequiredFieldError
        with pytest.raises(RequiredFieldError) as exc_info:
            test_service.create(data)
        
        assert "Отсутствует обязательное поле: name" in str(exc_info.value)
    
    def test_create_empty_required_field(self, test_service):
        """Тест создания записи с пустым обязательным полем."""
        data = {'name': ''}  # Пустое обязательное поле
        
        # Теперь для одного поля выбрасывается RequiredFieldError
        from utils.exceptions import RequiredFieldError
        with pytest.raises(RequiredFieldError) as exc_info:
            test_service.create(data)
        
        assert "Отсутствует обязательное поле: name" in str(exc_info.value)
    
    def test_create_invalid_data_type(self, test_service):
        """Тест создания записи с неверным типом данных."""
        data = {'name': 123}  # Должно быть строкой
        
        # Теперь выбрасывается InvalidFormatError
        from utils.exceptions import InvalidFormatError
        with pytest.raises(InvalidFormatError) as exc_info:
            test_service.create(data)
        
        assert "должно быть типа str" in str(exc_info.value)
    
    def test_create_string_too_long(self, test_service):
        """Тест создания записи со слишком длинной строкой."""
        data = {'name': 'x' * 101}  # Больше 100 символов
        
        # Теперь выбрасывается ValueOutOfRangeError
        from utils.exceptions import ValueOutOfRangeError
        with pytest.raises(ValueOutOfRangeError) as exc_info:
            test_service.create(data)
        
        assert "не может быть длиннее 100 символов" in str(exc_info.value)
    
    def test_get_by_id_existing(self, test_service):
        """Тест получения существующей записи."""
        data = {'name': 'Test Service'}
        record_id = test_service.create(data)
        
        result = test_service.get_by_id(record_id)
        
        assert result is not None
        assert result['id'] == record_id
        assert result['name'] == 'Test Service'
    
    def test_get_by_id_not_existing(self, test_service):
        """Тест получения несуществующей записи."""
        result = test_service.get_by_id(999)
        
        assert result is None
    
    def test_get_all_empty(self, test_service):
        """Тест получения всех записей из пустой таблицы."""
        result = test_service.get_all()
        
        assert result == []
    
    def test_get_all_with_records(self, test_service):
        """Тест получения всех записей."""
        # Создаем несколько записей
        test_service.create({'name': 'Service 1'})
        test_service.create({'name': 'Service 2'})
        test_service.create({'name': 'Service 3'})
        
        result = test_service.get_all()
        
        assert len(result) == 3
        assert all('name' in record for record in result)
    
    def test_update_existing_record(self, test_service):
        """Тест обновления существующей записи."""
        data = {'name': 'Original Name'}
        record_id = test_service.create(data)
        
        success = test_service.update(record_id, {'name': 'Updated Name'})
        
        assert success is True
        
        # Проверяем, что запись обновилась
        result = test_service.get_by_id(record_id)
        assert result['name'] == 'Updated Name'
    
    def test_update_invalid_data_type(self, test_service):
        """Тест обновления записи с неверным типом данных."""
        data = {'name': 'Test Service'}
        record_id = test_service.create(data)
        
        from utils.exceptions import InvalidFormatError
        with pytest.raises(InvalidFormatError) as exc_info:
            test_service.update(record_id, {'name': 123})
        
        assert "должно быть типа str" in str(exc_info.value)
    
    def test_update_string_too_long(self, test_service):
        """Тест обновления записи со слишком длинной строкой."""
        data = {'name': 'Test Service'}
        record_id = test_service.create(data)
        
        from utils.exceptions import ValueOutOfRangeError
        with pytest.raises(ValueOutOfRangeError) as exc_info:
            test_service.update(record_id, {'name': 'x' * 101})
        
        assert "не может быть длиннее 100 символов" in str(exc_info.value)
    
    def test_delete_existing_record(self, test_service):
        """Тест удаления существующей записи."""
        data = {'name': 'Test Service'}
        record_id = test_service.create(data)
        
        success = test_service.delete_by_id(record_id)
        
        assert success is True
        
        # Проверяем, что запись удалена
        result = test_service.get_by_id(record_id)
        assert result is None
    
    def test_delete_non_existing_record(self, test_service):
        """Тест удаления несуществующей записи."""
        with pytest.raises(NotFoundError) as exc_info:
            test_service.delete_by_id(999)
        
        assert "Запись с ID 999 не найдена" in str(exc_info.value)
    
    def test_soft_delete_existing_record(self, test_service):
        """Тест мягкого удаления существующей записи."""
        data = {'name': 'Test Service'}
        record_id = test_service.create(data)
        
        success = test_service.soft_delete_by_id(record_id)
        
        assert success is True
        
        # Проверяем, что запись помечена как удаленная
        result = test_service.get_by_id(record_id)
        assert result is not None
        assert result['to_delete'] == 1
    
    def test_soft_delete_non_existing_record(self, test_service):
        """Тест мягкого удаления несуществующей записи."""
        with pytest.raises(NotFoundError) as exc_info:
            test_service.soft_delete_by_id(999)
        
        assert "Запись с ID 999 не найдена" in str(exc_info.value)
    
    def test_restore_existing_record(self, test_service):
        """Тест восстановления существующей записи."""
        data = {'name': 'Test Service'}
        record_id = test_service.create(data)
        
        # Сначала помечаем на удаление
        test_service.soft_delete_by_id(record_id)
        
        # Затем восстанавливаем
        success = test_service.restore_by_id(record_id)
        
        assert success is True
        
        # Проверяем, что запись восстановлена
        result = test_service.get_by_id(record_id)
        assert result is not None
        assert result['to_delete'] == 0
    
    def test_restore_non_existing_record(self, test_service):
        """Тест восстановления несуществующей записи."""
        with pytest.raises(NotFoundError) as exc_info:
            test_service.restore_by_id(999)
        
        assert "Запись с ID 999 не найдена" in str(exc_info.value)
    
    def test_count_empty_table(self, test_service):
        """Тест подсчета записей в пустой таблице."""
        count = test_service.count()
        
        assert count == 0
    
    def test_count_with_records(self, test_service):
        """Тест подсчета записей."""
        # Создаем несколько записей
        test_service.create({'name': 'Service 1'})
        test_service.create({'name': 'Service 2'})
        test_service.create({'name': 'Service 3'})
        
        count = test_service.count()
        
        assert count == 3
    
    def test_validate_required_fields_valid(self, test_service):
        """Тест валидации обязательных полей - валидные данные."""
        data = {'name': 'Test', 'description': 'Test description'}
        
        # Не должно выбрасывать исключение
        test_service.validate_required_fields(data, ['name', 'description'])
    
    def test_validate_required_fields_missing(self, test_service):
        """Тест валидации обязательных полей - отсутствующие поля."""
        data = {'name': 'Test'}
        
        # Для одного отсутствующего поля выбрасывается RequiredFieldError
        from utils.exceptions import RequiredFieldError
        with pytest.raises(RequiredFieldError) as exc_info:
            test_service.validate_required_fields(data, ['name', 'description'])
        
        assert "Отсутствует обязательное поле: description" in str(exc_info.value)
    
    def test_validate_data_types_valid(self, test_service):
        """Тест валидации типов данных - валидные данные."""
        data = {'name': 'Test', 'age': 25}
        
        # Не должно выбрасывать исключение
        test_service.validate_data_types(data, {'name': str, 'age': int})
    
    def test_validate_data_types_invalid(self, test_service):
        """Тест валидации типов данных - неверные типы."""
        data = {'name': 123}
        
        from utils.exceptions import InvalidFormatError
        with pytest.raises(InvalidFormatError) as exc_info:
            test_service.validate_data_types(data, {'name': str})
        
        assert "должно быть типа str" in str(exc_info.value)
    
    def test_validate_string_length_valid(self, test_service):
        """Тест валидации длины строк - валидные данные."""
        data = {'name': 'Test', 'description': 'Short'}
        
        # Не должно выбрасывать исключение
        test_service.validate_string_length(data, {'name': 10, 'description': 20})
    
    def test_validate_string_length_too_long(self, test_service):
        """Тест валидации длины строк - слишком длинные строки."""
        data = {'name': 'Very long test name'}
        
        from utils.exceptions import ValueOutOfRangeError
        with pytest.raises(ValueOutOfRangeError) as exc_info:
            test_service.validate_string_length(data, {'name': 5})
        
        assert "не может быть длиннее 5 символов" in str(exc_info.value)
    
    def test_validate_numeric_range_valid(self, test_service):
        """Тест валидации числовых диапазонов - валидные данные."""
        data = {'age': 25, 'score': 85.5}
        
        # Не должно выбрасывать исключение
        test_service.validate_numeric_range(data, {'age': (18, 65), 'score': (0.0, 100.0)})
    
    def test_validate_numeric_range_out_of_range(self, test_service):
        """Тест валидации числовых диапазонов - значения вне диапазона."""
        data = {'age': 150}
        
        from utils.exceptions import ValueOutOfRangeError
        with pytest.raises(ValueOutOfRangeError) as exc_info:
            test_service.validate_numeric_range(data, {'age': (18, 65)})
        
        assert "должно быть в диапазоне от 18 до 65" in str(exc_info.value)
    
    def test_validate_date_format_valid(self, test_service):
        """Тест валидации формата даты - валидные данные."""
        data = {'birth_date': '1990-01-01', 'registration_date': '2024-01-15'}
        
        # Не должно выбрасывать исключение
        test_service.validate_date_format(data, ['birth_date', 'registration_date'])
    
    def test_validate_date_format_invalid(self, test_service):
        """Тест валидации формата даты - неверный формат."""
        data = {'birth_date': '01/01/1990'}
        
        from utils.exceptions import InvalidFormatError
        with pytest.raises(InvalidFormatError) as exc_info:
            test_service.validate_date_format(data, ['birth_date'])
        
        assert "должно быть в формате YYYY-MM-DD" in str(exc_info.value) 
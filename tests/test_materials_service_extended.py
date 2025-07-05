"""
Дополнительные тесты для новых методов MaterialsService.
Тестирует функциональность расчета веса, кеширования и валидации.
"""

import pytest
import math
from unittest.mock import Mock, patch, MagicMock
from services.materials_service import MaterialsService
from repositories.materials_repository import MaterialsRepository
from utils.exceptions import ValidationError, RecordNotFoundError


class TestMaterialsServiceExtended:
    """Тесты для расширенной функциональности MaterialsService."""
    
    def setup_method(self):
        """Настройка для каждого теста."""
        self.mock_repo = Mock(spec=MaterialsRepository)
        self.service = MaterialsService(self.mock_repo)
    
    # === Тесты кеширования справочников ===
    
    def test_get_suppliers_with_caching(self):
        """Тест получения поставщиков с кешированием."""
        # Настраиваем mock
        self.mock_repo.execute_query.return_value = [
            (1, 'Поставщик 1'),
            (2, 'Поставщик 2')
        ]
        
        # Первый вызов
        suppliers1 = self.service.get_suppliers()
        assert len(suppliers1) == 2
        assert suppliers1[0] == {'id': 1, 'name': 'Поставщик 1'}
        assert suppliers1[1] == {'id': 2, 'name': 'Поставщик 2'}
        
        # Второй вызов - должен использовать кеш
        suppliers2 = self.service.get_suppliers()
        assert suppliers1 == suppliers2
        
        # Проверяем, что запрос к БД был только один раз
        self.mock_repo.execute_query.assert_called_once()
    
    def test_get_grades_with_caching(self):
        """Тест получения марок с кешированием."""
        self.mock_repo.execute_query.return_value = [
            (1, 'Ст3', 7.85),
            (2, '40Х', 7.85)
        ]
        
        grades = self.service.get_grades()
        assert len(grades) == 2
        assert grades[0] == {'id': 1, 'grade': 'Ст3', 'density': 7.85}
        assert grades[1] == {'id': 2, 'grade': '40Х', 'density': 7.85}
    
    def test_get_rolling_types_with_caching(self):
        """Тест получения видов проката с кешированием."""
        # Настраиваем mock для PRAGMA запроса
        self.mock_repo.execute_query.side_effect = [
            [(0, 'id', 'INTEGER', 0, None, 1), (1, 'type', 'TEXT', 0, None, 0)],  # PRAGMA результат
            [(1, 'Круг'), (2, 'Лист')]  # Данные видов проката
        ]
        
        rolling_types = self.service.get_rolling_types()
        assert len(rolling_types) == 2
        assert rolling_types[0] == {'id': 1, 'name': 'Круг'}
        assert rolling_types[1] == {'id': 2, 'name': 'Лист'}
    
    def test_get_custom_orders_empty_table(self):
        """Тест получения пользовательских заказов при отсутствии таблицы."""
        # Имитируем отсутствие таблицы
        self.mock_repo.execute_query.side_effect = Exception("no such table: CustomOrders")
        
        orders = self.service.get_custom_orders()
        assert orders == []
    
    def test_clear_cache(self):
        """Тест очистки кеша."""
        # Заполняем кеш
        self.mock_repo.execute_query.return_value = [(1, 'Поставщик 1')]
        self.service.get_suppliers()
        
        # Очищаем кеш
        self.service.clear_cache()
        
        # Проверяем, что после очистки кеша делается новый запрос
        self.service.get_suppliers()
        assert self.mock_repo.execute_query.call_count == 2
    
    # === Тесты расчета веса ===
    
    def test_calculate_cross_section_area_circle(self):
        """Тест расчета площади сечения для круга."""
        # Диаметр 100 мм = 0.1 м, радиус 0.05 м
        area = self.service.calculate_cross_section_area('Круг', 100, 0)
        expected = math.pi * (0.05) ** 2
        assert abs(area - expected) < 1e-6
    
    def test_calculate_cross_section_area_rectangle(self):
        """Тест расчета площади сечения для листа."""
        # 10 x 20 мм = 0.01 x 0.02 м
        area = self.service.calculate_cross_section_area('Лист', 10, 20)
        expected = 0.01 * 0.02
        assert abs(area - expected) < 1e-6
    
    def test_calculate_cross_section_area_tube(self):
        """Тест расчета площади сечения для трубы."""
        # Диаметр 100 мм, толщина стенки 5 мм
        area = self.service.calculate_cross_section_area('Труба', 100, 5)
        outer_radius = 0.05  # 50 мм
        inner_radius = 0.045  # 45 мм
        expected = math.pi * (outer_radius ** 2 - inner_radius ** 2)
        assert abs(area - expected) < 1e-6
    
    def test_calculate_cross_section_area_hexagon(self):
        """Тест расчета площади сечения для шестигранника."""
        # Сторона 10 мм = 0.01 м
        area = self.service.calculate_cross_section_area('Шестигранник', 10, 0)
        expected = 3 * math.sqrt(3) / 2 * (0.01 ** 2)
        assert abs(area - expected) < 1e-6
    
    def test_calculate_cross_section_area_unknown_type(self):
        """Тест ошибки для неизвестного типа проката."""
        with pytest.raises(ValidationError) as excinfo:
            self.service.calculate_cross_section_area('Неизвестный', 100, 0)
        assert "Неизвестный тип проката" in str(excinfo.value)
    
    def test_calculate_material_weight_success(self):
        """Тест успешного расчета веса материала."""
        # Настраиваем mock для получения марки
        self.mock_repo.execute_query.return_value = [(1, 'Ст3', 7.85)]
        
        volume_data = [
            {'length': 1000, 'count': 2},  # 2 м
            {'length': 500, 'count': 1}    # 0.5 м
        ]
        
        # Расчет для круга диаметром 100 мм (площадь π * 0.05² = π * 0.0025)
        total_length_mm, total_weight_kg = self.service.calculate_material_weight(
            1, 'Круг', (100, 0), volume_data
        )
        
        assert total_length_mm == 2500  # 2000 + 500
        # Вес = площадь * длина * плотность = π * 0.0025 * 2.5 * 7.85
        expected_weight = math.pi * 0.0025 * 2.5 * 7.85
        assert abs(total_weight_kg - expected_weight) < 1
    
    def test_calculate_material_weight_grade_not_found(self):
        """Тест ошибки при отсутствии марки."""
        self.mock_repo.execute_query.return_value = []
        
        with pytest.raises(RecordNotFoundError) as excinfo:
            self.service.calculate_material_weight(999, 'Круг', (100, 0), [])
        assert "Марка с ID 999 не найдена" in str(excinfo.value)
    
    def test_process_volume_data(self):
        """Тест обработки данных объема."""
        volume_data = [
            {'length': 1000, 'count': 2},
            {'length': 500, 'count': 3}
        ]
        
        result = self.service.process_volume_data(volume_data)
        
        assert result['total_length_mm'] == 3500  # 2000 + 1500
        assert result['total_length_m'] == 3.5
        assert result['display_text'] == "3500 мм (3.50 м)"
        assert result['info_text'] == "Общая длина: 3.50 м"
        assert result['pieces_count'] == 2
        assert result['total_pieces'] == 5
    
    # === Тесты валидации ===
    
    def test_validate_order_number_success(self):
        """Тест успешной валидации номера заказа."""
        assert self.service.validate_order_number('2025/003') == True
        assert self.service.validate_order_number('1/1') == True
        assert self.service.validate_order_number('9999/999') == True
    
    def test_validate_order_number_invalid_format(self):
        """Тест ошибки валидации номера заказа."""
        with pytest.raises(ValidationError) as excinfo:
            self.service.validate_order_number('invalid')
        assert "Неверный формат номера заказа" in str(excinfo.value)
        
        with pytest.raises(ValidationError):
            self.service.validate_order_number('2025')
        
        with pytest.raises(ValidationError):
            self.service.validate_order_number('2025/abc')
    
    def test_format_order_number(self):
        """Тест форматирования номера заказа."""
        assert self.service.format_order_number('2025003') == '2025/003'
        assert self.service.format_order_number('1234567') == '1234/567'
        assert self.service.format_order_number('123') == '123'
        assert self.service.format_order_number('') == ''
        assert self.service.format_order_number('abc123def456') == '1234/56'  # 7 цифр максимум
    
    def test_validate_material_form_data_success(self):
        """Тест успешной валидации данных формы."""
        form_data = {
            'supplier_id': 1,
            'order_num': '2025/003',
            'is_custom_order': False,
            'rolling_type': 'Круг',
            'dim1': 100,
            'dim2': 0
        }
        
        # Не должно вызвать исключение
        self.service.validate_material_form_data(form_data)
    
    def test_validate_material_form_data_no_supplier(self):
        """Тест ошибки при отсутствии поставщика."""
        form_data = {
            'supplier_id': None,
            'order_num': '2025/003',
            'is_custom_order': False,
            'rolling_type': 'Круг',
            'dim1': 100,
            'dim2': 0
        }
        
        with pytest.raises(ValidationError) as excinfo:
            self.service.validate_material_form_data(form_data)
        assert "Необходимо выбрать поставщика" in str(excinfo.value)
    
    def test_validate_material_form_data_invalid_order_format(self):
        """Тест ошибки при неверном формате заказа."""
        form_data = {
            'supplier_id': 1,
            'order_num': 'invalid',
            'is_custom_order': False,
            'rolling_type': 'Круг',
            'dim1': 100,
            'dim2': 0
        }
        
        with pytest.raises(ValidationError) as excinfo:
            self.service.validate_material_form_data(form_data)
        assert "Неверный формат номера заказа" in str(excinfo.value)
    
    def test_validate_material_form_data_missing_dimensions(self):
        """Тест ошибки при отсутствии размеров."""
        form_data = {
            'supplier_id': 1,
            'order_num': '2025/003',
            'is_custom_order': False,
            'rolling_type': 'Круг',
            'dim1': 0,
            'dim2': 0
        }
        
        with pytest.raises(ValidationError) as excinfo:
            self.service.validate_material_form_data(form_data)
        assert "необходимо указать размер" in str(excinfo.value)
    
    def test_validate_material_form_data_missing_both_dimensions(self):
        """Тест ошибки при отсутствии обоих размеров для листа."""
        form_data = {
            'supplier_id': 1,
            'order_num': '2025/003',
            'is_custom_order': False,
            'rolling_type': 'Лист',
            'dim1': 10,
            'dim2': 0
        }
        
        with pytest.raises(ValidationError) as excinfo:
            self.service.validate_material_form_data(form_data)
        assert "необходимо указать оба размера" in str(excinfo.value)
    
    # === Тесты форматирования ===
    
    def test_format_materials_for_display(self):
        """Тест форматирования материалов для отображения."""
        materials = [
            {
                'id': 1,
                'arrival_date': '2025-01-15',
                'cert_date': '2025-01-10',
                'volume_length_mm': 1000,
                'volume_weight_kg': 62,
                'needs_lab': 1,
                'otk_remarks': 'Замечания ОТК'
            }
        ]
        
        formatted = self.service.format_materials_for_display(materials)
        
        assert len(formatted) == 1
        material = formatted[0]
        assert material['arrival_date_display'] == '15.01.2025'
        assert material['cert_date_display'] == '10.01.2025'
        assert material['volume_length_display'] == '1000'
        assert material['volume_weight_display'] == '62'
        assert material['needs_lab_display'] == 'Да'
        assert material['otk_remarks_display'] == 'Замечания ОТК'
    
    def test_search_materials_with_formatting(self):
        """Тест поиска материалов с форматированием."""
        # Настраиваем mock для поиска
        self.mock_repo.search_materials.return_value = [
            {
                'id': 1,
                'arrival_date': '2025-01-15',
                'cert_date': '2025-01-10',
                'volume_length_mm': 1000,
                'volume_weight_kg': 62,
                'needs_lab': 0,
                'otk_remarks': None
            }
        ]
        
        with patch.object(self.service, 'search_materials', return_value=self.mock_repo.search_materials.return_value):
            results = self.service.search_materials_with_formatting('test')
            
            assert len(results) == 1
            assert results[0]['arrival_date_display'] == '15.01.2025'
            assert results[0]['needs_lab_display'] == ''
            assert results[0]['otk_remarks_display'] == '' 
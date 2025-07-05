"""
Тесты для системы шаблонов протоколов лаборатории.

Проверяет функциональность:
- Создания и управления шаблонами
- Генерации протоколов
- Работы с переменными и формулами
- Валидации и обработки ошибок
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from services.protocol_template_service import ProtocolTemplateService
from utils.exceptions import ValidationError, BusinessLogicError


class TestProtocolTemplateService:
    """Тесты сервиса шаблонов протоколов."""
    
    @pytest.fixture
    def mock_db_connection(self):
        """Мок подключения к базе данных."""
        conn = Mock()
        cursor = Mock()
        conn.cursor.return_value = cursor
        return conn
    
    @pytest.fixture
    def template_service(self, mock_db_connection):
        """Сервис для тестирования."""
        return ProtocolTemplateService(mock_db_connection)
    
    @pytest.fixture
    def sample_template_data(self):
        """Пример данных шаблона для тестирования."""
        return {
            'name': 'Тестовый шаблон',
            'description': 'Описание тестового шаблона',
            'category': 'mechanical',
            'template_content': '''# Протокол испытаний
**Заявка:** {{ request_number }}
**Материал:** {{ material_grade }}
**Результат:** {{ test_results[0].result }}''',
            'variables': ['request_number', 'material_grade', 'test_results'],
            'formulas': [{
                'name': 'test_formula',
                'formula': 'value * 2',
                'description': 'Тестовая формула'
            }],
            'output_format': 'pdf',
            'version': 1,
            'is_active': True,
            'is_default': False,
            'created_by': 'test_user',
            'created_at': '2024-01-01T00:00:00',
            'updated_by': None,
            'updated_at': None
        }
    
    @pytest.fixture
    def sample_context_data(self):
        """Пример данных контекста для генерации."""
        return {
            'request_number': 'ЛР-2024-001',
            'material_grade': 'Ст3сп',
            'test_results': [
                {'name': 'Предел прочности', 'result': '450 МПа'},
                {'name': 'Предел текучести', 'result': '300 МПа'}
            ],
            'value': 100
        }
    
    def test_jinja_environment_setup(self, template_service):
        """Тест настройки окружения Jinja2."""
        env = template_service.jinja_env
        
        # Проверяем наличие пользовательских фильтров
        assert 'format_date' in env.filters
        assert 'format_number' in env.filters
        assert 'safe_divide' in env.filters
        assert 'calculate' in env.filters
        assert 'format_result' in env.filters
        
        # Проверяем глобальные функции
        assert 'now' in env.globals
        assert 'today' in env.globals
        assert 'calculate_formula' in env.globals
    
    def test_format_date_filter(self, template_service):
        """Тест фильтра форматирования дат."""
        # Строка даты
        result = template_service._format_date_filter('2024-01-15')
        assert result == '15.01.2024'
        
        # Пустое значение
        result = template_service._format_date_filter('')
        assert result == ''
        
        # Неверный формат
        result = template_service._format_date_filter('invalid')
        assert result == 'invalid'
    
    def test_format_number_filter(self, template_service):
        """Тест фильтра форматирования чисел."""
        # Целое число
        result = template_service._format_number_filter(123)
        assert result == '123.00'
        
        # Число с плавающей точкой
        result = template_service._format_number_filter(123.456, 1)
        assert result == '123.5'
        
        # Строка
        result = template_service._format_number_filter('не число')
        assert result == 'не число'
    
    def test_safe_divide_filter(self, template_service):
        """Тест безопасного деления."""
        # Обычное деление
        result = template_service._safe_divide_filter(10, 2)
        assert result == 5.0
        
        # Деление на ноль
        result = template_service._safe_divide_filter(10, 0, default=99)
        assert result == 99
        
        # Неверные типы
        result = template_service._safe_divide_filter('a', 'b', default=0)
        assert result == 0
    
    def test_calculate_formula_basic(self, template_service):
        """Тест базового расчета формул."""
        variables = {'x': 10, 'y': 5}
        
        # Простые арифметические операции
        result = template_service._calculate_formula('x + y', variables)
        assert result == 15
        
        result = template_service._calculate_formula('x * y', variables)
        assert result == 50
        
        # Использование математических функций
        result = template_service._calculate_formula('abs(-10)', variables)
        assert result == 10
        
        result = template_service._calculate_formula('round(3.14159, 2)', variables)
        assert result == 3.14
    
    def test_calculate_formula_advanced(self, template_service):
        """Тест продвинутых расчетов."""
        variables = {'length': 100, 'width': 50, 'pi': 3.14159}
        
        # Сложная формула
        result = template_service._calculate_formula('length * width / 2', variables)
        assert result == 2500.0
        
        # С использованием pi
        result = template_service._calculate_formula('pi * 2', variables)
        assert result == pytest.approx(6.28318, rel=1e-5)
    
    def test_calculate_formula_security(self, template_service):
        """Тест безопасности формул."""
        variables = {'x': 10}
        
        # Попытка использования запрещенных функций
        result = template_service._calculate_formula('import os', variables)
        assert result == 0  # Должно вернуть 0 при ошибке
        
        result = template_service._calculate_formula('__import__("os")', variables)
        assert result == 0
        
        result = template_service._calculate_formula('exec("print(123)")', variables)
        assert result == 0
    
    def test_is_safe_formula(self, template_service):
        """Тест проверки безопасности формул."""
        # Безопасные формулы
        assert template_service._is_safe_formula('x + y * 2')
        assert template_service._is_safe_formula('abs(value)')
        assert template_service._is_safe_formula('round(pi * r * r, 2)')
        
        # Небезопасные формулы
        assert not template_service._is_safe_formula('import os')
        assert not template_service._is_safe_formula('exec("code")')
        assert not template_service._is_safe_formula('eval("expression")')
        assert not template_service._is_safe_formula('open("file.txt")')
        assert not template_service._is_safe_formula('__import__("module")')
    
    def test_get_all_templates(self, template_service, mock_db_connection):
        """Тест получения всех шаблонов."""
        # Настраиваем мок
        cursor = mock_db_connection.cursor.return_value
        cursor.fetchall.return_value = [
            {
                'id': 1, 'name': 'Шаблон 1', 'description': 'Описание 1',
                'category': 'mechanical', 'output_format': 'pdf',
                'created_by': 'user1', 'created_at': '2024-01-01',
                'updated_at': None, 'version': 1, 'is_active': 1, 'is_default': 0
            },
            {
                'id': 2, 'name': 'Шаблон 2', 'description': 'Описание 2',
                'category': 'chemical', 'output_format': 'html',
                'created_by': 'user2', 'created_at': '2024-01-02',
                'updated_at': None, 'version': 1, 'is_active': 1, 'is_default': 1
            }
        ]
        
        # Выполняем тест
        templates = template_service.get_all_templates()
        
        # Проверяем результат
        assert len(templates) == 2
        assert templates[0]['name'] == 'Шаблон 1'
        assert templates[1]['name'] == 'Шаблон 2'
        assert templates[1]['is_default'] == True
        
        # Проверяем вызов SQL
        cursor.execute.assert_called_once()
        sql_query = cursor.execute.call_args[0][0]
        assert 'SELECT' in sql_query
        assert 'protocol_templates' in sql_query
    
    def test_get_all_templates_with_filters(self, template_service, mock_db_connection):
        """Тест получения шаблонов с фильтрами."""
        cursor = mock_db_connection.cursor.return_value
        cursor.fetchall.return_value = []
        
        # Тест с фильтром по категории
        template_service.get_all_templates(category='mechanical')
        
        cursor.execute.assert_called_once()
        sql_query, params = cursor.execute.call_args[0]
        assert 'category = ?' in sql_query
        assert 'mechanical' in params
        
        # Сброс мока
        cursor.reset_mock()
        
        # Тест с фильтром активности
        template_service.get_all_templates(active_only=False)
        
        cursor.execute.assert_called_once()
        sql_query, params = cursor.execute.call_args[0]
        assert 'is_active = ?' not in sql_query
    
    def test_get_template_by_id(self, template_service, mock_db_connection):
        """Тест получения шаблона по ID."""
        cursor = mock_db_connection.cursor.return_value
        cursor.fetchone.return_value = {
            'id': 1, 'name': 'Тестовый шаблон',
            'description': 'Описание', 'category': 'mechanical',
            'template_content': '# Заголовок\n{{ variable }}',
            'variables_json': '["variable"]',
            'formulas_json': '[]',
            'output_format': 'pdf', 'created_by': 'user',
            'created_at': '2024-01-01', 'updated_by': None,
            'updated_at': None, 'version': 1,
            'is_active': 1, 'is_default': 0
        }
        
        template = template_service.get_template_by_id(1)
        
        assert template is not None
        assert template['id'] == 1
        assert template['name'] == 'Тестовый шаблон'
        assert template['variables'] == ['variable']
        assert template['formulas'] == []
        assert template['is_active'] == True
        
        cursor.execute.assert_called_once_with(
            "SELECT * FROM protocol_templates WHERE id = ?", (1,)
        )
    
    def test_get_template_by_id_not_found(self, template_service, mock_db_connection):
        """Тест получения несуществующего шаблона."""
        cursor = mock_db_connection.cursor.return_value
        cursor.fetchone.return_value = None
        
        template = template_service.get_template_by_id(999)
        
        assert template is None
    
    def test_create_template(self, template_service, mock_db_connection, sample_template_data):
        """Тест создания нового шаблона."""
        cursor = mock_db_connection.cursor.return_value
        cursor.lastrowid = 123
        
        # Мок для проверки уникальности имени
        cursor.fetchone.return_value = None
        
        template_id = template_service.create_template(sample_template_data, 'test_user')
        
        assert template_id == 123
        
        # Проверяем вызов INSERT
        cursor.execute.assert_called()
        sql_query = cursor.execute.call_args_list[-1][0][0]
        assert 'INSERT INTO protocol_templates' in sql_query
        
        # Проверяем commit
        mock_db_connection.commit.assert_called_once()
    
    def test_create_template_validation_error(self, template_service, sample_template_data):
        """Тест ошибки валидации при создании шаблона."""
        # Удаляем обязательное поле
        del sample_template_data['name']
        
        with pytest.raises(ValidationError) as excinfo:
            template_service.create_template(sample_template_data, 'test_user')
        
        assert "обязательно для заполнения" in str(excinfo.value)
    
    def test_create_template_duplicate_name(self, template_service, mock_db_connection, sample_template_data):
        """Тест создания шаблона с дублирующимся именем."""
        cursor = mock_db_connection.cursor.return_value
        cursor.fetchone.return_value = {'id': 1}  # Имитируем существующий шаблон
        
        with pytest.raises(ValidationError) as excinfo:
            template_service.create_template(sample_template_data, 'test_user')
        
        assert "уже существует" in str(excinfo.value)
    
    def test_update_template(self, template_service, mock_db_connection, sample_template_data):
        """Тест обновления шаблона."""
        cursor = mock_db_connection.cursor.return_value
        cursor.rowcount = 1
        
        # Мок для get_template_by_id (текущий шаблон)
        with patch.object(template_service, 'get_template_by_id') as mock_get:
            mock_get.return_value = sample_template_data
            
            # Мок для проверки уникальности имени
            cursor.fetchone.return_value = None
            
            result = template_service.update_template(1, sample_template_data, 'test_user')
            
            assert result == True
            
            # Проверяем вызов UPDATE
            cursor.execute.assert_called()
            sql_query = cursor.execute.call_args_list[-1][0][0]
            assert 'UPDATE protocol_templates' in sql_query
            
            mock_db_connection.commit.assert_called_once()
    
    def test_delete_template(self, template_service, mock_db_connection):
        """Тест удаления шаблона."""
        cursor = mock_db_connection.cursor.return_value
        cursor.rowcount = 1
        
        result = template_service.delete_template(1, 'test_user')
        
        assert result == True
        
        # Проверяем мягкое удаление
        cursor.execute.assert_called_once()
        sql_query = cursor.execute.call_args[0][0]
        assert 'UPDATE protocol_templates' in sql_query
        assert 'is_active = 0' in sql_query
        
        mock_db_connection.commit.assert_called_once()
    
    def test_generate_protocol(self, template_service, mock_db_connection, sample_template_data, sample_context_data):
        """Тест генерации протокола."""
        # Настраиваем мок для get_template_by_id
        with patch.object(template_service, 'get_template_by_id') as mock_get:
            mock_get.return_value = sample_template_data
            
            result = template_service.generate_protocol(1, sample_context_data)
            
            # Проверяем, что результат содержит подставленные значения
            assert 'ЛР-2024-001' in result
            assert 'Ст3сп' in result
            assert '450 МПа' in result
            assert '# Протокол испытаний' in result
    
    def test_generate_protocol_with_formulas(self, template_service, mock_db_connection, sample_context_data):
        """Тест генерации протокола с формулами."""
        template_data = {
            'name': 'Шаблон с формулами',
            'template_content': '''# Результат
Значение: {{ value }}
Удвоенное значение: {{ calculated_values[0].value }}''',
            'formulas': [{
                'name': 'doubled_value',
                'formula': 'value * 2',
                'description': 'Удвоенное значение'
            }],
            'version': 1
        }
        
        with patch.object(template_service, 'get_template_by_id') as mock_get:
            mock_get.return_value = template_data
            
            result = template_service.generate_protocol(1, sample_context_data, calculate_formulas=True)
            
            # Проверяем, что формула была вычислена
            assert '200' in result  # value * 2 = 100 * 2 = 200
    
    def test_generate_protocol_template_not_found(self, template_service, mock_db_connection):
        """Тест генерации протокола для несуществующего шаблона."""
        with patch.object(template_service, 'get_template_by_id') as mock_get:
            mock_get.return_value = None
            
            with pytest.raises(ValidationError) as excinfo:
                template_service.generate_protocol(999, {})
            
            assert "не найден" in str(excinfo.value)
    
    def test_get_template_variables(self, template_service, mock_db_connection):
        """Тест получения переменных шаблонов."""
        cursor = mock_db_connection.cursor.return_value
        cursor.fetchall.return_value = [
            {
                'name': 'request_number', 'display_name': 'Номер заявки',
                'data_type': 'text', 'default_value': '',
                'description': 'Номер лабораторной заявки',
                'category': 'system', 'is_system': 1
            },
            {
                'name': 'material_grade', 'display_name': 'Марка материала',
                'data_type': 'text', 'default_value': '',
                'description': 'Марка испытываемого материала',
                'category': 'material', 'is_system': 1
            }
        ]
        
        variables = template_service.get_template_variables()
        
        assert len(variables) == 2
        assert variables[0]['name'] == 'request_number'
        assert variables[0]['is_system'] == True
        assert variables[1]['category'] == 'material'
    
    def test_get_template_variables_with_category(self, template_service, mock_db_connection):
        """Тест получения переменных с фильтром по категории."""
        cursor = mock_db_connection.cursor.return_value
        cursor.fetchall.return_value = []
        
        template_service.get_template_variables(category='system')
        
        cursor.execute.assert_called_once()
        sql_query, params = cursor.execute.call_args[0]
        assert 'category = ?' in sql_query
        assert 'system' in params
    
    def test_preview_protocol(self, template_service):
        """Тест предварительного просмотра протокола."""
        template_content = '''# Протокол
Номер: {{ request_number }}
Материал: {{ material_grade }}'''
        
        context_data = {
            'request_number': 'ЛР-001',
            'material_grade': 'Ст3'
        }
        
        result, errors = template_service.preview_protocol(template_content, context_data)
        
        assert len(errors) == 0
        assert 'ЛР-001' in result
        assert 'Ст3' in result
    
    def test_preview_protocol_with_errors(self, template_service):
        """Тест предварительного просмотра с ошибками."""
        # Синтаксическая ошибка в шаблоне
        template_content = '''# Протокол
Номер: {{ request_number
Материал: {{ material_grade }}'''
        
        context_data = {'request_number': 'ЛР-001'}
        
        result, errors = template_service.preview_protocol(template_content, context_data)
        
        assert len(errors) > 0
        assert 'Синтаксическая ошибка' in errors[0]
    
    def test_preview_protocol_undefined_variable(self, template_service):
        """Тест предварительного просмотра с неопределенной переменной."""
        template_content = '''# Протокол
Номер: {{ request_number }}
Материал: {{ undefined_variable }}'''
        
        context_data = {'request_number': 'ЛР-001'}
        
        result, errors = template_service.preview_protocol(template_content, context_data)
        
        assert len(errors) > 0
        assert 'Неопределенная переменная' in errors[0]
    
    def test_prepare_context(self, template_service, sample_template_data, sample_context_data):
        """Тест подготовки контекста."""
        context = template_service._prepare_context(
            sample_template_data, sample_context_data, calculate_formulas=True
        )
        
        # Проверяем добавление системных переменных
        assert 'report_date' in context
        assert 'report_time' in context
        assert 'template_name' in context
        assert 'template_version' in context
        
        # Проверяем исходные данные
        assert context['request_number'] == 'ЛР-2024-001'
        assert context['material_grade'] == 'Ст3сп'
        
        # Проверяем расчетные значения
        assert 'calculated_values' in context
        assert len(context['calculated_values']) == 1
        assert context['calculated_values'][0]['value'] == 200  # value * 2
    
    def test_prepare_context_without_formulas(self, template_service, sample_template_data, sample_context_data):
        """Тест подготовки контекста без расчета формул."""
        context = template_service._prepare_context(
            sample_template_data, sample_context_data, calculate_formulas=False
        )
        
        # Проверяем, что расчетные значения не добавлены
        assert 'calculated_values' not in context
    
    def test_validate_template_syntax(self, template_service):
        """Тест валидации синтаксиса шаблона."""
        # Корректный шаблон
        template_service._validate_template_syntax('{{ variable }}')
        
        # Некорректный шаблон
        with pytest.raises(ValidationError) as excinfo:
            template_service._validate_template_syntax('{{ variable')
        
        assert "синтаксиса" in str(excinfo.value)
    
    def test_error_handling_in_generate_protocol(self, template_service, mock_db_connection):
        """Тест обработки ошибок в генерации протокола."""
        # Настраиваем мок для выброса исключения
        with patch.object(template_service, 'get_template_by_id') as mock_get:
            mock_get.side_effect = Exception("Database error")
            
            with pytest.raises(BusinessLogicError) as excinfo:
                template_service.generate_protocol(1, {})
            
            assert "Ошибка генерации протокола" in str(excinfo.value)
    
    def test_error_handling_in_get_all_templates(self, template_service, mock_db_connection):
        """Тест обработки ошибок в получении шаблонов."""
        cursor = mock_db_connection.cursor.return_value
        cursor.execute.side_effect = Exception("Database error")
        
        with pytest.raises(BusinessLogicError) as excinfo:
            template_service.get_all_templates()
        
        assert "Ошибка получения списка шаблонов" in str(excinfo.value)
    
    def test_rollback_on_create_template_error(self, template_service, mock_db_connection, sample_template_data):
        """Тест отката транзакции при ошибке создания шаблона."""
        cursor = mock_db_connection.cursor.return_value
        cursor.execute.side_effect = Exception("Database error")
        
        with pytest.raises(BusinessLogicError):
            template_service.create_template(sample_template_data, 'test_user')
        
        # Проверяем, что был вызван rollback
        mock_db_connection.rollback.assert_called_once()
    
    def test_rollback_on_update_template_error(self, template_service, mock_db_connection, sample_template_data):
        """Тест отката транзакции при ошибке обновления шаблона."""
        cursor = mock_db_connection.cursor.return_value
        cursor.execute.side_effect = Exception("Database error")
        
        with pytest.raises(BusinessLogicError):
            template_service.update_template(1, sample_template_data, 'test_user')
        
        # Проверяем, что был вызван rollback
        mock_db_connection.rollback.assert_called_once()


class TestTemplateIntegration:
    """Интеграционные тесты системы шаблонов."""
    
    def test_end_to_end_template_workflow(self, template_service, mock_db_connection):
        """Тест полного цикла работы с шаблоном."""
        # Подготовка данных
        template_data = {
            'name': 'Интеграционный тест',
            'description': 'Тест полного цикла',
            'category': 'test',
            'template_content': '''# Протокол {{ request_number }}
Материал: {{ material_grade }}
Результат: {{ test_results[0].result }}
Дата: {{ report_date }}''',
            'variables': ['request_number', 'material_grade', 'test_results'],
            'formulas': [],
            'output_format': 'pdf'
        }
        
        context_data = {
            'request_number': 'ЛР-2024-999',
            'material_grade': 'Сталь 09Г2С',
            'test_results': [
                {'name': 'Твердость', 'result': '180 HB'}
            ]
        }
        
        # Настраиваем моки
        cursor = mock_db_connection.cursor.return_value
        cursor.lastrowid = 100
        cursor.rowcount = 1
        cursor.fetchone.return_value = None  # Для проверки уникальности
        
        # 1. Создаем шаблон
        template_id = template_service.create_template(template_data, 'integration_test')
        assert template_id == 100
        
        # 2. Получаем шаблон
        cursor.fetchone.return_value = {
            'id': template_id, 'name': template_data['name'],
            'description': template_data['description'],
            'category': template_data['category'],
            'template_content': template_data['template_content'],
            'variables_json': json.dumps(template_data['variables']),
            'formulas_json': json.dumps(template_data['formulas']),
            'output_format': template_data['output_format'],
            'created_by': 'integration_test',
            'created_at': '2024-01-01',
            'updated_by': None, 'updated_at': None,
            'version': 1, 'is_active': 1, 'is_default': 0
        }
        
        retrieved_template = template_service.get_template_by_id(template_id)
        assert retrieved_template['name'] == template_data['name']
        
        # 3. Генерируем протокол
        protocol_content = template_service.generate_protocol(
            template_id, context_data, calculate_formulas=False
        )
        
        # Проверяем содержимое сгенерированного протокола
        assert 'ЛР-2024-999' in protocol_content
        assert 'Сталь 09Г2С' in protocol_content
        assert '180 HB' in protocol_content
        assert datetime.now().strftime('%d.%m.%Y') in protocol_content
        
        # 4. Обновляем шаблон
        template_data['description'] = 'Обновленное описание'
        success = template_service.update_template(template_id, template_data, 'integration_test')
        assert success == True
        
        # 5. Удаляем шаблон
        success = template_service.delete_template(template_id, 'integration_test')
        assert success == True
    
    def test_complex_template_with_formulas(self, template_service, mock_db_connection):
        """Тест сложного шаблона с формулами."""
        template_data = {
            'name': 'Сложный шаблон',
            'template_content': '''# Механические испытания
Образец: {{ specimen_id }}
Начальная длина: {{ initial_length }} мм
Конечная длина: {{ final_length }} мм
Относительное удлинение: {{ calculated_values[0].value }}%
Площадь поперечного сечения: {{ calculated_values[1].value }} мм²''',
            'formulas': [
                {
                    'name': 'relative_elongation',
                    'formula': '(final_length - initial_length) / initial_length * 100',
                    'description': 'Относительное удлинение'
                },
                {
                    'name': 'cross_section_area',
                    'formula': 'pi * (diameter / 2) ** 2',
                    'description': 'Площадь поперечного сечения'
                }
            ],
            'variables': ['specimen_id', 'initial_length', 'final_length', 'diameter'],
            'version': 1
        }
        
        context_data = {
            'specimen_id': 'SP-001',
            'initial_length': 100,
            'final_length': 120,
            'diameter': 10,
            'pi': 3.14159
        }
        
        # Настраиваем мок
        with patch.object(template_service, 'get_template_by_id') as mock_get:
            mock_get.return_value = template_data
            
            protocol_content = template_service.generate_protocol(
                1, context_data, calculate_formulas=True
            )
            
            # Проверяем результаты расчетов
            assert '20.0' in protocol_content  # (120-100)/100*100 = 20%
            assert '78.54' in protocol_content  # 3.14159 * (10/2)^2 ≈ 78.54 
"""
Тесты для сервиса статистического анализа.
"""

import pytest
import numpy as np
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
import json

from services.statistics_service import StatisticsService
from utils.exceptions import BusinessLogicError, ValidationError


class TestStatisticsService:
    """Тесты для StatisticsService."""

    @pytest.fixture
    def mock_db_connection(self):
        """Фикстура для mock соединения с БД."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        return mock_conn

    @pytest.fixture
    def statistics_service(self, mock_db_connection):
        """Фикстура для StatisticsService."""
        return StatisticsService(mock_db_connection)

    @pytest.fixture
    def sample_test_data(self):
        """Пример данных для тестирования."""
        return [
            {
                'request_id': 1,
                'request_number': 'REQ-001',
                'date': '2024-01-01',
                'value': 450.5,
                'material_grade': 'Ст20',
                'heat_num': 'A123',
                'original_value': '450.5 МПа'
            },
            {
                'request_id': 2,
                'request_number': 'REQ-002',
                'date': '2024-01-02',
                'value': 455.0,
                'material_grade': 'Ст20',
                'heat_num': 'A124',
                'original_value': '455.0 МПа'
            },
            {
                'request_id': 3,
                'request_number': 'REQ-003',
                'date': '2024-01-03',
                'value': 448.2,
                'material_grade': 'Ст20',
                'heat_num': 'A125',
                'original_value': '448.2 МПа'
            },
            {
                'request_id': 4,
                'request_number': 'REQ-004',
                'date': '2024-01-04',
                'value': 460.8,
                'material_grade': 'Ст20',
                'heat_num': 'A126',
                'original_value': '460.8 МПа'
            },
            {
                'request_id': 5,
                'request_number': 'REQ-005',
                'date': '2024-01-05',
                'value': 452.3,
                'material_grade': 'Ст20',
                'heat_num': 'A127',
                'original_value': '452.3 МПа'
            }
        ]

    def test_initialization(self, mock_db_connection):
        """Тест инициализации сервиса."""
        service = StatisticsService(mock_db_connection)
        assert service.db_connection == mock_db_connection
        assert hasattr(service, 'grubbs_critical_values')
        assert service.grubbs_critical_values[10] == 2.290

    def test_extract_numeric_value(self, statistics_service):
        """Тест извлечения числового значения из строки."""
        assert statistics_service._extract_numeric_value("450.5") == 450.5
        assert statistics_service._extract_numeric_value("450.5 МПа") == 450.5
        assert statistics_service._extract_numeric_value("Значение: 450.5") == 450.5
        assert statistics_service._extract_numeric_value("450") == 450.0
        assert statistics_service._extract_numeric_value("-450.5") == -450.5
        assert statistics_service._extract_numeric_value("1.5e-3") == 0.0015
        assert statistics_service._extract_numeric_value("") is None
        assert statistics_service._extract_numeric_value("нет данных") is None

    def test_get_test_results_data(self, statistics_service, mock_db_connection):
        """Тест получения данных результатов тестов."""
        # Мокируем результат запроса к БД
        mock_cursor = mock_db_connection.cursor.return_value
        mock_cursor.fetchall.return_value = [
            {
                'id': 1,
                'request_number': 'REQ-001',
                'creation_date': '2024-01-01',
                'results_json': json.dumps([
                    {'name': 'Предел прочности', 'result': '450.5 МПа'}
                ]),
                'material_grade': 'Ст20',
                'heat_num': 'A123'
            }
        ]

        result = statistics_service.get_test_results_data('Предел прочности', 'Ст20', 30)
        
        assert len(result) == 1
        assert result[0]['value'] == 450.5
        assert result[0]['material_grade'] == 'Ст20'
        assert result[0]['request_number'] == 'REQ-001'

    def test_calculate_basic_statistics(self, statistics_service):
        """Тест расчета основных статистик."""
        values = [450.5, 455.0, 448.2, 460.8, 452.3]
        stats = statistics_service.calculate_basic_statistics(values)
        
        assert stats['count'] == 5
        assert abs(stats['mean'] - 453.36) < 0.01
        assert abs(stats['median'] - 452.3) < 0.01
        assert abs(stats['std'] - 4.92) < 0.1
        assert stats['min'] == 448.2
        assert stats['max'] == 460.8
        assert abs(stats['range'] - 12.6) < 0.01
        assert stats['cv'] > 0  # Коэффициент вариации должен быть положительным

    def test_calculate_basic_statistics_empty(self, statistics_service):
        """Тест расчета статистик для пустого списка."""
        stats = statistics_service.calculate_basic_statistics([])
        assert stats == {}

    def test_detect_outliers_grubbs(self, statistics_service):
        """Тест определения выбросов по критерию Граббса."""
        # Данные с выбросом
        values = [450.5, 455.0, 448.2, 460.8, 452.3, 500.0]  # 500.0 - выброс
        
        result = statistics_service.detect_outliers_grubbs(values)
        
        assert 'outliers' in result
        assert 'test_statistic' in result
        assert 'critical_value' in result
        assert len(result['outliers']) >= 1  # Должен быть найден хотя бы один выброс
        assert result['test_statistic'] is not None
        assert result['critical_value'] is not None

    def test_detect_outliers_grubbs_no_outliers(self, statistics_service):
        """Тест определения выбросов для данных без выбросов."""
        values = [450.5, 455.0, 448.2, 460.8, 452.3]
        
        result = statistics_service.detect_outliers_grubbs(values)
        
        assert len(result['outliers']) == 0
        assert result['test_statistic'] is not None
        assert result['critical_value'] is not None

    def test_detect_outliers_grubbs_insufficient_data(self, statistics_service):
        """Тест определения выбросов для недостаточного количества данных."""
        values = [450.5, 455.0]
        
        result = statistics_service.detect_outliers_grubbs(values)
        
        assert len(result['outliers']) == 0
        assert result['test_statistic'] is None
        assert result['critical_value'] is None

    def test_get_grubbs_critical_value(self, statistics_service):
        """Тест получения критического значения Граббса."""
        # Проверяем табличные значения
        assert statistics_service._get_grubbs_critical_value(10) == 2.290
        assert statistics_service._get_grubbs_critical_value(20) == 2.709
        
        # Проверяем интерполяцию
        value_15 = statistics_service._get_grubbs_critical_value(15)
        assert 2.5 < value_15 < 2.6
        
        # Проверяем большие выборки
        value_150 = statistics_service._get_grubbs_critical_value(150)
        assert value_150 == statistics_service.grubbs_critical_values[100]

    def test_calculate_control_chart_limits_x_chart(self, statistics_service):
        """Тест расчета границ контрольной карты для индивидуальных значений."""
        values = [450.5, 455.0, 448.2, 460.8, 452.3]
        
        limits = statistics_service.calculate_control_chart_limits(values, 'X')
        
        assert 'center_line' in limits
        assert 'ucl' in limits
        assert 'lcl' in limits
        assert 'avg_moving_range' in limits
        
        # Проверяем, что границы корректны
        assert limits['ucl'] > limits['center_line']
        assert limits['lcl'] < limits['center_line']
        assert limits['avg_moving_range'] > 0

    def test_calculate_control_chart_limits_mr_chart(self, statistics_service):
        """Тест расчета границ контрольной карты для скользящих размахов."""
        values = [450.5, 455.0, 448.2, 460.8, 452.3]
        
        limits = statistics_service.calculate_control_chart_limits(values, 'MR')
        
        assert 'center_line' in limits
        assert 'ucl' in limits
        assert 'lcl' in limits
        
        # Проверяем, что границы корректны
        assert limits['ucl'] > limits['center_line']
        assert limits['lcl'] == 0  # Для карты размахов нижняя граница = 0

    def test_calculate_control_chart_limits_empty(self, statistics_service):
        """Тест расчета границ контрольной карты для пустых данных."""
        limits = statistics_service.calculate_control_chart_limits([], 'X')
        assert limits == {}

    def test_check_control_chart_rules(self, statistics_service):
        """Тест проверки правил контрольной карты."""
        values = [450.5, 455.0, 448.2, 460.8, 452.3]
        limits = {
            'center_line': 453.0,
            'ucl': 465.0,
            'lcl': 441.0
        }
        
        rules = statistics_service.check_control_chart_rules(values, limits)
        
        assert 'rule_1_violations' in rules
        assert 'rule_2_violations' in rules
        assert 'rule_3_violations' in rules
        assert 'rule_4_violations' in rules
        assert 'process_stable' in rules
        
        # Для нормальных данных процесс должен быть стабильным
        assert rules['process_stable'] is True

    def test_check_control_chart_rules_with_violations(self, statistics_service):
        """Тест проверки правил контрольной карты с нарушениями."""
        # Данные с точкой вне границ
        values = [450.5, 455.0, 448.2, 470.0, 452.3]  # 470.0 выше UCL
        limits = {
            'center_line': 453.0,
            'ucl': 465.0,
            'lcl': 441.0
        }
        
        rules = statistics_service.check_control_chart_rules(values, limits)
        
        assert len(rules['rule_1_violations']) > 0
        assert rules['process_stable'] is False

    def test_calculate_process_capability(self, statistics_service):
        """Тест расчета показателей воспроизводимости процесса."""
        values = [450.5, 455.0, 448.2, 460.8, 452.3]
        
        # Со спецификационными границами
        capability = statistics_service.calculate_process_capability(
            values, lower_spec=440.0, upper_spec=470.0
        )
        
        assert 'cp' in capability
        assert 'cpk' in capability
        assert 'cpu' in capability
        assert 'cpl' in capability
        assert 'pp' in capability
        assert 'ppk' in capability
        
        # Все показатели должны быть положительными
        assert capability['cp'] > 0
        assert capability['cpk'] > 0

    def test_calculate_process_capability_one_sided(self, statistics_service):
        """Тест расчета показателей воспроизводимости для односторонних границ."""
        values = [450.5, 455.0, 448.2, 460.8, 452.3]
        
        # Только верхняя граница
        capability = statistics_service.calculate_process_capability(
            values, upper_spec=470.0
        )
        
        assert 'cpu' in capability
        assert 'cpk' in capability
        assert 'cp' not in capability

    def test_calculate_process_capability_no_specs(self, statistics_service):
        """Тест расчета показателей воспроизводимости без спецификационных границ."""
        values = [450.5, 455.0, 448.2, 460.8, 452.3]
        
        capability = statistics_service.calculate_process_capability(values)
        
        assert capability == {}

    def test_calculate_process_capability_zero_std(self, statistics_service):
        """Тест расчета показателей воспроизводимости для данных с нулевым СКО."""
        values = [450.0, 450.0, 450.0, 450.0, 450.0]
        
        capability = statistics_service.calculate_process_capability(
            values, lower_spec=440.0, upper_spec=460.0
        )
        
        assert capability['cp'] == float('inf')
        assert capability['cpk'] == float('inf')

    def test_get_available_tests(self, statistics_service, mock_db_connection):
        """Тест получения списка доступных тестов."""
        mock_cursor = mock_db_connection.cursor.return_value
        mock_cursor.fetchall.return_value = [
            {'name': 'Предел прочности'},
            {'name': 'Предел текучести'}
        ]
        
        tests = statistics_service.get_available_tests()
        
        assert len(tests) >= 2
        assert 'Предел прочности' in tests
        assert 'Предел текучести' in tests

    def test_get_material_grades(self, statistics_service, mock_db_connection):
        """Тест получения списка марок материалов."""
        mock_cursor = mock_db_connection.cursor.return_value
        mock_cursor.fetchall.return_value = [
            {'grade': 'Ст20'},
            {'grade': 'Ст45'}
        ]
        
        grades = statistics_service.get_material_grades()
        
        assert len(grades) == 2
        assert 'Ст20' in grades
        assert 'Ст45' in grades

    def test_get_test_results_data_with_filter(self, statistics_service, mock_db_connection):
        """Тест получения данных с фильтром по материалу."""
        mock_cursor = mock_db_connection.cursor.return_value
        mock_cursor.fetchall.return_value = []
        
        statistics_service.get_test_results_data('Предел прочности', 'Ст20', 30)
        
        # Проверяем, что запрос был выполнен с фильтром по материалу
        mock_cursor.execute.assert_called_once()
        args, kwargs = mock_cursor.execute.call_args
        query = args[0]
        params = args[1] if len(args) > 1 else []
        
        assert 'g.grade = ?' in query
        assert 'Ст20' in params

    def test_get_test_results_data_database_error(self, statistics_service, mock_db_connection):
        """Тест обработки ошибки БД при получении данных."""
        mock_cursor = mock_db_connection.cursor.return_value
        mock_cursor.execute.side_effect = Exception("Database error")
        
        with pytest.raises(BusinessLogicError) as exc_info:
            statistics_service.get_test_results_data('Предел прочности', None, 30)
        
        assert "Ошибка получения данных для статистического анализа" in str(exc_info.value)

    def test_get_test_results_data_json_error(self, statistics_service, mock_db_connection):
        """Тест обработки ошибки JSON при получении данных."""
        mock_cursor = mock_db_connection.cursor.return_value
        mock_cursor.fetchall.return_value = [
            {
                'id': 1,
                'request_number': 'REQ-001',
                'creation_date': '2024-01-01',
                'results_json': 'invalid json',
                'material_grade': 'Ст20',
                'heat_num': 'A123'
            }
        ]
        
        result = statistics_service.get_test_results_data('Предел прочности', None, 30)
        
        # Должен вернуть пустой список из-за ошибки JSON
        assert result == []

    def test_statistical_calculations_with_real_data(self, statistics_service):
        """Интеграционный тест статистических расчетов с реальными данными."""
        # Данные, имитирующие реальные результаты испытаний
        values = [
            452.3, 448.7, 456.1, 451.9, 449.5, 454.2, 450.8, 453.6, 447.9, 455.7,
            452.1, 450.3, 448.8, 454.9, 451.2, 449.7, 453.4, 452.8, 450.6, 454.1
        ]
        
        # Основные статистики
        stats = statistics_service.calculate_basic_statistics(values)
        assert stats['count'] == 20
        assert 450 < stats['mean'] < 455
        assert stats['std'] > 0
        
        # Анализ выбросов
        outliers = statistics_service.detect_outliers_grubbs(values)
        assert outliers['test_statistic'] is not None
        assert outliers['critical_value'] is not None
        
        # Контрольные карты
        limits = statistics_service.calculate_control_chart_limits(values, 'X')
        assert limits['center_line'] > 0
        assert limits['ucl'] > limits['center_line']
        assert limits['lcl'] < limits['center_line']
        
        # Проверка правил
        rules = statistics_service.check_control_chart_rules(values, limits)
        assert 'process_stable' in rules
        
        # Воспроизводимость процесса
        capability = statistics_service.calculate_process_capability(
            values, lower_spec=440.0, upper_spec=465.0
        )
        assert capability['cp'] > 0
        assert capability['cpk'] > 0

    def test_edge_cases_small_datasets(self, statistics_service):
        """Тест граничных случаев для малых наборов данных."""
        # Один элемент
        single_value = [450.0]
        stats = statistics_service.calculate_basic_statistics(single_value)
        assert stats['count'] == 1
        assert stats['mean'] == 450.0
        # Для одного элемента СКО может быть NaN или 0, проверяем что это число
        assert isinstance(stats['std'], float)
        
        # Два элемента
        two_values = [450.0, 455.0]
        outliers = statistics_service.detect_outliers_grubbs(two_values)
        assert len(outliers['outliers']) == 0
        
        # Контрольные карты с минимальными данными
        limits = statistics_service.calculate_control_chart_limits(single_value, 'X')
        assert limits['center_line'] == 450.0

    def test_performance_large_dataset(self, statistics_service):
        """Тест производительности для больших наборов данных."""
        # Создаем большой набор данных
        np.random.seed(42)
        large_values = np.random.normal(450, 5, 1000).tolist()
        
        # Все операции должны выполняться быстро
        import time
        
        start = time.time()
        stats = statistics_service.calculate_basic_statistics(large_values)
        basic_time = time.time() - start
        
        start = time.time()
        outliers = statistics_service.detect_outliers_grubbs(large_values)
        outliers_time = time.time() - start
        
        start = time.time()
        limits = statistics_service.calculate_control_chart_limits(large_values, 'X')
        control_time = time.time() - start
        
        # Проверяем результаты
        assert stats['count'] == 1000
        assert outliers['test_statistic'] is not None
        assert limits['center_line'] is not None
        
        # Проверяем время выполнения (должно быть разумным)
        assert basic_time < 1.0  # Менее 1 секунды
        assert outliers_time < 2.0  # Менее 2 секунд
        assert control_time < 1.0  # Менее 1 секунды 
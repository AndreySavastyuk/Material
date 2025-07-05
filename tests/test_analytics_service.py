"""
Тесты для аналитического сервиса.
"""

import pytest
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
import sqlite3
import tempfile
import os

from services.analytics_service import AnalyticsService
from utils.exceptions import BusinessLogicError, ValidationError


class TestAnalyticsService:
    """Тесты для AnalyticsService."""
    
    @pytest.fixture
    def db_connection(self):
        """Фикстура для подключения к тестовой БД."""
        # Создаем временную БД в памяти
        conn = sqlite3.connect(':memory:')
        
        # Создаем необходимые таблицы
        conn.execute('''
            CREATE TABLE Suppliers (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL
            )
        ''')
        
        conn.execute('''
            CREATE TABLE Grades (
                id INTEGER PRIMARY KEY,
                grade TEXT NOT NULL,
                standard TEXT,
                density REAL
            )
        ''')
        
        conn.execute('''
            CREATE TABLE RollingTypes (
                id INTEGER PRIMARY KEY,
                type TEXT NOT NULL
            )
        ''')
        
        conn.execute('''
            CREATE TABLE Materials (
                id INTEGER PRIMARY KEY,
                to_delete INTEGER DEFAULT 0,
                arrival_date TEXT,
                supplier_id INTEGER,
                grade_id INTEGER,
                rolling_type_id INTEGER,
                cert_num TEXT,
                needs_lab INTEGER DEFAULT 0,
                volume_weight_kg REAL,
                volume_length_mm REAL,
                FOREIGN KEY (supplier_id) REFERENCES Suppliers(id),
                FOREIGN KEY (grade_id) REFERENCES Grades(id),
                FOREIGN KEY (rolling_type_id) REFERENCES RollingTypes(id)
            )
        ''')
        
        conn.execute('''
            CREATE TABLE defects (
                id INTEGER PRIMARY KEY,
                material_id INTEGER,
                defect_type TEXT,
                description TEXT,
                reported_by TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                to_delete INTEGER DEFAULT 0,
                FOREIGN KEY (material_id) REFERENCES Materials(id)
            )
        ''')
        
        conn.execute('''
            CREATE TABLE lab_requests (
                id INTEGER PRIMARY KEY,
                creation_date TEXT,
                request_number TEXT,
                material_id INTEGER,
                tests_json TEXT,
                status TEXT DEFAULT 'Не отработана',
                archived INTEGER DEFAULT 0,
                results_json TEXT,
                FOREIGN KEY (material_id) REFERENCES Materials(id)
            )
        ''')
        
        # Заполняем тестовыми данными
        conn.execute("INSERT INTO Suppliers (name) VALUES ('Поставщик А')")
        conn.execute("INSERT INTO Suppliers (name) VALUES ('Поставщик Б')")
        
        conn.execute("INSERT INTO Grades (grade, standard, density) VALUES ('Сталь 20', 'ГОСТ 1050', 7.85)")
        conn.execute("INSERT INTO Grades (grade, standard, density) VALUES ('Сталь 45', 'ГОСТ 1050', 7.85)")
        
        conn.execute("INSERT INTO RollingTypes (type) VALUES ('Круг')")
        conn.execute("INSERT INTO RollingTypes (type) VALUES ('Лист')")
        
        # Добавляем материалы
        today = datetime.now().strftime('%Y-%m-%d')
        week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        
        conn.execute('''
            INSERT INTO Materials (arrival_date, supplier_id, grade_id, rolling_type_id, 
                                 cert_num, needs_lab, volume_weight_kg, volume_length_mm)
            VALUES (?, 1, 1, 1, 'CERT001', 1, 100.5, 2000)
        ''', (today,))
        
        conn.execute('''
            INSERT INTO Materials (arrival_date, supplier_id, grade_id, rolling_type_id, 
                                 cert_num, needs_lab, volume_weight_kg, volume_length_mm)
            VALUES (?, 2, 2, 2, 'CERT002', 0, 200.0, 3000)
        ''', (week_ago,))
        
        # Добавляем дефекты
        conn.execute('''
            INSERT INTO defects (material_id, defect_type, description, reported_by)
            VALUES (1, 'Царапина', 'Небольшая царапина', 'Контроллер')
        ''')
        
        # Добавляем заявки лаборатории
        conn.execute('''
            INSERT INTO lab_requests (creation_date, request_number, material_id, status)
            VALUES (?, 'REQ001', 1, 'Не отработана')
        ''', (week_ago,))
        
        conn.commit()
        yield conn
        conn.close()
    
    @pytest.fixture
    def analytics_service(self, db_connection):
        """Фикстура для AnalyticsService."""
        return AnalyticsService(db_connection)
    
    def test_create_quality_analysis_report(self, analytics_service):
        """Тест создания отчета по анализу качества."""
        # Без фильтра по датам
        result = analytics_service.create_quality_analysis_report()
        
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2  # Два поставщика
        assert 'Поставщик' in result.columns
        assert 'Всего материалов' in result.columns
        assert 'Процент брака (%)' in result.columns
        
        # С фильтром по датам
        today = datetime.now().strftime('%Y-%m-%d')
        result_filtered = analytics_service.create_quality_analysis_report(
            date_from=today, date_to=today
        )
        
        assert isinstance(result_filtered, pd.DataFrame)
        assert len(result_filtered) <= len(result)
    
    def test_create_defects_by_grade_report(self, analytics_service):
        """Тест создания отчета по статистике брака по маркам."""
        result = analytics_service.create_defects_by_grade_report()
        
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2  # Две марки
        assert 'Марка' in result.columns
        assert 'Всего материалов' in result.columns
        assert 'Процент брака (%)' in result.columns
        
        # Проверяем, что процент брака рассчитан правильно
        steel_20_row = result[result['Марка'] == 'Сталь 20']
        assert len(steel_20_row) == 1
        assert steel_20_row.iloc[0]['Процент брака (%)'] == 100.0  # 1 дефект из 1 материала
    
    def test_create_supply_dynamics_report(self, analytics_service):
        """Тест создания отчета по динамике поставок."""
        # По месяцам
        result = analytics_service.create_supply_dynamics_report(group_by='month')
        
        assert isinstance(result, pd.DataFrame)
        assert 'Месяц' in result.columns
        assert 'Количество поставок' in result.columns
        assert 'Общий вес (кг)' in result.columns
        
        # По дням
        result_daily = analytics_service.create_supply_dynamics_report(group_by='day')
        
        assert isinstance(result_daily, pd.DataFrame)
        assert 'День' in result_daily.columns
        
        # С фильтром по датам
        today = datetime.now().strftime('%Y-%m-%d')
        result_filtered = analytics_service.create_supply_dynamics_report(
            date_from=today, date_to=today, group_by='day'
        )
        
        assert isinstance(result_filtered, pd.DataFrame)
    
    def test_create_overdue_tests_report(self, analytics_service):
        """Тест создания отчета о просроченных испытаниях."""
        result = analytics_service.create_overdue_tests_report(overdue_days=1)
        
        assert isinstance(result, pd.DataFrame)
        assert 'Номер заявки' in result.columns
        assert 'Дней просрочки' in result.columns
        assert 'Статус' in result.columns
        
        # Проверяем, что есть просроченные заявки
        assert len(result) > 0
    
    def test_create_dashboard_data(self, analytics_service):
        """Тест создания данных для дашборда."""
        result = analytics_service.create_dashboard_data()
        
        assert isinstance(result, dict)
        assert 'main_metrics' in result
        assert 'defects_stats' in result
        assert 'lab_stats' in result
        assert 'top_suppliers' in result
        assert 'recent_supplies' in result
        assert 'quality_by_suppliers' in result
        
        # Проверяем основные метрики
        main_metrics = result['main_metrics']
        assert main_metrics['total_materials'] == 2
        assert main_metrics['active_materials'] == 2
        assert main_metrics['need_testing'] == 1
        assert main_metrics['suppliers_count'] == 2
        
        # Проверяем статистику дефектов
        defects_stats = result['defects_stats']
        assert defects_stats['total_defects'] == 1
        assert defects_stats['affected_materials'] == 1
        assert defects_stats['defect_types_count'] == 1
        
        # Проверяем статистику лаборатории
        lab_stats = result['lab_stats']
        assert lab_stats['total_requests'] == 1
        assert lab_stats['pending_requests'] == 1
    
    @patch('matplotlib.pyplot.savefig')
    def test_create_chart_image(self, mock_savefig, analytics_service):
        """Тест создания изображения графика."""
        # Создаем тестовые данные
        data = pd.DataFrame({
            'Поставщик': ['Поставщик А', 'Поставщик Б'],
            'Количество': [10, 20]
        })
        
        # Мокаем savefig чтобы избежать реального сохранения
        mock_savefig.return_value = None
        
        result = analytics_service.create_chart_image(
            'bar', data, 'Тест график',
            x_column='Поставщик', y_column='Количество'
        )
        
        # Проверяем, что результат - строка (base64)
        assert isinstance(result, str)
        
        # Проверяем, что savefig был вызван
        mock_savefig.assert_called_once()
    
    @patch('matplotlib.pyplot.savefig')
    def test_create_quality_trend_chart(self, mock_savefig, analytics_service):
        """Тест создания графика тренда качества."""
        mock_savefig.return_value = None
        
        result = analytics_service.create_quality_trend_chart(days=30)
        
        assert isinstance(result, str)
    
    @patch('matplotlib.pyplot.savefig')
    def test_create_suppliers_comparison_chart(self, mock_savefig, analytics_service):
        """Тест создания графика сравнения поставщиков."""
        mock_savefig.return_value = None
        
        result = analytics_service.create_suppliers_comparison_chart()
        
        assert isinstance(result, str)
    
    def test_handle_db_error(self, analytics_service):
        """Тест обработки ошибок БД."""
        test_error = sqlite3.Error("Test error")
        
        with pytest.raises(BusinessLogicError) as exc_info:
            analytics_service.handle_db_error(test_error, "тестовой операции")
        
        assert "тестовой операции" in str(exc_info.value)
        assert exc_info.value.original_error == test_error
    
    def test_empty_data_handling(self, analytics_service):
        """Тест обработки пустых данных."""
        # Очищаем таблицы
        analytics_service.db_connection.execute("DELETE FROM Materials")
        analytics_service.db_connection.execute("DELETE FROM defects")
        analytics_service.db_connection.execute("DELETE FROM lab_requests")
        analytics_service.db_connection.commit()
        
        # Проверяем, что функции возвращают пустые результаты
        result = analytics_service.create_quality_analysis_report()
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0 or all(result['Всего материалов'] == 0)
        
        result = analytics_service.create_defects_by_grade_report()
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0 or all(result['Всего материалов'] == 0)
        
        result = analytics_service.create_supply_dynamics_report()
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0
        
        result = analytics_service.create_overdue_tests_report()
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0
        
        dashboard_data = analytics_service.create_dashboard_data()
        assert dashboard_data['main_metrics']['total_materials'] == 0
        assert dashboard_data['defects_stats']['total_defects'] == 0
        assert dashboard_data['lab_stats']['total_requests'] == 0
    
    def test_date_validation(self, analytics_service):
        """Тест валидации дат."""
        # Неправильный формат даты
        with pytest.raises(Exception):
            analytics_service.create_quality_analysis_report(
                date_from='invalid-date', date_to='2024-01-01'
            )
        
        # Дата "от" больше даты "до"
        result = analytics_service.create_quality_analysis_report(
            date_from='2024-12-31', date_to='2024-01-01'
        )
        # Должен вернуть пустой результат
        assert len(result) == 0 or all(result['Всего материалов'] == 0) 
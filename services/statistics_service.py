"""
Сервис для статистического анализа результатов испытаний.

Предоставляет функциональность для:
- Расчета основных статистических показателей (среднее, СКО, медиана)
- Определения выбросов по критерию Граббса
- Построения контрольных карт Шухарта
- Анализа стабильности процесса
"""

import json
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple, Union
import math

import numpy as np
from scipy import stats
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from utils.logger import get_logger
from utils.exceptions import ValidationError, BusinessLogicError

logger = get_logger(__name__)


class StatisticsService:
    """
    Сервис для статистического анализа результатов испытаний.
    """
    
    def __init__(self, db_connection):
        """
        Инициализация сервиса.
        
        Args:
            db_connection: Подключение к базе данных
        """
        self.db_connection = db_connection
        
        # Критические значения для критерия Граббса (альфа = 0.05)
        self.grubbs_critical_values = {
            3: 1.148, 4: 1.481, 5: 1.715, 6: 1.887, 7: 2.020, 8: 2.126,
            9: 2.215, 10: 2.290, 11: 2.355, 12: 2.412, 13: 2.462, 14: 2.507,
            15: 2.549, 16: 2.585, 17: 2.620, 18: 2.651, 19: 2.681, 20: 2.709,
            21: 2.733, 22: 2.758, 23: 2.781, 24: 2.802, 25: 2.822, 26: 2.841,
            27: 2.859, 28: 2.876, 29: 2.893, 30: 2.908, 35: 2.979, 40: 3.036,
            45: 3.085, 50: 3.128, 60: 3.199, 70: 3.257, 80: 3.305, 90: 3.347,
            100: 3.384
        }
    
    def get_test_results_data(self, test_name: str, material_grade: Optional[str] = None,
                             days_back: int = 30) -> List[Dict[str, Any]]:
        """
        Получение данных результатов испытаний за определенный период.
        
        Args:
            test_name: Название теста
            material_grade: Марка материала (опционально)
            days_back: Количество дней назад
            
        Returns:
            Список данных результатов
        """
        try:
            start_date = datetime.now() - timedelta(days=days_back)
            
            query = """
                SELECT 
                    lr.id,
                    lr.request_number,
                    lr.creation_date,
                    lr.results_json,
                    g.grade as material_grade,
                    m.heat_num
                FROM lab_requests lr
                JOIN Materials m ON lr.material_id = m.id
                JOIN Grades g ON m.grade_id = g.id
                WHERE lr.creation_date >= ?
                AND lr.status = 'ППСД пройден'
                AND lr.archived = 0
            """
            
            params = [start_date.strftime('%Y-%m-%d')]
            
            if material_grade:
                query += " AND g.grade = ?"
                params.append(material_grade)
            
            query += " ORDER BY lr.creation_date"
            
            cursor = self.db_connection.cursor()
            cursor.execute(query, params)
            
            results = []
            for row in cursor.fetchall():
                try:
                    results_data = json.loads(row['results_json'])
                    
                    # Ищем нужный тест
                    for result in results_data:
                        if result['name'] == test_name:
                            value_str = result.get('result', '')
                            
                            # Извлекаем числовое значение
                            numeric_value = self._extract_numeric_value(value_str)
                            
                            if numeric_value is not None:
                                results.append({
                                    'request_id': row['id'],
                                    'request_number': row['request_number'],
                                    'date': row['creation_date'],
                                    'value': numeric_value,
                                    'material_grade': row['material_grade'],
                                    'heat_num': row['heat_num'] or '',
                                    'original_value': value_str
                                })
                            break
                            
                except json.JSONDecodeError:
                    continue
                except Exception as e:
                    logger.warning(f"Ошибка обработки результата {row['id']}: {e}")
                    continue
            
            logger.info(f"Получено {len(results)} результатов для теста '{test_name}'")
            return results
            
        except Exception as e:
            logger.error(f"Ошибка получения данных результатов: {e}")
            raise BusinessLogicError(
                message="Ошибка получения данных для статистического анализа",
                original_error=e
            )
    
    def _extract_numeric_value(self, value_str: str) -> Optional[float]:
        """
        Извлечение числового значения из строки результата.
        
        Args:
            value_str: Строка с результатом
            
        Returns:
            Числовое значение или None
        """
        if not value_str:
            return None
        
        # Удаляем лишние пробелы
        value_str = value_str.strip()
        
        # Пытаемся извлечь число из строки
        import re
        
        # Паттерн для числа (целое или дробное)
        number_pattern = r'[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?'
        
        match = re.search(number_pattern, value_str)
        if match:
            try:
                return float(match.group())
            except ValueError:
                return None
        
        return None
    
    def calculate_basic_statistics(self, values: List[float]) -> Dict[str, float]:
        """
        Расчет основных статистических показателей.
        
        Args:
            values: Список значений
            
        Returns:
            Словарь с основными статистиками
        """
        if not values:
            return {}
        
        try:
            values_array = np.array(values)
            
            statistics = {
                'count': len(values),
                'mean': float(np.mean(values_array)),
                'median': float(np.median(values_array)),
                'std': float(np.std(values_array, ddof=1)),  # Выборочное СКО
                'min': float(np.min(values_array)),
                'max': float(np.max(values_array)),
                'range': float(np.max(values_array) - np.min(values_array)),
                'cv': float(np.std(values_array, ddof=1) / np.mean(values_array) * 100),  # Коэффициент вариации
                'q1': float(np.percentile(values_array, 25)),
                'q3': float(np.percentile(values_array, 75)),
                'iqr': float(np.percentile(values_array, 75) - np.percentile(values_array, 25)),
                'skewness': float(stats.skew(values_array)),
                'kurtosis': float(stats.kurtosis(values_array))
            }
            
            return statistics
            
        except Exception as e:
            logger.error(f"Ошибка расчета статистик: {e}")
            return {}
    
    def detect_outliers_grubbs(self, values: List[float], alpha: float = 0.05) -> Dict[str, Any]:
        """
        Определение выбросов по критерию Граббса.
        
        Args:
            values: Список значений
            alpha: Уровень значимости (по умолчанию 0.05)
            
        Returns:
            Словарь с результатами анализа выбросов
        """
        if len(values) < 3:
            return {'outliers': [], 'test_statistic': None, 'critical_value': None}
        
        try:
            values_array = np.array(values)
            n = len(values_array)
            
            # Получаем критическое значение
            critical_value = self._get_grubbs_critical_value(n, alpha)
            
            mean_val = np.mean(values_array)
            std_val = np.std(values_array, ddof=1)
            
            if std_val == 0:
                return {'outliers': [], 'test_statistic': None, 'critical_value': critical_value}
            
            # Расчет статистики Граббса для каждого значения
            grubbs_stats = np.abs(values_array - mean_val) / std_val
            max_grubbs = np.max(grubbs_stats)
            
            outliers = []
            if max_grubbs > critical_value:
                # Находим все значения, которые являются выбросами
                outlier_indices = np.where(grubbs_stats > critical_value)[0]
                
                for idx in outlier_indices:
                    outliers.append({
                        'index': int(idx),
                        'value': float(values_array[idx]),
                        'grubbs_statistic': float(grubbs_stats[idx]),
                        'z_score': float((values_array[idx] - mean_val) / std_val)
                    })
            
            return {
                'outliers': outliers,
                'test_statistic': float(max_grubbs),
                'critical_value': critical_value,
                'mean': float(mean_val),
                'std': float(std_val)
            }
            
        except Exception as e:
            logger.error(f"Ошибка определения выбросов: {e}")
            return {'outliers': [], 'test_statistic': None, 'critical_value': None}
    
    def _get_grubbs_critical_value(self, n: int, alpha: float = 0.05) -> float:
        """
        Получение критического значения для критерия Граббса.
        
        Args:
            n: Размер выборки
            alpha: Уровень значимости
            
        Returns:
            Критическое значение
        """
        # Для alpha = 0.05 используем таблицу
        if alpha == 0.05:
            if n in self.grubbs_critical_values:
                return self.grubbs_critical_values[n]
            elif n > 100:
                # Для больших выборок используем аппроксимацию
                return self.grubbs_critical_values[100]
            else:
                # Интерполяция для промежуточных значений
                keys = sorted(self.grubbs_critical_values.keys())
                for i, k in enumerate(keys):
                    if n < k:
                        if i == 0:
                            return self.grubbs_critical_values[k]
                        # Линейная интерполяция
                        k1, k2 = keys[i-1], keys[i]
                        v1, v2 = self.grubbs_critical_values[k1], self.grubbs_critical_values[k2]
                        return v1 + (v2 - v1) * (n - k1) / (k2 - k1)
                
                return self.grubbs_critical_values[keys[-1]]
        else:
            # Для других уровней значимости используем t-распределение
            t_crit = stats.t.ppf(1 - alpha / (2 * n), n - 2)
            return ((n - 1) / math.sqrt(n)) * math.sqrt(t_crit**2 / (n - 2 + t_crit**2))
    
    def calculate_control_chart_limits(self, values: List[float], chart_type: str = 'X') -> Dict[str, float]:
        """
        Расчет границ контрольной карты Шухарта.
        
        Args:
            values: Список значений
            chart_type: Тип карты ('X' для индивидуальных значений, 'MR' для скользящих размахов)
            
        Returns:
            Словарь с границами карты
        """
        if not values:
            return {}
        
        try:
            values_array = np.array(values)
            
            if chart_type == 'X':
                # Карта индивидуальных значений
                center_line = np.mean(values_array)
                
                # Расчет скользящих размахов
                moving_ranges = []
                for i in range(1, len(values_array)):
                    moving_ranges.append(abs(values_array[i] - values_array[i-1]))
                
                if not moving_ranges:
                    return {'center_line': center_line, 'ucl': center_line, 'lcl': center_line}
                
                avg_moving_range = np.mean(moving_ranges)
                
                # Константы для карты индивидуальных значений
                A2 = 2.66  # Для n=2 (скользящий размах)
                
                ucl = center_line + A2 * avg_moving_range
                lcl = center_line - A2 * avg_moving_range
                
                return {
                    'center_line': float(center_line),
                    'ucl': float(ucl),
                    'lcl': float(lcl),
                    'avg_moving_range': float(avg_moving_range)
                }
                
            elif chart_type == 'MR':
                # Карта скользящих размахов
                moving_ranges = []
                for i in range(1, len(values_array)):
                    moving_ranges.append(abs(values_array[i] - values_array[i-1]))
                
                if not moving_ranges:
                    return {}
                
                center_line = np.mean(moving_ranges)
                
                # Константы для карты размахов
                D3 = 0    # Для n=2
                D4 = 3.27 # Для n=2
                
                ucl = D4 * center_line
                lcl = D3 * center_line
                
                return {
                    'center_line': float(center_line),
                    'ucl': float(ucl),
                    'lcl': float(lcl)
                }
                
        except Exception as e:
            logger.error(f"Ошибка расчета границ контрольной карты: {e}")
            return {}
    
    def check_control_chart_rules(self, values: List[float], limits: Dict[str, float]) -> Dict[str, Any]:
        """
        Проверка правил контрольной карты Шухарта.
        
        Args:
            values: Список значений
            limits: Границы контрольной карты
            
        Returns:
            Результаты проверки правил
        """
        if not values or not limits:
            return {}
        
        try:
            values_array = np.array(values)
            center_line = limits['center_line']
            ucl = limits['ucl']
            lcl = limits['lcl']
            
            # Правило 1: Точки вне контрольных границ
            points_outside = []
            for i, val in enumerate(values_array):
                if val > ucl or val < lcl:
                    points_outside.append({
                        'index': i,
                        'value': float(val),
                        'type': 'above_ucl' if val > ucl else 'below_lcl'
                    })
            
            # Правило 2: 7 точек подряд по одну сторону от центральной линии
            consecutive_above = 0
            consecutive_below = 0
            runs_above_7 = []
            runs_below_7 = []
            
            for i, val in enumerate(values_array):
                if val > center_line:
                    consecutive_above += 1
                    consecutive_below = 0
                    if consecutive_above >= 7:
                        runs_above_7.append({
                            'start_index': i - consecutive_above + 1,
                            'end_index': i,
                            'length': consecutive_above
                        })
                elif val < center_line:
                    consecutive_below += 1
                    consecutive_above = 0
                    if consecutive_below >= 7:
                        runs_below_7.append({
                            'start_index': i - consecutive_below + 1,
                            'end_index': i,
                            'length': consecutive_below
                        })
                else:
                    consecutive_above = 0
                    consecutive_below = 0
            
            # Правило 3: 2 из 3 точек подряд в зоне A (между 2σ и 3σ)
            sigma = (ucl - center_line) / 3
            zone_a_upper = center_line + 2 * sigma
            zone_a_lower = center_line - 2 * sigma
            
            zone_a_violations = []
            for i in range(len(values_array) - 2):
                points_in_zone_a = 0
                for j in range(3):
                    val = values_array[i + j]
                    if (val > zone_a_upper and val <= ucl) or (val < zone_a_lower and val >= lcl):
                        points_in_zone_a += 1
                
                if points_in_zone_a >= 2:
                    zone_a_violations.append({
                        'start_index': i,
                        'end_index': i + 2,
                        'points_in_zone_a': points_in_zone_a
                    })
            
            # Правило 4: Тренд (6 точек подряд возрастающие или убывающие)
            trends = []
            for i in range(len(values_array) - 5):
                increasing = True
                decreasing = True
                for j in range(5):
                    if values_array[i + j] >= values_array[i + j + 1]:
                        increasing = False
                    if values_array[i + j] <= values_array[i + j + 1]:
                        decreasing = False
                
                if increasing or decreasing:
                    trends.append({
                        'start_index': i,
                        'end_index': i + 5,
                        'type': 'increasing' if increasing else 'decreasing'
                    })
            
            return {
                'rule_1_violations': points_outside,
                'rule_2_violations': {'runs_above_7': runs_above_7, 'runs_below_7': runs_below_7},
                'rule_3_violations': zone_a_violations,
                'rule_4_violations': trends,
                'process_stable': len(points_outside) == 0 and len(runs_above_7) == 0 and 
                                 len(runs_below_7) == 0 and len(zone_a_violations) == 0 and len(trends) == 0
            }
            
        except Exception as e:
            logger.error(f"Ошибка проверки правил контрольной карты: {e}")
            return {}
    
    def calculate_process_capability(self, values: List[float], 
                                   lower_spec: Optional[float] = None,
                                   upper_spec: Optional[float] = None) -> Dict[str, float]:
        """
        Расчет показателей воспроизводимости процесса.
        
        Args:
            values: Список значений
            lower_spec: Нижняя граница спецификации
            upper_spec: Верхняя граница спецификации
            
        Returns:
            Показатели воспроизводимости
        """
        if not values:
            return {}
        
        try:
            values_array = np.array(values)
            mean_val = np.mean(values_array)
            std_val = np.std(values_array, ddof=1)
            
            if std_val == 0:
                return {'cp': float('inf'), 'cpk': float('inf'), 'pp': float('inf'), 'ppk': float('inf')}
            
            capability = {}
            
            # Cp - потенциальная воспроизводимость
            if lower_spec is not None and upper_spec is not None:
                cp = (upper_spec - lower_spec) / (6 * std_val)
                capability['cp'] = float(cp)
            
            # Cpk - действительная воспроизводимость
            if lower_spec is not None and upper_spec is not None:
                cpu = (upper_spec - mean_val) / (3 * std_val)
                cpl = (mean_val - lower_spec) / (3 * std_val)
                cpk = min(cpu, cpl)
                capability['cpk'] = float(cpk)
                capability['cpu'] = float(cpu)
                capability['cpl'] = float(cpl)
            elif upper_spec is not None:
                cpu = (upper_spec - mean_val) / (3 * std_val)
                capability['cpu'] = float(cpu)
                capability['cpk'] = float(cpu)
            elif lower_spec is not None:
                cpl = (mean_val - lower_spec) / (3 * std_val)
                capability['cpl'] = float(cpl)
                capability['cpk'] = float(cpl)
            
            # Pp и Ppk (с использованием полного стандартного отклонения)
            if lower_spec is not None and upper_spec is not None:
                pp = (upper_spec - lower_spec) / (6 * std_val)
                ppu = (upper_spec - mean_val) / (3 * std_val)
                ppl = (mean_val - lower_spec) / (3 * std_val)
                ppk = min(ppu, ppl)
                
                capability['pp'] = float(pp)
                capability['ppk'] = float(ppk)
                capability['ppu'] = float(ppu)
                capability['ppl'] = float(ppl)
            
            return capability
            
        except Exception as e:
            logger.error(f"Ошибка расчета показателей воспроизводимости: {e}")
            return {}
    
    def get_available_tests(self) -> List[str]:
        """
        Получение списка доступных тестов из базы данных.
        
        Returns:
            Список названий тестов
        """
        try:
            query = """
                SELECT DISTINCT tv.name
                FROM template_variables tv
                WHERE tv.category = 'test_results'
                AND tv.is_system = 1
                ORDER BY tv.name
            """
            
            cursor = self.db_connection.cursor()
            cursor.execute(query)
            
            tests = [row['name'] for row in cursor.fetchall()]
            
            # Добавляем наиболее распространенные тесты, если их нет в БД
            common_tests = [
                'Предел прочности',
                'Предел текучести',
                'Относительное удлинение',
                'Относительное сужение',
                'Ударная вязкость',
                'Твердость по Бринеллю',
                'Твердость по Роквеллу'
            ]
            
            for test in common_tests:
                if test not in tests:
                    tests.append(test)
            
            return tests
            
        except Exception as e:
            logger.error(f"Ошибка получения списка тестов: {e}")
            return []
    
    def get_material_grades(self) -> List[str]:
        """
        Получение списка марок материалов.
        
        Returns:
            Список марок материалов
        """
        try:
            query = """
                SELECT DISTINCT g.grade
                FROM Grades g
                JOIN Materials m ON g.id = m.grade_id
                JOIN lab_requests lr ON m.id = lr.material_id
                WHERE lr.status = 'ППСД пройден'
                ORDER BY g.grade
            """
            
            cursor = self.db_connection.cursor()
            cursor.execute(query)
            
            grades = [row['grade'] for row in cursor.fetchall()]
            return grades
            
        except Exception as e:
            logger.error(f"Ошибка получения списка марок материалов: {e}")
            return [] 
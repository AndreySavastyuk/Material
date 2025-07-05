"""
Сервис для создания аналитических отчетов и дашборда.
Расширяет базовую функциональность отчетности аналитическими возможностями.
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import sqlite3
import os
import io
import base64

# Импорты для визуализации
import matplotlib
matplotlib.use('Agg')  # Использовать non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.figure import Figure
import seaborn as sns

from services.base import BaseService
from utils.exceptions import (
    ValidationError, RequiredFieldError, InvalidFormatError,
    ValueOutOfRangeError, RecordNotFoundError, BusinessLogicError
)
from utils.logger import get_logger

logger = get_logger('services.analytics')

# Настройка стилей для графиков
plt.style.use('seaborn-v0_8')
sns.set_palette("husl")


class AnalyticsService:
    """
    Сервис для создания аналитических отчетов и визуализаций.
    """
    
    def __init__(self, db_connection: sqlite3.Connection):
        """
        Инициализация сервиса аналитики.
        
        Args:
            db_connection: Соединение с базой данных
        """
        self.db_connection = db_connection
        self.output_dir = "reports"
        self._ensure_output_dir()
    
    def _ensure_output_dir(self):
        """Создает директорию для отчетов если она не существует."""
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
    
    def create_quality_analysis_report(self, 
                                     date_from: Optional[str] = None,
                                     date_to: Optional[str] = None) -> pd.DataFrame:
        """
        Создает отчет по анализу качества по поставщикам.
        
        Args:
            date_from: Дата начала периода (YYYY-MM-DD)
            date_to: Дата окончания периода (YYYY-MM-DD)
            
        Returns:
            DataFrame с анализом качества по поставщикам
        """
        try:
            query = """
                SELECT 
                    s.name as 'Поставщик',
                    COUNT(m.id) as 'Всего материалов',
                    COUNT(CASE WHEN m.needs_lab = 1 THEN 1 END) as 'Требуют испытаний',
                    COUNT(d.id) as 'Количество дефектов',
                    ROUND(
                        CASE 
                            WHEN COUNT(m.id) > 0 
                            THEN (COUNT(d.id) * 100.0 / COUNT(m.id))
                            ELSE 0 
                        END, 2
                    ) as 'Процент брака (%)',
                    SUM(m.volume_weight_kg) as 'Общий вес (кг)',
                    GROUP_CONCAT(DISTINCT d.defect_type) as 'Типы дефектов'
                FROM Suppliers s
                LEFT JOIN Materials m ON s.id = m.supplier_id AND m.to_delete = 0
                LEFT JOIN defects d ON m.id = d.material_id AND d.to_delete = 0
                WHERE 1=1
            """
            
            params = []
            
            if date_from:
                query += " AND m.arrival_date >= ?"
                params.append(date_from)
            
            if date_to:
                query += " AND m.arrival_date <= ?"
                params.append(date_to)
            
            query += " GROUP BY s.id, s.name ORDER BY COUNT(m.id) DESC"
            
            df = pd.read_sql_query(query, self.db_connection, params=params)
            
            logger.info(f"Создан отчет по анализу качества поставщиков: {len(df)} записей")
            return df
            
        except Exception as e:
            self.handle_db_error(e, "создании отчета по анализу качества")
            raise
    
    def create_defects_by_grade_report(self,
                                     date_from: Optional[str] = None,
                                     date_to: Optional[str] = None) -> pd.DataFrame:
        """
        Создает отчет по статистике брака по маркам материалов.
        
        Args:
            date_from: Дата начала периода (YYYY-MM-DD)
            date_to: Дата окончания периода (YYYY-MM-DD)
            
        Returns:
            DataFrame со статистикой брака по маркам
        """
        try:
            query = """
                SELECT 
                    g.grade as 'Марка',
                    g.standard as 'Стандарт',
                    COUNT(m.id) as 'Всего материалов',
                    COUNT(d.id) as 'Количество дефектов',
                    ROUND(
                        CASE 
                            WHEN COUNT(m.id) > 0 
                            THEN (COUNT(d.id) * 100.0 / COUNT(m.id))
                            ELSE 0 
                        END, 2
                    ) as 'Процент брака (%)',
                    GROUP_CONCAT(DISTINCT d.defect_type) as 'Основные дефекты',
                    AVG(g.density) as 'Плотность',
                    SUM(m.volume_weight_kg) as 'Общий вес (кг)'
                FROM Grades g
                LEFT JOIN Materials m ON g.id = m.grade_id AND m.to_delete = 0
                LEFT JOIN defects d ON m.id = d.material_id AND d.to_delete = 0
                WHERE 1=1
            """
            
            params = []
            
            if date_from:
                query += " AND m.arrival_date >= ?"
                params.append(date_from)
            
            if date_to:
                query += " AND m.arrival_date <= ?"
                params.append(date_to)
            
            query += " GROUP BY g.id, g.grade, g.standard ORDER BY COUNT(d.id) DESC"
            
            df = pd.read_sql_query(query, self.db_connection, params=params)
            
            logger.info(f"Создан отчет по статистике брака по маркам: {len(df)} записей")
            return df
            
        except Exception as e:
            self.handle_db_error(e, "создании отчета по статистике брака")
            raise
    
    def create_supply_dynamics_report(self,
                                    date_from: Optional[str] = None,
                                    date_to: Optional[str] = None,
                                    group_by: str = 'month') -> pd.DataFrame:
        """
        Создает отчет по динамике поставок материалов.
        
        Args:
            date_from: Дата начала периода (YYYY-MM-DD)
            date_to: Дата окончания периода (YYYY-MM-DD)
            group_by: Группировка ('day', 'week', 'month', 'quarter')
            
        Returns:
            DataFrame с динамикой поставок
        """
        try:
            # Определяем формат группировки
            if group_by == 'day':
                date_format = "strftime('%Y-%m-%d', m.arrival_date)"
                period_name = 'День'
            elif group_by == 'week':
                date_format = "strftime('%Y-W%W', m.arrival_date)"
                period_name = 'Неделя'
            elif group_by == 'month':
                date_format = "strftime('%Y-%m', m.arrival_date)"
                period_name = 'Месяц'
            elif group_by == 'quarter':
                date_format = "strftime('%Y-Q', m.arrival_date) || CASE " \
                            "WHEN CAST(strftime('%m', m.arrival_date) AS INTEGER) <= 3 THEN '1' " \
                            "WHEN CAST(strftime('%m', m.arrival_date) AS INTEGER) <= 6 THEN '2' " \
                            "WHEN CAST(strftime('%m', m.arrival_date) AS INTEGER) <= 9 THEN '3' " \
                            "ELSE '4' END"
                period_name = 'Квартал'
            else:
                date_format = "strftime('%Y-%m', m.arrival_date)"
                period_name = 'Месяц'
            
            query = f"""
                SELECT 
                    {date_format} as '{period_name}',
                    COUNT(m.id) as 'Количество поставок',
                    COUNT(DISTINCT m.supplier_id) as 'Количество поставщиков',
                    SUM(m.volume_weight_kg) as 'Общий вес (кг)',
                    SUM(m.volume_length_mm) as 'Общая длина (мм)',
                    AVG(m.volume_weight_kg) as 'Средний вес поставки (кг)',
                    GROUP_CONCAT(DISTINCT s.name) as 'Поставщики'
                FROM Materials m
                LEFT JOIN Suppliers s ON m.supplier_id = s.id
                WHERE m.to_delete = 0
            """
            
            params = []
            
            if date_from:
                query += " AND m.arrival_date >= ?"
                params.append(date_from)
            
            if date_to:
                query += " AND m.arrival_date <= ?"
                params.append(date_to)
            
            query += f" GROUP BY {date_format} ORDER BY {date_format}"
            
            df = pd.read_sql_query(query, self.db_connection, params=params)
            
            logger.info(f"Создан отчет по динамике поставок: {len(df)} записей")
            return df
            
        except Exception as e:
            self.handle_db_error(e, "создании отчета по динамике поставок")
            raise
    
    def create_overdue_tests_report(self, overdue_days: int = 30) -> pd.DataFrame:
        """
        Создает отчет о просроченных испытаниях.
        
        Args:
            overdue_days: Количество дней для определения просрочки
            
        Returns:
            DataFrame с просроченными испытаниями
        """
        try:
            cutoff_date = (datetime.now() - timedelta(days=overdue_days)).strftime('%Y-%m-%d')
            
            query = """
                SELECT 
                    lr.request_number as 'Номер заявки',
                    lr.creation_date as 'Дата создания',
                    DATE(lr.creation_date, '+{} days') as 'Плановая дата завершения',
                    julianday('now') - julianday(lr.creation_date) as 'Дней просрочки',
                    lr.status as 'Статус',
                    m.id as 'ID материала',
                    s.name as 'Поставщик',
                    g.grade as 'Марка',
                    rt.type as 'Тип проката',
                    m.arrival_date as 'Дата поступления материала',
                    m.cert_num as 'Номер сертификата'
                FROM lab_requests lr
                LEFT JOIN Materials m ON lr.material_id = m.id
                LEFT JOIN Suppliers s ON m.supplier_id = s.id
                LEFT JOIN Grades g ON m.grade_id = g.id
                LEFT JOIN RollingTypes rt ON m.rolling_type_id = rt.id
                WHERE lr.creation_date <= ?
                AND lr.status NOT IN ('Завершена', 'Отменена', 'Архивирована')
                AND lr.archived = 0
                ORDER BY lr.creation_date ASC
            """.format(overdue_days)
            
            df = pd.read_sql_query(query, self.db_connection, params=[cutoff_date])
            
            logger.info(f"Создан отчет о просроченных испытаниях: {len(df)} записей")
            return df
            
        except Exception as e:
            self.handle_db_error(e, "создании отчета о просроченных испытаниях")
            raise
    
    def create_dashboard_data(self) -> Dict[str, Any]:
        """
        Создает данные для дашборда с ключевыми метриками.
        
        Returns:
            Словарь с данными для дашборда
        """
        try:
            dashboard_data = {}
            
            # Основные показатели
            main_metrics = self.db_connection.execute("""
                SELECT 
                    COUNT(*) as total_materials,
                    COUNT(CASE WHEN to_delete = 0 THEN 1 END) as active_materials,
                    COUNT(CASE WHEN needs_lab = 1 AND to_delete = 0 THEN 1 END) as need_testing,
                    SUM(CASE WHEN to_delete = 0 THEN volume_weight_kg ELSE 0 END) as total_weight,
                    COUNT(DISTINCT supplier_id) as suppliers_count
                FROM Materials
            """).fetchone()
            
            dashboard_data['main_metrics'] = {
                'total_materials': main_metrics[0],
                'active_materials': main_metrics[1],
                'need_testing': main_metrics[2],
                'total_weight': main_metrics[3] or 0,
                'suppliers_count': main_metrics[4]
            }
            
            # Статистика дефектов
            defects_stats = self.db_connection.execute("""
                SELECT 
                    COUNT(*) as total_defects,
                    COUNT(DISTINCT material_id) as affected_materials,
                    COUNT(DISTINCT defect_type) as defect_types_count
                FROM defects
                WHERE to_delete = 0
            """).fetchone()
            
            dashboard_data['defects_stats'] = {
                'total_defects': defects_stats[0],
                'affected_materials': defects_stats[1],
                'defect_types_count': defects_stats[2]
            }
            
            # Статистика лаборатории
            lab_stats = self.db_connection.execute("""
                SELECT 
                    COUNT(*) as total_requests,
                    COUNT(CASE WHEN status = 'Не отработана' THEN 1 END) as pending_requests,
                    COUNT(CASE WHEN status = 'Завершена' THEN 1 END) as completed_requests,
                    COUNT(CASE WHEN archived = 1 THEN 1 END) as archived_requests
                FROM lab_requests
            """).fetchone()
            
            dashboard_data['lab_stats'] = {
                'total_requests': lab_stats[0],
                'pending_requests': lab_stats[1],
                'completed_requests': lab_stats[2],
                'archived_requests': lab_stats[3]
            }
            
            # Топ поставщики
            top_suppliers = self.db_connection.execute("""
                SELECT 
                    s.name,
                    COUNT(m.id) as materials_count,
                    SUM(m.volume_weight_kg) as total_weight
                FROM Suppliers s
                LEFT JOIN Materials m ON s.id = m.supplier_id AND m.to_delete = 0
                GROUP BY s.id, s.name
                ORDER BY materials_count DESC
                LIMIT 5
            """).fetchall()
            
            dashboard_data['top_suppliers'] = [
                {'name': row[0], 'materials_count': row[1], 'total_weight': row[2] or 0}
                for row in top_suppliers
            ]
            
            # Последние поставки
            recent_supplies = self.db_connection.execute("""
                SELECT 
                    m.arrival_date,
                    s.name as supplier,
                    g.grade,
                    m.volume_weight_kg
                FROM Materials m
                LEFT JOIN Suppliers s ON m.supplier_id = s.id
                LEFT JOIN Grades g ON m.grade_id = g.id
                WHERE m.to_delete = 0
                ORDER BY m.arrival_date DESC
                LIMIT 10
            """).fetchall()
            
            dashboard_data['recent_supplies'] = [
                {
                    'date': row[0],
                    'supplier': row[1],
                    'grade': row[2],
                    'weight': row[3] or 0
                }
                for row in recent_supplies
            ]
            
            # Процент качества по поставщикам
            quality_by_suppliers = self.db_connection.execute("""
                SELECT 
                    s.name,
                    COUNT(m.id) as total_materials,
                    COUNT(d.id) as defects_count,
                    ROUND(
                        CASE 
                            WHEN COUNT(m.id) > 0 
                            THEN ((COUNT(m.id) - COUNT(d.id)) * 100.0 / COUNT(m.id))
                            ELSE 100 
                        END, 1
                    ) as quality_percentage
                FROM Suppliers s
                LEFT JOIN Materials m ON s.id = m.supplier_id AND m.to_delete = 0
                LEFT JOIN defects d ON m.id = d.material_id AND d.to_delete = 0
                GROUP BY s.id, s.name
                HAVING COUNT(m.id) > 0
                ORDER BY quality_percentage DESC
            """).fetchall()
            
            dashboard_data['quality_by_suppliers'] = [
                {
                    'supplier': row[0],
                    'total_materials': row[1],
                    'defects_count': row[2],
                    'quality_percentage': row[3]
                }
                for row in quality_by_suppliers
            ]
            
            logger.info("Создан дашборд с ключевыми метриками")
            return dashboard_data
            
        except Exception as e:
            self.handle_db_error(e, "создании дашборда")
            raise
    
    def create_chart_image(self, chart_type: str, data: Any, title: str = "", **kwargs) -> str:
        """
        Создает изображение графика и возвращает его в base64.
        
        Args:
            chart_type: Тип графика ('bar', 'line', 'pie', 'scatter')
            data: Данные для графика
            title: Заголовок графика
            **kwargs: Дополнительные параметры
            
        Returns:
            Строка в формате base64 с изображением графика
        """
        try:
            fig, ax = plt.subplots(figsize=(10, 6))
            fig.patch.set_facecolor('white')
            
            if chart_type == 'bar':
                if isinstance(data, pd.DataFrame):
                    x_col = kwargs.get('x_column', data.columns[0])
                    y_col = kwargs.get('y_column', data.columns[1])
                    ax.bar(data[x_col], data[y_col])
                    ax.set_xlabel(x_col)
                    ax.set_ylabel(y_col)
                
            elif chart_type == 'line':
                if isinstance(data, pd.DataFrame):
                    x_col = kwargs.get('x_column', data.columns[0])
                    y_col = kwargs.get('y_column', data.columns[1])
                    ax.plot(data[x_col], data[y_col], marker='o')
                    ax.set_xlabel(x_col)
                    ax.set_ylabel(y_col)
                    plt.xticks(rotation=45)
                
            elif chart_type == 'pie':
                if isinstance(data, pd.DataFrame):
                    labels_col = kwargs.get('labels_column', data.columns[0])
                    values_col = kwargs.get('values_column', data.columns[1])
                    ax.pie(data[values_col], labels=data[labels_col], autopct='%1.1f%%')
                
            elif chart_type == 'scatter':
                if isinstance(data, pd.DataFrame):
                    x_col = kwargs.get('x_column', data.columns[0])
                    y_col = kwargs.get('y_column', data.columns[1])
                    ax.scatter(data[x_col], data[y_col])
                    ax.set_xlabel(x_col)
                    ax.set_ylabel(y_col)
            
            ax.set_title(title)
            plt.tight_layout()
            
            # Сохраняем график в base64
            buffer = io.BytesIO()
            plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
            buffer.seek(0)
            image_base64 = base64.b64encode(buffer.getvalue()).decode()
            plt.close(fig)
            
            return image_base64
            
        except Exception as e:
            logger.error(f"Ошибка при создании графика: {e}")
            plt.close('all')
            return ""
    
    def create_quality_trend_chart(self, days: int = 90) -> str:
        """
        Создает график тренда качества за указанный период.
        
        Args:
            days: Количество дней для анализа
            
        Returns:
            Base64 строка с изображением графика
        """
        try:
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            
            # Получаем данные по дням
            query = """
                SELECT 
                    DATE(m.arrival_date) as date,
                    COUNT(m.id) as total_materials,
                    COUNT(d.id) as defects_count,
                    ROUND(
                        CASE 
                            WHEN COUNT(m.id) > 0 
                            THEN ((COUNT(m.id) - COUNT(d.id)) * 100.0 / COUNT(m.id))
                            ELSE 100 
                        END, 1
                    ) as quality_percentage
                FROM Materials m
                LEFT JOIN defects d ON m.id = d.material_id AND d.to_delete = 0
                WHERE m.arrival_date >= ? AND m.to_delete = 0
                GROUP BY DATE(m.arrival_date)
                ORDER BY DATE(m.arrival_date)
            """
            
            df = pd.read_sql_query(query, self.db_connection, params=[start_date])
            
            if df.empty:
                return ""
            
            # Создаем график
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
            fig.patch.set_facecolor('white')
            
            # График качества
            df['date'] = pd.to_datetime(df['date'])
            ax1.plot(df['date'], df['quality_percentage'], marker='o', linewidth=2, markersize=4)
            ax1.set_title('Динамика качества материалов (%)', fontsize=14, fontweight='bold')
            ax1.set_ylabel('Процент качества (%)')
            ax1.grid(True, alpha=0.3)
            ax1.set_ylim(0, 105)
            
            # График количества поставок
            ax2.bar(df['date'], df['total_materials'], alpha=0.7, color='skyblue')
            ax2.set_title('Количество поставок по дням', fontsize=14, fontweight='bold')
            ax2.set_ylabel('Количество материалов')
            ax2.set_xlabel('Дата')
            ax2.grid(True, alpha=0.3)
            
            # Форматирование дат на оси X
            for ax in [ax1, ax2]:
                ax.tick_params(axis='x', rotation=45)
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
                ax.xaxis.set_major_locator(mdates.WeekdayLocator())
            
            plt.tight_layout()
            
            # Сохраняем график в base64
            buffer = io.BytesIO()
            plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
            buffer.seek(0)
            image_base64 = base64.b64encode(buffer.getvalue()).decode()
            plt.close(fig)
            
            return image_base64
            
        except Exception as e:
            logger.error(f"Ошибка при создании графика тренда качества: {e}")
            plt.close('all')
            return ""
    
    def create_suppliers_comparison_chart(self) -> str:
        """
        Создает график сравнения поставщиков по качеству и объемам.
        
        Returns:
            Base64 строка с изображением графика
        """
        try:
            # Получаем данные по поставщикам
            quality_data = self.create_quality_analysis_report()
            
            if quality_data.empty:
                return ""
            
            # Создаем график
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
            fig.patch.set_facecolor('white')
            
            # График процента брака
            suppliers = quality_data['Поставщик']
            defect_percent = quality_data['Процент брака (%)']
            total_materials = quality_data['Всего материалов']
            
            # Столбчатая диаграмма процента брака
            bars1 = ax1.bar(suppliers, defect_percent, color='lightcoral', alpha=0.7)
            ax1.set_title('Процент брака по поставщикам', fontsize=14, fontweight='bold')
            ax1.set_ylabel('Процент брака (%)')
            ax1.tick_params(axis='x', rotation=45)
            ax1.grid(True, alpha=0.3, axis='y')
            
            # Добавляем значения на столбцы
            for bar, value in zip(bars1, defect_percent):
                if value > 0:
                    ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1,
                            f'{value}%', ha='center', va='bottom', fontweight='bold')
            
            # Круговая диаграмма распределения материалов
            materials_data = quality_data[quality_data['Всего материалов'] > 0]
            if not materials_data.empty:
                ax2.pie(materials_data['Всего материалов'], 
                       labels=materials_data['Поставщик'],
                       autopct='%1.1f%%', startangle=90)
                ax2.set_title('Распределение материалов по поставщикам', 
                             fontsize=14, fontweight='bold')
            
            plt.tight_layout()
            
            # Сохраняем график в base64
            buffer = io.BytesIO()
            plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
            buffer.seek(0)
            image_base64 = base64.b64encode(buffer.getvalue()).decode()
            plt.close(fig)
            
            return image_base64
            
        except Exception as e:
            logger.error(f"Ошибка при создании графика сравнения поставщиков: {e}")
            plt.close('all')
            return ""
    
    def handle_db_error(self, error: Exception, operation: str) -> None:
        """
        Обработка ошибок базы данных.
        
        Args:
            error: Исключение
            operation: Описание операции
        """
        logger.error(f"Ошибка БД при {operation}: {error}")
        raise BusinessLogicError(
            f"Ошибка при {operation}: {error}",
            original_error=error,
            suggestions=["Проверьте соединение с базой данных"]
        ) 
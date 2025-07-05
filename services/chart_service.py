"""
Сервис для создания и управления графиками и диаграммами.
Поддерживает как статические (matplotlib), так и интерактивные (plotly) графики.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Union
import sqlite3
import os
import io
import base64
import json

# Импорты для статических графиков (matplotlib)
import matplotlib
matplotlib.use('Agg')  # Использовать non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.figure import Figure
import seaborn as sns

# Импорты для интерактивных графиков (plotly)
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import plotly.offline as pyo
from plotly.graph_objs import Figure as PlotlyFigure

from utils.logger import get_logger
from utils.exceptions import ValidationError, BusinessLogicError

logger = get_logger('services.chart')

# Настройка стилей
plt.style.use('seaborn-v0_8')
sns.set_palette("husl")

# Цветовые схемы
CHART_COLORS = {
    'primary': ['#3498db', '#e74c3c', '#2ecc71', '#f39c12', '#9b59b6', '#1abc9c'],
    'quality': ['#27ae60', '#f39c12', '#e74c3c'],
    'heatmap': 'RdYlBu_r',
    'sequential': 'viridis'
}


class ChartService:
    """
    Сервис для создания различных типов графиков и диаграмм.
    """
    
    def __init__(self, db_connection: sqlite3.Connection):
        """
        Инициализация сервиса графиков.
        
        Args:
            db_connection: Соединение с базой данных
        """
        self.db_connection = db_connection
        self.output_dir = "reports/charts"
        self._ensure_output_dir()
    
    def _ensure_output_dir(self):
        """Создает директорию для графиков если она не существует."""
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
    
    # ===== СТАТИЧЕСКИЕ ГРАФИКИ (MATPLOTLIB) =====
    
    def create_matplotlib_chart(self, 
                               chart_type: str, 
                               data: pd.DataFrame, 
                               title: str = "",
                               x_column: str = None,
                               y_column: str = None,
                               figsize: Tuple[int, int] = (12, 8),
                               **kwargs) -> str:
        """
        Создает статический график с помощью matplotlib.
        
        Args:
            chart_type: Тип графика ('bar', 'line', 'pie', 'scatter', 'hist', 'box')
            data: Данные для графика
            title: Заголовок графика
            x_column: Название колонки для оси X
            y_column: Название колонки для оси Y
            figsize: Размер фигуры
            **kwargs: Дополнительные параметры
            
        Returns:
            Base64 строка с изображением графика
        """
        try:
            fig, ax = plt.subplots(figsize=figsize)
            fig.patch.set_facecolor('white')
            
            if data.empty:
                ax.text(0.5, 0.5, 'Нет данных для отображения', 
                       ha='center', va='center', transform=ax.transAxes, fontsize=14)
                ax.set_title(title)
                return self._save_matplotlib_to_base64(fig)
            
            x_col = x_column or data.columns[0]
            y_col = y_column or (data.columns[1] if len(data.columns) > 1 else data.columns[0])
            
            if chart_type == 'bar':
                bars = ax.bar(data[x_col], data[y_col], 
                             color=CHART_COLORS['primary'][:len(data)], alpha=0.8)
                ax.set_xlabel(x_col)
                ax.set_ylabel(y_col)
                
                # Добавляем значения на столбцы
                for bar in bars:
                    height = bar.get_height()
                    if height > 0:
                        ax.text(bar.get_x() + bar.get_width()/2., height,
                               f'{height:.1f}', ha='center', va='bottom')
                
                plt.xticks(rotation=45, ha='right')
                
            elif chart_type == 'line':
                ax.plot(data[x_col], data[y_col], marker='o', linewidth=2, markersize=6,
                       color=CHART_COLORS['primary'][0])
                ax.set_xlabel(x_col)
                ax.set_ylabel(y_col)
                ax.grid(True, alpha=0.3)
                plt.xticks(rotation=45, ha='right')
                
            elif chart_type == 'pie':
                wedges, texts, autotexts = ax.pie(data[y_col], labels=data[x_col], 
                                                 autopct='%1.1f%%', startangle=90,
                                                 colors=CHART_COLORS['primary'])
                # Улучшаем читаемость
                for autotext in autotexts:
                    autotext.set_color('white')
                    autotext.set_fontweight('bold')
                
            elif chart_type == 'scatter':
                scatter = ax.scatter(data[x_col], data[y_col], 
                                   c=CHART_COLORS['primary'][0], alpha=0.6, s=50)
                ax.set_xlabel(x_col)
                ax.set_ylabel(y_col)
                ax.grid(True, alpha=0.3)
                
            elif chart_type == 'hist':
                ax.hist(data[x_col], bins=kwargs.get('bins', 20), 
                       color=CHART_COLORS['primary'][0], alpha=0.7, edgecolor='black')
                ax.set_xlabel(x_col)
                ax.set_ylabel('Частота')
                ax.grid(True, alpha=0.3)
                
            elif chart_type == 'box':
                box_data = [data[col].dropna() for col in data.select_dtypes(include=[np.number]).columns]
                box_labels = data.select_dtypes(include=[np.number]).columns
                ax.boxplot(box_data, labels=box_labels)
                ax.set_ylabel('Значения')
                plt.xticks(rotation=45, ha='right')
                ax.grid(True, alpha=0.3)
            
            ax.set_title(title, fontsize=16, fontweight='bold', pad=20)
            plt.tight_layout()
            
            return self._save_matplotlib_to_base64(fig)
            
        except Exception as e:
            logger.error(f"Ошибка при создании matplotlib графика: {e}")
            plt.close('all')
            return ""
    
    def create_heatmap(self, 
                      data: pd.DataFrame, 
                      title: str = "Тепловая карта",
                      x_column: str = None,
                      y_column: str = None,
                      value_column: str = None,
                      figsize: Tuple[int, int] = (12, 8)) -> str:
        """
        Создает тепловую карту дефектов или других данных.
        
        Args:
            data: Данные для тепловой карты
            title: Заголовок
            x_column: Колонка для оси X
            y_column: Колонка для оси Y
            value_column: Колонка со значениями
            figsize: Размер фигуры
            
        Returns:
            Base64 строка с изображением
        """
        try:
            fig, ax = plt.subplots(figsize=figsize)
            fig.patch.set_facecolor('white')
            
            if data.empty:
                ax.text(0.5, 0.5, 'Нет данных для тепловой карты', 
                       ha='center', va='center', transform=ax.transAxes, fontsize=14)
                ax.set_title(title)
                return self._save_matplotlib_to_base64(fig)
            
            # Если данные уже в виде матрицы
            if x_column is None and y_column is None:
                heatmap_data = data.select_dtypes(include=[np.number])
                sns.heatmap(heatmap_data, annot=True, cmap=CHART_COLORS['heatmap'], 
                           fmt='.1f', ax=ax, cbar_kws={'label': 'Значение'})
            else:
                # Создаем pivot table для тепловой карты
                x_col = x_column or data.columns[0]
                y_col = y_column or data.columns[1]
                val_col = value_column or data.columns[2]
                
                pivot_data = data.pivot_table(values=val_col, index=y_col, 
                                            columns=x_col, aggfunc='sum', fill_value=0)
                
                sns.heatmap(pivot_data, annot=True, cmap=CHART_COLORS['heatmap'], 
                           fmt='.1f', ax=ax, cbar_kws={'label': val_col})
            
            ax.set_title(title, fontsize=16, fontweight='bold', pad=20)
            plt.tight_layout()
            
            return self._save_matplotlib_to_base64(fig)
            
        except Exception as e:
            logger.error(f"Ошибка при создании тепловой карты: {e}")
            plt.close('all')
            return ""
    
    def create_multi_chart(self, 
                          charts_config: List[Dict[str, Any]], 
                          title: str = "Комбинированный график",
                          figsize: Tuple[int, int] = (15, 10)) -> str:
        """
        Создает комбинированный график с несколькими подграфиками.
        
        Args:
            charts_config: Список конфигураций графиков
            title: Общий заголовок
            figsize: Размер фигуры
            
        Returns:
            Base64 строка с изображением
        """
        try:
            num_charts = len(charts_config)
            rows = (num_charts + 1) // 2
            cols = 2 if num_charts > 1 else 1
            
            fig, axes = plt.subplots(rows, cols, figsize=figsize)
            fig.patch.set_facecolor('white')
            
            if num_charts == 1:
                axes = [axes]
            elif rows == 1:
                axes = axes if isinstance(axes, list) else [axes]
            else:
                axes = axes.flatten()
            
            for i, config in enumerate(charts_config):
                if i >= len(axes):
                    break
                    
                ax = axes[i]
                data = config['data']
                chart_type = config['type']
                chart_title = config.get('title', f'График {i+1}')
                
                if data.empty:
                    ax.text(0.5, 0.5, 'Нет данных', ha='center', va='center', 
                           transform=ax.transAxes)
                    ax.set_title(chart_title)
                    continue
                
                x_col = config.get('x_column', data.columns[0])
                y_col = config.get('y_column', data.columns[1] if len(data.columns) > 1 else data.columns[0])
                
                if chart_type == 'bar':
                    ax.bar(data[x_col], data[y_col], color=CHART_COLORS['primary'][i % len(CHART_COLORS['primary'])])
                elif chart_type == 'line':
                    ax.plot(data[x_col], data[y_col], marker='o', color=CHART_COLORS['primary'][i % len(CHART_COLORS['primary'])])
                elif chart_type == 'pie':
                    ax.pie(data[y_col], labels=data[x_col], autopct='%1.1f%%')
                
                ax.set_title(chart_title, fontweight='bold')
                ax.grid(True, alpha=0.3)
            
            # Скрываем лишние подграфики
            for i in range(num_charts, len(axes)):
                axes[i].set_visible(False)
            
            fig.suptitle(title, fontsize=18, fontweight='bold')
            plt.tight_layout()
            
            return self._save_matplotlib_to_base64(fig)
            
        except Exception as e:
            logger.error(f"Ошибка при создании комбинированного графика: {e}")
            plt.close('all')
            return ""
    
    # ===== ИНТЕРАКТИВНЫЕ ГРАФИКИ (PLOTLY) =====
    
    def create_plotly_chart(self, 
                           chart_type: str, 
                           data: pd.DataFrame, 
                           title: str = "",
                           x_column: str = None,
                           y_column: str = None,
                           **kwargs) -> str:
        """
        Создает интерактивный график с помощью plotly.
        
        Args:
            chart_type: Тип графика ('bar', 'line', 'scatter', 'pie', 'box', 'heatmap')
            data: Данные для графика
            title: Заголовок графика
            x_column: Название колонки для оси X
            y_column: Название колонки для оси Y
            **kwargs: Дополнительные параметры
            
        Returns:
            HTML строка с интерактивным графиком
        """
        try:
            if data.empty:
                fig = go.Figure()
                fig.add_annotation(text="Нет данных для отображения", 
                                 xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
                fig.update_layout(title=title)
                return pyo.plot(fig, output_type='div', include_plotlyjs=True)
            
            x_col = x_column or data.columns[0]
            y_col = y_column or (data.columns[1] if len(data.columns) > 1 else data.columns[0])
            
            if chart_type == 'bar':
                fig = px.bar(data, x=x_col, y=y_col, title=title,
                           color_discrete_sequence=CHART_COLORS['primary'])
                
            elif chart_type == 'line':
                fig = px.line(data, x=x_col, y=y_col, title=title, markers=True,
                            color_discrete_sequence=CHART_COLORS['primary'])
                
            elif chart_type == 'scatter':
                fig = px.scatter(data, x=x_col, y=y_col, title=title,
                               color_discrete_sequence=CHART_COLORS['primary'])
                
            elif chart_type == 'pie':
                fig = px.pie(data, values=y_col, names=x_col, title=title,
                           color_discrete_sequence=CHART_COLORS['primary'])
                
            elif chart_type == 'box':
                numeric_cols = data.select_dtypes(include=[np.number]).columns
                fig = go.Figure()
                for i, col in enumerate(numeric_cols):
                    fig.add_trace(go.Box(y=data[col], name=col, 
                                       marker_color=CHART_COLORS['primary'][i % len(CHART_COLORS['primary'])]))
                fig.update_layout(title=title)
                
            elif chart_type == 'heatmap':
                if len(data.columns) >= 3:
                    x_col = x_column or data.columns[0]
                    y_col = y_column or data.columns[1]
                    z_col = kwargs.get('z_column', data.columns[2])
                    
                    pivot_data = data.pivot_table(values=z_col, index=y_col, 
                                                columns=x_col, aggfunc='sum', fill_value=0)
                    
                    fig = px.imshow(pivot_data, title=title, 
                                  color_continuous_scale='RdYlBu_r', aspect="auto")
                else:
                    correlation_matrix = data.select_dtypes(include=[np.number]).corr()
                    fig = px.imshow(correlation_matrix, title=title,
                                  color_continuous_scale='RdYlBu_r', aspect="auto")
            
            # Настройка макета
            fig.update_layout(
                font=dict(size=12),
                plot_bgcolor='white',
                paper_bgcolor='white',
                showlegend=True,
                margin=dict(l=50, r=50, t=80, b=50)
            )
            
            return pyo.plot(fig, output_type='div', include_plotlyjs=True)
            
        except Exception as e:
            logger.error(f"Ошибка при создании plotly графика: {e}")
            return f"<div>Ошибка при создании графика: {e}</div>"
    
    def create_interactive_supply_chart(self, 
                                      date_from: str = None, 
                                      date_to: str = None) -> str:
        """
        Создает интерактивный график поставок с детализацией.
        
        Args:
            date_from: Дата начала периода
            date_to: Дата окончания периода
            
        Returns:
            HTML строка с интерактивным графиком
        """
        try:
            # Получаем данные о поставках
            query = """
                SELECT 
                    DATE(m.arrival_date) as date,
                    s.name as supplier,
                    g.grade as grade,
                    rt.type as rolling_type,
                    COUNT(m.id) as materials_count,
                    SUM(m.volume_weight_kg) as total_weight,
                    SUM(m.volume_length_mm) as total_length
                FROM Materials m
                LEFT JOIN Suppliers s ON m.supplier_id = s.id
                LEFT JOIN Grades g ON m.grade_id = g.id
                LEFT JOIN RollingTypes rt ON m.rolling_type_id = rt.id
                WHERE m.to_delete = 0
            """
            
            params = []
            if date_from:
                query += " AND m.arrival_date >= ?"
                params.append(date_from)
            if date_to:
                query += " AND m.arrival_date <= ?"
                params.append(date_to)
            
            query += " GROUP BY DATE(m.arrival_date), s.name, g.grade, rt.type ORDER BY DATE(m.arrival_date)"
            
            data = pd.read_sql_query(query, self.db_connection, params=params)
            
            if data.empty:
                fig = go.Figure()
                fig.add_annotation(text="Нет данных о поставках за указанный период", 
                                 xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
                fig.update_layout(title="Интерактивный график поставок")
                return pyo.plot(fig, output_type='div', include_plotlyjs=True)
            
            # Создаем subplot с несколькими графиками
            fig = make_subplots(
                rows=3, cols=1,
                subplot_titles=('Количество поставок', 'Общий вес (кг)', 'Поставки по поставщикам'),
                vertical_spacing=0.1
            )
            
            # График 1: Количество поставок по дням
            daily_data = data.groupby('date').agg({
                'materials_count': 'sum',
                'total_weight': 'sum'
            }).reset_index()
            
            fig.add_trace(
                go.Scatter(x=daily_data['date'], y=daily_data['materials_count'],
                          mode='lines+markers', name='Количество поставок',
                          line=dict(color=CHART_COLORS['primary'][0], width=3),
                          hovertemplate='Дата: %{x}<br>Поставок: %{y}<extra></extra>'),
                row=1, col=1
            )
            
            # График 2: Общий вес по дням
            fig.add_trace(
                go.Scatter(x=daily_data['date'], y=daily_data['total_weight'],
                          mode='lines+markers', name='Общий вес',
                          line=dict(color=CHART_COLORS['primary'][1], width=3),
                          hovertemplate='Дата: %{x}<br>Вес: %{y:.1f} кг<extra></extra>'),
                row=2, col=1
            )
            
            # График 3: Поставки по поставщикам (stacked bar)
            supplier_data = data.groupby(['date', 'supplier']).agg({
                'materials_count': 'sum'
            }).reset_index()
            
            suppliers = supplier_data['supplier'].unique()
            for i, supplier in enumerate(suppliers):
                supplier_subset = supplier_data[supplier_data['supplier'] == supplier]
                fig.add_trace(
                    go.Bar(x=supplier_subset['date'], y=supplier_subset['materials_count'],
                          name=supplier, 
                          marker_color=CHART_COLORS['primary'][i % len(CHART_COLORS['primary'])],
                          hovertemplate=f'Поставщик: {supplier}<br>Дата: %{{x}}<br>Поставок: %{{y}}<extra></extra>'),
                    row=3, col=1
                )
            
            # Настройка макета
            fig.update_layout(
                height=1000,
                title_text="Интерактивный анализ поставок материалов",
                title_x=0.5,
                font=dict(size=12),
                plot_bgcolor='white',
                paper_bgcolor='white',
                hovermode='closest'
            )
            
            # Настройка осей
            fig.update_xaxes(title_text="Дата", row=3, col=1)
            fig.update_yaxes(title_text="Количество", row=1, col=1)
            fig.update_yaxes(title_text="Вес (кг)", row=2, col=1)
            fig.update_yaxes(title_text="Поставки", row=3, col=1)
            
            return pyo.plot(fig, output_type='div', include_plotlyjs=True)
            
        except Exception as e:
            logger.error(f"Ошибка при создании интерактивного графика поставок: {e}")
            return f"<div>Ошибка при создании графика: {e}</div>"
    
    def create_defects_heatmap(self, 
                              date_from: str = None, 
                              date_to: str = None) -> str:
        """
        Создает тепловую карту дефектов по поставщикам и маркам.
        
        Args:
            date_from: Дата начала периода
            date_to: Дата окончания периода
            
        Returns:
            HTML строка с интерактивной тепловой картой
        """
        try:
            # Получаем данные о дефектах
            query = """
                SELECT 
                    s.name as supplier,
                    g.grade as grade,
                    d.defect_type,
                    COUNT(d.id) as defects_count,
                    COUNT(DISTINCT m.id) as affected_materials
                FROM defects d
                JOIN Materials m ON d.material_id = m.id
                JOIN Suppliers s ON m.supplier_id = s.id
                JOIN Grades g ON m.grade_id = g.id
                WHERE d.to_delete = 0
            """
            
            params = []
            if date_from:
                query += " AND m.arrival_date >= ?"
                params.append(date_from)
            if date_to:
                query += " AND m.arrival_date <= ?"
                params.append(date_to)
            
            query += " GROUP BY s.name, g.grade, d.defect_type"
            
            data = pd.read_sql_query(query, self.db_connection, params=params)
            
            if data.empty:
                fig = go.Figure()
                fig.add_annotation(text="Нет данных о дефектах за указанный период", 
                                 xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
                fig.update_layout(title="Тепловая карта дефектов")
                return pyo.plot(fig, output_type='div', include_plotlyjs=True)
            
            # Создаем тепловую карту поставщик x марка
            heatmap_data = data.groupby(['supplier', 'grade']).agg({
                'defects_count': 'sum'
            }).reset_index()
            
            pivot_data = heatmap_data.pivot(index='supplier', columns='grade', 
                                          values='defects_count').fillna(0)
            
            fig = go.Figure(data=go.Heatmap(
                z=pivot_data.values,
                x=pivot_data.columns,
                y=pivot_data.index,
                colorscale='RdYlBu_r',
                hoverongaps=False,
                hovertemplate='Поставщик: %{y}<br>Марка: %{x}<br>Дефектов: %{z}<extra></extra>'
            ))
            
            fig.update_layout(
                title="Тепловая карта дефектов по поставщикам и маркам",
                title_x=0.5,
                xaxis_title="Марка материала",
                yaxis_title="Поставщик",
                font=dict(size=12),
                plot_bgcolor='white',
                paper_bgcolor='white'
            )
            
            return pyo.plot(fig, output_type='div', include_plotlyjs=True)
            
        except Exception as e:
            logger.error(f"Ошибка при создании тепловой карты дефектов: {e}")
            return f"<div>Ошибка при создании тепловой карты: {e}</div>"
    
    # ===== ЭКСПОРТ ГРАФИКОВ =====
    
    def export_chart_to_file(self, 
                            chart_base64: str, 
                            filename: str, 
                            format: str = 'png') -> str:
        """
        Экспортирует график в файл.
        
        Args:
            chart_base64: График в формате base64
            filename: Имя файла без расширения
            format: Формат файла ('png', 'jpg', 'svg', 'pdf')
            
        Returns:
            Путь к сохраненному файлу
        """
        try:
            if not chart_base64:
                raise ValueError("Нет данных графика для экспорта")
            
            # Декодируем base64
            image_data = base64.b64decode(chart_base64)
            
            # Формируем путь к файлу
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            file_path = os.path.join(self.output_dir, f"{filename}_{timestamp}.{format}")
            
            # Сохраняем файл
            with open(file_path, 'wb') as f:
                f.write(image_data)
            
            logger.info(f"График экспортирован в файл: {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"Ошибка при экспорте графика: {e}")
            raise BusinessLogicError(f"Не удалось экспортировать график: {e}")
    
    def export_plotly_chart(self, 
                           fig: PlotlyFigure, 
                           filename: str, 
                           format: str = 'png',
                           width: int = 1200,
                           height: int = 800) -> str:
        """
        Экспортирует plotly график в файл.
        
        Args:
            fig: Plotly фигура
            filename: Имя файла без расширения
            format: Формат файла ('png', 'jpg', 'svg', 'pdf', 'html')
            width: Ширина изображения
            height: Высота изображения
            
        Returns:
            Путь к сохраненному файлу
        """
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            file_path = os.path.join(self.output_dir, f"{filename}_{timestamp}.{format}")
            
            if format == 'html':
                pyo.plot(fig, filename=file_path, auto_open=False)
            else:
                # Для статических форматов нужен kaleido
                fig.write_image(file_path, format=format, width=width, height=height)
            
            logger.info(f"Plotly график экспортирован в файл: {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"Ошибка при экспорте plotly графика: {e}")
            raise BusinessLogicError(f"Не удалось экспортировать график: {e}")
    
    # ===== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ =====
    
    def _save_matplotlib_to_base64(self, fig) -> str:
        """
        Сохраняет matplotlib график в base64.
        
        Args:
            fig: Matplotlib фигура
            
        Returns:
            Base64 строка с изображением
        """
        try:
            buffer = io.BytesIO()
            fig.savefig(buffer, format='png', dpi=150, bbox_inches='tight', 
                       facecolor='white', edgecolor='none')
            buffer.seek(0)
            image_base64 = base64.b64encode(buffer.getvalue()).decode()
            plt.close(fig)
            return image_base64
            
        except Exception as e:
            logger.error(f"Ошибка при сохранении matplotlib графика: {e}")
            plt.close(fig)
            return ""
    
    def get_chart_types(self) -> Dict[str, List[str]]:
        """
        Возвращает список доступных типов графиков.
        
        Returns:
            Словарь с типами графиков
        """
        return {
            'matplotlib': ['bar', 'line', 'pie', 'scatter', 'hist', 'box', 'heatmap'],
            'plotly': ['bar', 'line', 'scatter', 'pie', 'box', 'heatmap', 'interactive_supply', 'defects_heatmap']
        }
    
    def get_color_schemes(self) -> Dict[str, List[str]]:
        """
        Возвращает доступные цветовые схемы.
        
        Returns:
            Словарь с цветовыми схемами
        """
        return CHART_COLORS 
"""
Окно статистического анализа результатов испытаний.

Предоставляет интерфейс для:
- Выбора параметров анализа
- Просмотра основных статистик
- Анализа выбросов
- Контрольных карт Шухарта
- Показателей воспроизводимости
"""

import sys
from datetime import datetime
from typing import Dict, List, Any, Optional

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem, QTabWidget,
    QTextEdit, QSplitter, QMessageBox, QProgressBar, QFrame,
    QScrollArea
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QPixmap

import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.dates as mdates
import numpy as np

from services.statistics_service import StatisticsService
from utils.logger import get_logger

logger = get_logger(__name__)

# Настройка matplotlib для корректного отображения русского текста
plt.rcParams['font.family'] = ['DejaVu Sans', 'Arial', 'sans-serif']
plt.rcParams['axes.unicode_minus'] = False


class StatisticsAnalysisThread(QThread):
    """Поток для выполнения статистического анализа."""
    
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    progress = pyqtSignal(int)
    
    def __init__(self, statistics_service: StatisticsService, 
                 test_name: str, material_grade: Optional[str], 
                 days_back: int, specs: Dict[str, Optional[float]]):
        super().__init__()
        self.statistics_service = statistics_service
        self.test_name = test_name
        self.material_grade = material_grade
        self.days_back = days_back
        self.specs = specs
    
    def run(self):
        """Выполнение анализа в отдельном потоке."""
        try:
            self.progress.emit(10)
            
            # Получение данных
            data = self.statistics_service.get_test_results_data(
                self.test_name, self.material_grade, self.days_back
            )
            
            if not data:
                self.error.emit("Нет данных для анализа")
                return
            
            self.progress.emit(30)
            
            values = [item['value'] for item in data]
            
            # Основные статистики
            basic_stats = self.statistics_service.calculate_basic_statistics(values)
            self.progress.emit(50)
            
            # Анализ выбросов
            outliers_analysis = self.statistics_service.detect_outliers_grubbs(values)
            self.progress.emit(70)
            
            # Контрольные карты
            control_limits = self.statistics_service.calculate_control_chart_limits(values, 'X')
            control_rules = self.statistics_service.check_control_chart_rules(values, control_limits)
            
            mr_limits = self.statistics_service.calculate_control_chart_limits(values, 'MR')
            self.progress.emit(85)
            
            # Показатели воспроизводимости
            capability = self.statistics_service.calculate_process_capability(
                values, self.specs.get('lower'), self.specs.get('upper')
            )
            self.progress.emit(100)
            
            result = {
                'data': data,
                'values': values,
                'basic_stats': basic_stats,
                'outliers': outliers_analysis,
                'control_limits': control_limits,
                'control_rules': control_rules,
                'mr_limits': mr_limits,
                'capability': capability
            }
            
            self.finished.emit(result)
            
        except Exception as e:
            logger.error(f"Ошибка в потоке анализа: {e}")
            self.error.emit(str(e))


class StatisticsPlotWidget(QFrame):
    """Виджет для отображения статистических графиков."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameStyle(QFrame.StyledPanel)
        
        layout = QVBoxLayout(self)
        
        self.figure = Figure(figsize=(12, 8))
        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas)
        
    def clear_plots(self):
        """Очистка всех графиков."""
        self.figure.clear()
        self.canvas.draw()
    
    def plot_control_chart(self, data: List[Dict], control_limits: Dict, 
                          mr_limits: Dict, title: str):
        """Построение контрольной карты."""
        if not data or not control_limits:
            return
        
        self.figure.clear()
        
        # Подготовка данных
        dates = [datetime.strptime(item['date'], '%Y-%m-%d') for item in data]
        values = [item['value'] for item in data]
        
        # Расчет скользящих размахов
        moving_ranges = []
        mr_dates = []
        for i in range(1, len(values)):
            moving_ranges.append(abs(values[i] - values[i-1]))
            mr_dates.append(dates[i])
        
        # Создание подграфиков
        ax1 = self.figure.add_subplot(2, 1, 1)
        ax2 = self.figure.add_subplot(2, 1, 2)
        
        # График индивидуальных значений
        ax1.plot(dates, values, 'bo-', linewidth=1, markersize=4, label='Значения')
        ax1.axhline(y=control_limits['center_line'], color='g', linestyle='-', 
                   linewidth=2, label='Центральная линия')
        ax1.axhline(y=control_limits['ucl'], color='r', linestyle='--', 
                   linewidth=2, label='ВКГ')
        ax1.axhline(y=control_limits['lcl'], color='r', linestyle='--', 
                   linewidth=2, label='НКГ')
        
        ax1.set_title(f'Контрольная карта индивидуальных значений - {title}')
        ax1.set_ylabel('Значение')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # График скользящих размахов
        if moving_ranges and mr_limits:
            ax2.plot(mr_dates, moving_ranges, 'ro-', linewidth=1, markersize=4, 
                    label='Скользящий размах')
            ax2.axhline(y=mr_limits['center_line'], color='g', linestyle='-', 
                       linewidth=2, label='Центральная линия')
            ax2.axhline(y=mr_limits['ucl'], color='r', linestyle='--', 
                       linewidth=2, label='ВКГ')
            ax2.axhline(y=mr_limits['lcl'], color='r', linestyle='--', 
                       linewidth=2, label='НКГ')
        
        ax2.set_title('Карта скользящих размахов')
        ax2.set_xlabel('Дата')
        ax2.set_ylabel('Размах')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        # Форматирование дат на оси X
        for ax in [ax1, ax2]:
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m'))
            ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, len(dates)//10)))
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
        
        self.figure.tight_layout()
        self.canvas.draw()
    
    def plot_histogram(self, values: List[float], basic_stats: Dict, 
                      outliers: Dict, title: str):
        """Построение гистограммы с анализом нормальности."""
        if not values:
            return
        
        self.figure.clear()
        ax = self.figure.add_subplot(1, 1, 1)
        
        # Гистограмма
        n_bins = min(20, max(5, int(np.sqrt(len(values)))))
        counts, bins, patches = ax.hist(values, bins=n_bins, alpha=0.7, 
                                       color='skyblue', edgecolor='black')
        
        # Вертикальные линии для основных статистик
        mean_val = basic_stats.get('mean', 0)
        median_val = basic_stats.get('median', 0)
        std_val = basic_stats.get('std', 0)
        
        ax.axvline(mean_val, color='red', linestyle='--', linewidth=2, 
                  label=f'Среднее: {mean_val:.2f}')
        ax.axvline(median_val, color='green', linestyle='--', linewidth=2, 
                  label=f'Медиана: {median_val:.2f}')
        
        # Границы ±3σ
        if std_val > 0:
            ax.axvline(mean_val - 3*std_val, color='orange', linestyle=':', 
                      linewidth=2, label='-3σ')
            ax.axvline(mean_val + 3*std_val, color='orange', linestyle=':', 
                      linewidth=2, label='+3σ')
        
        # Отметка выбросов
        if outliers and outliers.get('outliers'):
            outlier_values = [o['value'] for o in outliers['outliers']]
            ax.scatter(outlier_values, [0] * len(outlier_values), 
                      color='red', s=100, marker='x', linewidth=3, 
                      label=f'Выбросы ({len(outlier_values)})')
        
        ax.set_title(f'Гистограмма - {title}')
        ax.set_xlabel('Значение')
        ax.set_ylabel('Частота')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        self.figure.tight_layout()
        self.canvas.draw()


class StatisticsWindow(QDialog):
    """Главное окно статистического анализа."""
    
    def __init__(self, statistics_service: StatisticsService, parent=None):
        super().__init__(parent)
        self.statistics_service = statistics_service
        self.analysis_thread = None
        self.current_results = None
        
        self.setWindowTitle('Статистический анализ результатов испытаний')
        self.setModal(True)
        self.resize(1200, 800)
        
        self._setup_ui()
        self._load_initial_data()
    
    def _setup_ui(self):
        """Настройка пользовательского интерфейса."""
        layout = QVBoxLayout(self)
        
        # Панель параметров
        params_group = self._create_parameters_group()
        layout.addWidget(params_group)
        
        # Прогресс-бар
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Основной контент (табы)
        self.tab_widget = QTabWidget()
        
        # Вкладка с основными статистиками
        self.stats_tab = self._create_statistics_tab()
        self.tab_widget.addTab(self.stats_tab, 'Основные статистики')
        
        # Вкладка с графиками
        self.plots_tab = self._create_plots_tab()
        self.tab_widget.addTab(self.plots_tab, 'Графики')
        
        # Вкладка с анализом выбросов
        self.outliers_tab = self._create_outliers_tab()
        self.tab_widget.addTab(self.outliers_tab, 'Выбросы')
        
        # Вкладка с контрольными картами
        self.control_tab = self._create_control_tab()
        self.tab_widget.addTab(self.control_tab, 'Контрольные карты')
        
        # Вкладка с воспроизводимостью
        self.capability_tab = self._create_capability_tab()
        self.tab_widget.addTab(self.capability_tab, 'Воспроизводимость')
        
        layout.addWidget(self.tab_widget)
    
    def _create_parameters_group(self) -> QGroupBox:
        """Создание группы параметров анализа."""
        group = QGroupBox('Параметры анализа')
        layout = QFormLayout(group)
        
        # Выбор теста
        self.test_combo = QComboBox()
        layout.addRow('Тест:', self.test_combo)
        
        # Выбор марки материала
        self.material_combo = QComboBox()
        self.material_combo.addItem('Все марки', None)
        layout.addRow('Марка материала:', self.material_combo)
        
        # Период анализа
        self.days_spin = QSpinBox()
        self.days_spin.setRange(1, 365)
        self.days_spin.setValue(30)
        self.days_spin.setSuffix(' дней')
        layout.addRow('Период:', self.days_spin)
        
        # Спецификационные границы
        specs_layout = QHBoxLayout()
        
        self.lower_spec_check = QCheckBox('Нижняя граница:')
        self.lower_spec_spin = QDoubleSpinBox()
        self.lower_spec_spin.setRange(-999999, 999999)
        self.lower_spec_spin.setDecimals(2)
        self.lower_spec_spin.setEnabled(False)
        
        self.upper_spec_check = QCheckBox('Верхняя граница:')
        self.upper_spec_spin = QDoubleSpinBox()
        self.upper_spec_spin.setRange(-999999, 999999)
        self.upper_spec_spin.setDecimals(2)
        self.upper_spec_spin.setEnabled(False)
        
        self.lower_spec_check.toggled.connect(self.lower_spec_spin.setEnabled)
        self.upper_spec_check.toggled.connect(self.upper_spec_spin.setEnabled)
        
        specs_layout.addWidget(self.lower_spec_check)
        specs_layout.addWidget(self.lower_spec_spin)
        specs_layout.addWidget(self.upper_spec_check)
        specs_layout.addWidget(self.upper_spec_spin)
        
        layout.addRow('Спецификация:', specs_layout)
        
        # Кнопка анализа
        self.analyze_button = QPushButton('Выполнить анализ')
        self.analyze_button.clicked.connect(self._start_analysis)
        layout.addRow(self.analyze_button)
        
        return group
    
    def _create_statistics_tab(self) -> QScrollArea:
        """Создание вкладки с основными статистиками."""
        scroll = QScrollArea()
        widget = QFrame()
        layout = QVBoxLayout(widget)
        
        # Таблица основных статистик
        self.stats_table = QTableWidget(0, 2)
        self.stats_table.setHorizontalHeaderLabels(['Параметр', 'Значение'])
        self.stats_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(QLabel('Основные статистические показатели:'))
        layout.addWidget(self.stats_table)
        
        # Таблица данных
        self.data_table = QTableWidget(0, 6)
        self.data_table.setHorizontalHeaderLabels([
            '№ заявки', 'Дата', 'Значение', 'Марка', 'Плавка', 'Исходное значение'
        ])
        layout.addWidget(QLabel('Исходные данные:'))
        layout.addWidget(self.data_table)
        
        scroll.setWidget(widget)
        scroll.setWidgetResizable(True)
        return scroll
    
    def _create_plots_tab(self) -> QFrame:
        """Создание вкладки с графиками."""
        widget = QFrame()
        layout = QVBoxLayout(widget)
        
        # Кнопки выбора типа графика
        buttons_layout = QHBoxLayout()
        
        self.histogram_button = QPushButton('Гистограмма')
        self.histogram_button.clicked.connect(self._show_histogram)
        buttons_layout.addWidget(self.histogram_button)
        
        self.trend_button = QPushButton('Тренд')
        self.trend_button.clicked.connect(self._show_trend)
        buttons_layout.addWidget(self.trend_button)
        
        buttons_layout.addStretch()
        layout.addLayout(buttons_layout)
        
        # Область для графиков
        self.plot_widget = StatisticsPlotWidget()
        layout.addWidget(self.plot_widget)
        
        return widget
    
    def _create_outliers_tab(self) -> QScrollArea:
        """Создание вкладки с анализом выбросов."""
        scroll = QScrollArea()
        widget = QFrame()
        layout = QVBoxLayout(widget)
        
        # Результаты теста Граббса
        self.grubbs_text = QTextEdit()
        self.grubbs_text.setMaximumHeight(150)
        layout.addWidget(QLabel('Результаты критерия Граббса:'))
        layout.addWidget(self.grubbs_text)
        
        # Таблица выбросов
        self.outliers_table = QTableWidget(0, 4)
        self.outliers_table.setHorizontalHeaderLabels([
            'Индекс', 'Значение', 'Статистика Граббса', 'Z-оценка'
        ])
        layout.addWidget(QLabel('Обнаруженные выбросы:'))
        layout.addWidget(self.outliers_table)
        
        scroll.setWidget(widget)
        scroll.setWidgetResizable(True)
        return scroll
    
    def _create_control_tab(self) -> QScrollArea:
        """Создание вкладки с контрольными картами."""
        scroll = QScrollArea()
        widget = QFrame()
        layout = QVBoxLayout(widget)
        
        # Информация о границах
        self.control_info_text = QTextEdit()
        self.control_info_text.setMaximumHeight(150)
        layout.addWidget(QLabel('Границы контрольной карты:'))
        layout.addWidget(self.control_info_text)
        
        # Кнопка построения карты
        self.control_chart_button = QPushButton('Построить контрольную карту')
        self.control_chart_button.clicked.connect(self._show_control_chart)
        layout.addWidget(self.control_chart_button)
        
        # Результаты проверки правил
        self.rules_text = QTextEdit()
        layout.addWidget(QLabel('Проверка правил стабильности:'))
        layout.addWidget(self.rules_text)
        
        scroll.setWidget(widget)
        scroll.setWidgetResizable(True)
        return scroll
    
    def _create_capability_tab(self) -> QScrollArea:
        """Создание вкладки с показателями воспроизводимости."""
        scroll = QScrollArea()
        widget = QFrame()
        layout = QVBoxLayout(widget)
        
        # Таблица показателей воспроизводимости
        self.capability_table = QTableWidget(0, 2)
        self.capability_table.setHorizontalHeaderLabels(['Показатель', 'Значение'])
        layout.addWidget(QLabel('Показатели воспроизводимости процесса:'))
        layout.addWidget(self.capability_table)
        
        # Интерпретация результатов
        self.interpretation_text = QTextEdit()
        layout.addWidget(QLabel('Интерпретация результатов:'))
        layout.addWidget(self.interpretation_text)
        
        scroll.setWidget(widget)
        scroll.setWidgetResizable(True)
        return scroll
    
    def _load_initial_data(self):
        """Загрузка начальных данных для комбобоксов."""
        try:
            # Загрузка тестов
            tests = self.statistics_service.get_available_tests()
            self.test_combo.addItems(tests)
            
            # Загрузка марок материалов
            grades = self.statistics_service.get_material_grades()
            for grade in grades:
                self.material_combo.addItem(grade, grade)
                
        except Exception as e:
            logger.error(f"Ошибка загрузки начальных данных: {e}")
            QMessageBox.warning(self, 'Ошибка', f'Не удалось загрузить данные: {e}')
    
    def _start_analysis(self):
        """Запуск статистического анализа."""
        test_name = self.test_combo.currentText()
        if not test_name:
            QMessageBox.warning(self, 'Предупреждение', 'Выберите тест для анализа')
            return
        
        material_grade = self.material_combo.currentData()
        days_back = self.days_spin.value()
        
        specs = {}
        if self.lower_spec_check.isChecked():
            specs['lower'] = self.lower_spec_spin.value()
        if self.upper_spec_check.isChecked():
            specs['upper'] = self.upper_spec_spin.value()
        
        # Запуск анализа в отдельном потоке
        self.analysis_thread = StatisticsAnalysisThread(
            self.statistics_service, test_name, material_grade, days_back, specs
        )
        
        self.analysis_thread.finished.connect(self._on_analysis_finished)
        self.analysis_thread.error.connect(self._on_analysis_error)
        self.analysis_thread.progress.connect(self.progress_bar.setValue)
        
        self.analyze_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        self.analysis_thread.start()
    
    def _on_analysis_finished(self, results: Dict[str, Any]):
        """Обработка завершения анализа."""
        self.current_results = results
        
        try:
            self._populate_statistics_tab(results)
            self._populate_outliers_tab(results)
            self._populate_control_tab(results)
            self._populate_capability_tab(results)
            
            # Переключение на первую вкладку
            self.tab_widget.setCurrentIndex(0)
            
        except Exception as e:
            logger.error(f"Ошибка отображения результатов: {e}")
            QMessageBox.critical(self, 'Ошибка', f'Ошибка отображения результатов: {e}')
        
        finally:
            self.analyze_button.setEnabled(True)
            self.progress_bar.setVisible(False)
    
    def _on_analysis_error(self, error_message: str):
        """Обработка ошибки анализа."""
        QMessageBox.critical(self, 'Ошибка анализа', error_message)
        self.analyze_button.setEnabled(True)
        self.progress_bar.setVisible(False)
    
    def _populate_statistics_tab(self, results: Dict[str, Any]):
        """Заполнение вкладки основных статистик."""
        basic_stats = results.get('basic_stats', {})
        data = results.get('data', [])
        
        # Заполнение таблицы статистик
        stats_items = [
            ('Количество измерений', f"{basic_stats.get('count', 0):.0f}"),
            ('Среднее значение', f"{basic_stats.get('mean', 0):.3f}"),
            ('Медиана', f"{basic_stats.get('median', 0):.3f}"),
            ('Стандартное отклонение', f"{basic_stats.get('std', 0):.3f}"),
            ('Коэффициент вариации', f"{basic_stats.get('cv', 0):.2f}%"),
            ('Минимум', f"{basic_stats.get('min', 0):.3f}"),
            ('Максимум', f"{basic_stats.get('max', 0):.3f}"),
            ('Размах', f"{basic_stats.get('range', 0):.3f}"),
            ('1-й квартиль (Q1)', f"{basic_stats.get('q1', 0):.3f}"),
            ('3-й квартиль (Q3)', f"{basic_stats.get('q3', 0):.3f}"),
            ('Межквартильный размах', f"{basic_stats.get('iqr', 0):.3f}"),
            ('Асимметрия', f"{basic_stats.get('skewness', 0):.3f}"),
            ('Эксцесс', f"{basic_stats.get('kurtosis', 0):.3f}")
        ]
        
        self.stats_table.setRowCount(len(stats_items))
        for i, (param, value) in enumerate(stats_items):
            self.stats_table.setItem(i, 0, QTableWidgetItem(param))
            self.stats_table.setItem(i, 1, QTableWidgetItem(value))
        
        self.stats_table.resizeColumnsToContents()
        
        # Заполнение таблицы данных
        self.data_table.setRowCount(len(data))
        for i, item in enumerate(data):
            self.data_table.setItem(i, 0, QTableWidgetItem(item['request_number']))
            self.data_table.setItem(i, 1, QTableWidgetItem(item['date']))
            self.data_table.setItem(i, 2, QTableWidgetItem(f"{item['value']:.3f}"))
            self.data_table.setItem(i, 3, QTableWidgetItem(item['material_grade']))
            self.data_table.setItem(i, 4, QTableWidgetItem(item['heat_num']))
            self.data_table.setItem(i, 5, QTableWidgetItem(item['original_value']))
        
        self.data_table.resizeColumnsToContents()
    
    def _populate_outliers_tab(self, results: Dict[str, Any]):
        """Заполнение вкладки анализа выбросов."""
        outliers_analysis = results.get('outliers', {})
        
        # Информация о тесте Граббса
        test_stat = outliers_analysis.get('test_statistic')
        critical_val = outliers_analysis.get('critical_value')
        outliers_list = outliers_analysis.get('outliers', [])
        
        grubbs_info = f"""Критерий Граббса (α = 0.05):
Тестовая статистика: {test_stat:.4f if test_stat else 'N/A'}
Критическое значение: {critical_val:.4f if critical_val else 'N/A'}
Статус: {'Выбросы обнаружены' if outliers_list else 'Выбросы не обнаружены'}
Количество выбросов: {len(outliers_list)}"""
        
        self.grubbs_text.setPlainText(grubbs_info)
        
        # Таблица выбросов
        self.outliers_table.setRowCount(len(outliers_list))
        for i, outlier in enumerate(outliers_list):
            self.outliers_table.setItem(i, 0, QTableWidgetItem(str(outlier['index'])))
            self.outliers_table.setItem(i, 1, QTableWidgetItem(f"{outlier['value']:.3f}"))
            self.outliers_table.setItem(i, 2, QTableWidgetItem(f"{outlier['grubbs_statistic']:.4f}"))
            self.outliers_table.setItem(i, 3, QTableWidgetItem(f"{outlier['z_score']:.3f}"))
        
        self.outliers_table.resizeColumnsToContents()
    
    def _populate_control_tab(self, results: Dict[str, Any]):
        """Заполнение вкладки контрольных карт."""
        control_limits = results.get('control_limits', {})
        mr_limits = results.get('mr_limits', {})
        control_rules = results.get('control_rules', {})
        
        # Информация о границах
        control_info = f"""Границы контрольной карты индивидуальных значений:
Центральная линия: {control_limits.get('center_line', 0):.3f}
Верхняя контрольная граница (ВКГ): {control_limits.get('ucl', 0):.3f}
Нижняя контрольная граница (НКГ): {control_limits.get('lcl', 0):.3f}

Границы карты скользящих размахов:
Центральная линия: {mr_limits.get('center_line', 0):.3f}
ВКГ: {mr_limits.get('ucl', 0):.3f}
НКГ: {mr_limits.get('lcl', 0):.3f}"""
        
        self.control_info_text.setPlainText(control_info)
        
        # Результаты проверки правил
        is_stable = control_rules.get('process_stable', True)
        rule1_violations = control_rules.get('rule_1_violations', [])
        rule2_violations = control_rules.get('rule_2_violations', {})
        rule3_violations = control_rules.get('rule_3_violations', [])
        rule4_violations = control_rules.get('rule_4_violations', [])
        
        rules_info = f"""Анализ стабильности процесса:
Процесс стабилен: {'Да' if is_stable else 'Нет'}

Правило 1 (точки вне границ): {len(rule1_violations)} нарушений
Правило 2 (7 точек по одну сторону): {len(rule2_violations.get('runs_above_7', [])) + len(rule2_violations.get('runs_below_7', []))} нарушений
Правило 3 (2 из 3 в зоне A): {len(rule3_violations)} нарушений
Правило 4 (тренды): {len(rule4_violations)} нарушений

Рекомендации:
"""
        
        if not is_stable:
            if rule1_violations:
                rules_info += "• Имеются точки вне контрольных границ - проверьте особые причины\n"
            if rule2_violations.get('runs_above_7') or rule2_violations.get('runs_below_7'):
                rules_info += "• Обнаружены длинные серии - возможен сдвиг процесса\n"
            if rule3_violations:
                rules_info += "• Повышенная изменчивость в зоне A - контролируйте входные параметры\n"
            if rule4_violations:
                rules_info += "• Обнаружены тренды - процесс имеет тенденцию к изменению\n"
        else:
            rules_info += "• Процесс находится в статистически управляемом состоянии"
        
        self.rules_text.setPlainText(rules_info)
    
    def _populate_capability_tab(self, results: Dict[str, Any]):
        """Заполнение вкладки показателей воспроизводимости."""
        capability = results.get('capability', {})
        
        if not capability:
            self.capability_table.setRowCount(1)
            self.capability_table.setItem(0, 0, QTableWidgetItem('Нет данных'))
            self.capability_table.setItem(0, 1, QTableWidgetItem('Укажите спецификационные границы'))
            
            self.interpretation_text.setPlainText(
                "Для расчета показателей воспроизводимости необходимо указать "
                "спецификационные границы в параметрах анализа."
            )
            return
        
        # Заполнение таблицы показателей
        capability_items = []
        if 'cp' in capability:
            capability_items.append(('Cp (потенциальная воспроизводимость)', f"{capability['cp']:.3f}"))
        if 'cpk' in capability:
            capability_items.append(('Cpk (действительная воспроизводимость)', f"{capability['cpk']:.3f}"))
        if 'cpu' in capability:
            capability_items.append(('Cpu (односторонняя, верхняя)', f"{capability['cpu']:.3f}"))
        if 'cpl' in capability:
            capability_items.append(('Cpl (односторонняя, нижняя)', f"{capability['cpl']:.3f}"))
        if 'pp' in capability:
            capability_items.append(('Pp (производительность)', f"{capability['pp']:.3f}"))
        if 'ppk' in capability:
            capability_items.append(('Ppk (фактическая производительность)', f"{capability['ppk']:.3f}"))
        
        self.capability_table.setRowCount(len(capability_items))
        for i, (param, value) in enumerate(capability_items):
            self.capability_table.setItem(i, 0, QTableWidgetItem(param))
            self.capability_table.setItem(i, 1, QTableWidgetItem(value))
        
        self.capability_table.resizeColumnsToContents()
        
        # Интерпретация результатов
        cpk = capability.get('cpk', 0)
        interpretation = f"""Интерпретация показателей воспроизводимости:

Cpk = {cpk:.3f}

Оценка воспроизводимости:
"""
        
        if cpk >= 1.67:
            interpretation += "• Отличная воспроизводимость (Cpk ≥ 1.67)\n"
            interpretation += "• Процесс производит менее 0.6 дефектов на миллион возможностей\n"
        elif cpk >= 1.33:
            interpretation += "• Хорошая воспроизводимость (1.33 ≤ Cpk < 1.67)\n"
            interpretation += "• Процесс производит менее 64 дефектов на миллион возможностей\n"
        elif cpk >= 1.0:
            interpretation += "• Удовлетворительная воспроизводимость (1.0 ≤ Cpk < 1.33)\n"
            interpretation += "• Процесс производит менее 2700 дефектов на миллион возможностей\n"
        else:
            interpretation += "• Неудовлетворительная воспроизводимость (Cpk < 1.0)\n"
            interpretation += "• Процесс производит более 2700 дефектов на миллион возможностей\n"
            interpretation += "• Требуется улучшение процесса\n"
        
        if 'cp' in capability and 'cpk' in capability:
            cp = capability['cp']
            if cp > cpk:
                interpretation += f"\nПроцесс смещен от центра спецификации:\n"
                interpretation += f"• Потенциал воспроизводимости (Cp = {cp:.3f}) выше фактической (Cpk = {cpk:.3f})\n"
                interpretation += f"• Рекомендуется центрирование процесса\n"
        
        self.interpretation_text.setPlainText(interpretation)
    
    def _show_histogram(self):
        """Отображение гистограммы."""
        if not self.current_results:
            QMessageBox.warning(self, 'Предупреждение', 'Сначала выполните анализ')
            return
        
        values = self.current_results.get('values', [])
        basic_stats = self.current_results.get('basic_stats', {})
        outliers = self.current_results.get('outliers', {})
        test_name = self.test_combo.currentText()
        
        self.plot_widget.plot_histogram(values, basic_stats, outliers, test_name)
    
    def _show_trend(self):
        """Отображение графика тренда."""
        if not self.current_results:
            QMessageBox.warning(self, 'Предупреждение', 'Сначала выполните анализ')
            return
        
        # Реализация аналогична _show_histogram, но для тренда
        QMessageBox.information(self, 'В разработке', 'График тренда в разработке')
    
    def _show_control_chart(self):
        """Отображение контрольной карты."""
        if not self.current_results:
            QMessageBox.warning(self, 'Предупреждение', 'Сначала выполните анализ')
            return
        
        data = self.current_results.get('data', [])
        control_limits = self.current_results.get('control_limits', {})
        mr_limits = self.current_results.get('mr_limits', {})
        test_name = self.test_combo.currentText()
        
        self.plot_widget.plot_control_chart(data, control_limits, mr_limits, test_name) 
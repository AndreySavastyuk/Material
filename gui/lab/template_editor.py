"""
Редактор шаблонов протоколов лаборатории.

Предоставляет интерфейс для:
- Создания и редактирования шаблонов
- Работы с переменными и формулами
- Предварительного просмотра
- Синтаксической проверки
"""

import json
from typing import Dict, List, Any, Optional
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout,
    QLineEdit, QTextEdit, QComboBox, QSpinBox, QCheckBox, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem, QTabWidget,
    QSplitter, QGroupBox, QMessageBox, QDialogButtonBox,
    QListWidget, QListWidgetItem, QFrame, QScrollArea, QWidget,
    QHeaderView, QAbstractItemView, QToolButton, QMenu
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QColor, QSyntaxHighlighter, QTextCharFormat

from services.protocol_template_service import ProtocolTemplateService
from utils.logger import get_logger

logger = get_logger(__name__)


class Jinja2Highlighter(QSyntaxHighlighter):
    """Подсветка синтаксиса для Jinja2 шаблонов."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_highlighting_rules()
    
    def _setup_highlighting_rules(self):
        """Настройка правил подсветки."""
        # Формат для различных элементов Jinja2
        self.formats = {}
        
        # Переменные {{ variable }}
        self.formats['variable'] = QTextCharFormat()
        self.formats['variable'].setForeground(QColor(0, 128, 0))
        self.formats['variable'].setFontWeight(QFont.Bold)
        
        # Блоки {% block %}
        self.formats['block'] = QTextCharFormat()
        self.formats['block'].setForeground(QColor(128, 0, 128))
        self.formats['block'].setFontWeight(QFont.Bold)
        
        # Комментарии {# comment #}
        self.formats['comment'] = QTextCharFormat()
        self.formats['comment'].setForeground(QColor(128, 128, 128))
        self.formats['comment'].setFontItalic(True)
        
        # Фильтры |filter
        self.formats['filter'] = QTextCharFormat()
        self.formats['filter'].setForeground(QColor(0, 0, 255))
    
    def highlightBlock(self, text):
        """Подсветка блока текста."""
        import re
        
        # Переменные {{ ... }}
        for match in re.finditer(r'\{\{[^}]*\}\}', text):
            self.setFormat(match.start(), match.end() - match.start(), 
                          self.formats['variable'])
        
        # Блоки {% ... %}
        for match in re.finditer(r'\{%[^%]*%\}', text):
            self.setFormat(match.start(), match.end() - match.start(), 
                          self.formats['block'])
        
        # Комментарии {# ... #}
        for match in re.finditer(r'\{#[^#]*#\}', text):
            self.setFormat(match.start(), match.end() - match.start(), 
                          self.formats['comment'])
        
        # Фильтры
        for match in re.finditer(r'\|[\w_]+', text):
            self.setFormat(match.start(), match.end() - match.start(), 
                          self.formats['filter'])


class VariableSelector(QDialog):
    """Диалог выбора переменной для вставки в шаблон."""
    
    variable_selected = pyqtSignal(str)
    
    def __init__(self, template_service: ProtocolTemplateService, parent=None):
        super().__init__(parent)
        self.template_service = template_service
        self._setup_ui()
        self._load_variables()
    
    def _setup_ui(self):
        """Настройка интерфейса."""
        self.setWindowTitle('Выбор переменной')
        self.setModal(True)
        self.resize(500, 400)
        
        layout = QVBoxLayout(self)
        
        # Фильтр по категории
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel('Категория:'))
        
        self.category_combo = QComboBox()
        self.category_combo.addItem('Все', None)
        self.category_combo.addItem('Система', 'system')
        self.category_combo.addItem('Материал', 'material')
        self.category_combo.addItem('Испытания', 'testing')
        self.category_combo.addItem('Пользовательские', 'custom')
        self.category_combo.currentTextChanged.connect(self._filter_variables)
        filter_layout.addWidget(self.category_combo)
        filter_layout.addStretch()
        
        layout.addLayout(filter_layout)
        
        # Таблица переменных
        self.variables_table = QTableWidget(0, 4)
        self.variables_table.setHorizontalHeaderLabels([
            'Имя', 'Отображаемое имя', 'Тип', 'Описание'
        ])
        self.variables_table.horizontalHeader().setStretchLastSection(True)
        self.variables_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.variables_table.itemDoubleClicked.connect(self._on_variable_double_clicked)
        layout.addWidget(self.variables_table)
        
        # Кнопки
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal
        )
        buttons.accepted.connect(self._select_variable)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def _load_variables(self):
        """Загрузка списка переменных."""
        try:
            self.all_variables = self.template_service.get_template_variables()
            self._update_variables_table()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка загрузки переменных: {e}")
    
    def _filter_variables(self):
        """Фильтрация переменных по категории."""
        self._update_variables_table()
    
    def _update_variables_table(self):
        """Обновление таблицы переменных."""
        category = self.category_combo.currentData()
        
        if category:
            filtered_vars = [v for v in self.all_variables if v['category'] == category]
        else:
            filtered_vars = self.all_variables
        
        self.variables_table.setRowCount(len(filtered_vars))
        
        for i, var in enumerate(filtered_vars):
            self.variables_table.setItem(i, 0, QTableWidgetItem(var['name']))
            self.variables_table.setItem(i, 1, QTableWidgetItem(var['display_name']))
            self.variables_table.setItem(i, 2, QTableWidgetItem(var['data_type']))
            self.variables_table.setItem(i, 3, QTableWidgetItem(var['description']))
    
    def _on_variable_double_clicked(self, item):
        """Обработка двойного клика по переменной."""
        self._select_variable()
    
    def _select_variable(self):
        """Выбор переменной."""
        current_row = self.variables_table.currentRow()
        if current_row >= 0:
            var_name = self.variables_table.item(current_row, 0).text()
            self.variable_selected.emit(f"{{{{ {var_name} }}}}")
            self.accept()


class FormulaEditor(QDialog):
    """Редактор формул для шаблонов."""
    
    def __init__(self, formula_data: Optional[Dict[str, Any]] = None, parent=None):
        super().__init__(parent)
        self.formula_data = formula_data or {}
        self._setup_ui()
        self._load_formula_data()
    
    def _setup_ui(self):
        """Настройка интерфейса."""
        self.setWindowTitle('Редактор формулы')
        self.setModal(True)
        self.resize(600, 400)
        
        layout = QVBoxLayout(self)
        
        # Основные поля
        form_layout = QFormLayout()
        
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText('Например: relative_elongation')
        form_layout.addRow('Имя формулы:', self.name_edit)
        
        self.display_name_edit = QLineEdit()
        self.display_name_edit.setPlaceholderText('Например: Относительное удлинение')
        form_layout.addRow('Отображаемое имя:', self.display_name_edit)
        
        self.unit_edit = QLineEdit()
        self.unit_edit.setPlaceholderText('Например: %')
        form_layout.addRow('Единица измерения:', self.unit_edit)
        
        layout.addLayout(form_layout)
        
        # Редактор формулы
        formula_group = QGroupBox('Формула')
        formula_layout = QVBoxLayout(formula_group)
        
        self.formula_edit = QTextEdit()
        self.formula_edit.setPlaceholderText(
            'Например: (final_length - initial_length) / initial_length * 100'
        )
        self.formula_edit.setMaximumHeight(100)
        formula_layout.addWidget(self.formula_edit)
        
        # Помощь по функциям
        help_label = QLabel(
            'Доступные функции: abs, round, min, max, sum, len, pow, sqrt, '
            'sin, cos, tan, log, log10, exp, pi, e'
        )
        help_label.setWordWrap(True)
        help_label.setStyleSheet('color: gray; font-size: 10px;')
        formula_layout.addWidget(help_label)
        
        layout.addWidget(formula_group)
        
        # Описание
        self.description_edit = QTextEdit()
        self.description_edit.setPlaceholderText('Описание формулы...')
        self.description_edit.setMaximumHeight(80)
        layout.addWidget(QLabel('Описание:'))
        layout.addWidget(self.description_edit)
        
        # Кнопки
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal
        )
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def _load_formula_data(self):
        """Загрузка данных формулы для редактирования."""
        if self.formula_data:
            self.name_edit.setText(self.formula_data.get('name', ''))
            self.display_name_edit.setText(self.formula_data.get('display_name', ''))
            self.unit_edit.setText(self.formula_data.get('unit', ''))
            self.formula_edit.setPlainText(self.formula_data.get('formula', ''))
            self.description_edit.setPlainText(self.formula_data.get('description', ''))
    
    def _validate_and_accept(self):
        """Валидация и подтверждение."""
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Ошибка", "Укажите имя формулы")
            return
        
        if not self.formula_edit.toPlainText().strip():
            QMessageBox.warning(self, "Ошибка", "Укажите формулу")
            return
        
        self.accept()
    
    def get_formula_data(self) -> Dict[str, Any]:
        """Получение данных формулы."""
        return {
            'name': self.name_edit.text().strip(),
            'display_name': self.display_name_edit.text().strip(),
            'unit': self.unit_edit.text().strip(),
            'formula': self.formula_edit.toPlainText().strip(),
            'description': self.description_edit.toPlainText().strip()
        }


class TemplateEditor(QDialog):
    """Основной редактор шаблонов протоколов."""
    
    def __init__(self, template_service: ProtocolTemplateService, 
                 template_id: Optional[int] = None, parent=None):
        super().__init__(parent)
        self.template_service = template_service
        self.template_id = template_id
        self.template_data = {}
        self.preview_timer = QTimer()
        self.preview_timer.setSingleShot(True)
        self.preview_timer.timeout.connect(self._update_preview)
        
        self._setup_ui()
        if template_id:
            self._load_template()
        else:
            self._setup_new_template()
    
    def _setup_ui(self):
        """Настройка интерфейса."""
        title = 'Редактирование шаблона' if self.template_id else 'Новый шаблон'
        self.setWindowTitle(title)
        self.resize(1200, 800)
        
        layout = QVBoxLayout(self)
        
        # Основная информация
        info_group = QGroupBox('Основная информация')
        info_layout = QFormLayout(info_group)
        
        self.name_edit = QLineEdit()
        info_layout.addRow('Название:', self.name_edit)
        
        self.description_edit = QLineEdit()
        info_layout.addRow('Описание:', self.description_edit)
        
        self.category_combo = QComboBox()
        self.category_combo.addItems([
            'general', 'mechanical', 'chemical', 'metallographic', 
            'simple', 'calculated', 'custom'
        ])
        info_layout.addRow('Категория:', self.category_combo)
        
        self.output_format_combo = QComboBox()
        self.output_format_combo.addItems(['pdf', 'html', 'txt'])
        info_layout.addRow('Формат вывода:', self.output_format_combo)
        
        layout.addWidget(info_group)
        
        # Основная рабочая область
        main_splitter = QSplitter(Qt.Horizontal)
        
        # Левая панель - редактор
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        # Панель инструментов
        toolbar_layout = QHBoxLayout()
        
        self.insert_var_btn = QPushButton('Вставить переменную')
        self.insert_var_btn.clicked.connect(self._insert_variable)
        toolbar_layout.addWidget(self.insert_var_btn)
        
        self.preview_btn = QPushButton('Обновить превью')
        self.preview_btn.clicked.connect(self._update_preview)
        toolbar_layout.addWidget(self.preview_btn)
        
        toolbar_layout.addStretch()
        left_layout.addLayout(toolbar_layout)
        
        # Редактор шаблона
        self.template_edit = QTextEdit()
        self.template_edit.setFont(QFont('Consolas', 10))
        self.highlighter = Jinja2Highlighter(self.template_edit.document())
        self.template_edit.textChanged.connect(self._on_template_changed)
        left_layout.addWidget(QLabel('Содержимое шаблона:'))
        left_layout.addWidget(self.template_edit)
        
        main_splitter.addWidget(left_widget)
        
        # Правая панель - настройки и превью
        right_tabs = QTabWidget()
        
        # Вкладка формул
        formulas_widget = self._create_formulas_tab()
        right_tabs.addTab(formulas_widget, 'Формулы')
        
        # Вкладка превью
        preview_widget = self._create_preview_tab()
        right_tabs.addTab(preview_widget, 'Превью')
        
        main_splitter.addWidget(right_tabs)
        main_splitter.setSizes([700, 500])
        
        layout.addWidget(main_splitter)
        
        # Кнопки управления
        buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel,
            Qt.Horizontal
        )
        buttons.button(QDialogButtonBox.Save).setText('Сохранить')
        buttons.button(QDialogButtonBox.Cancel).setText('Отмена')
        buttons.accepted.connect(self._save_template)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def _create_formulas_tab(self) -> QWidget:
        """Создание вкладки формул."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Панель управления формулами
        formulas_toolbar = QHBoxLayout()
        
        self.add_formula_btn = QPushButton('Добавить формулу')
        self.add_formula_btn.clicked.connect(self._add_formula)
        formulas_toolbar.addWidget(self.add_formula_btn)
        
        self.edit_formula_btn = QPushButton('Редактировать')
        self.edit_formula_btn.clicked.connect(self._edit_formula)
        self.edit_formula_btn.setEnabled(False)
        formulas_toolbar.addWidget(self.edit_formula_btn)
        
        self.remove_formula_btn = QPushButton('Удалить')
        self.remove_formula_btn.clicked.connect(self._remove_formula)
        self.remove_formula_btn.setEnabled(False)
        formulas_toolbar.addWidget(self.remove_formula_btn)
        
        formulas_toolbar.addStretch()
        layout.addLayout(formulas_toolbar)
        
        # Таблица формул
        self.formulas_table = QTableWidget(0, 4)
        self.formulas_table.setHorizontalHeaderLabels([
            'Имя', 'Отображаемое имя', 'Формула', 'Описание'
        ])
        self.formulas_table.horizontalHeader().setStretchLastSection(True)
        self.formulas_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.formulas_table.itemSelectionChanged.connect(self._on_formula_selection_changed)
        self.formulas_table.itemDoubleClicked.connect(self._edit_formula)
        layout.addWidget(self.formulas_table)
        
        return widget
    
    def _create_preview_tab(self) -> QWidget:
        """Создание вкладки превью."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Панель управления превью
        preview_toolbar = QHBoxLayout()
        
        self.auto_preview_cb = QCheckBox('Автообновление превью')
        self.auto_preview_cb.setChecked(True)
        preview_toolbar.addWidget(self.auto_preview_cb)
        
        preview_toolbar.addStretch()
        layout.addLayout(preview_toolbar)
        
        # Область превью
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setFont(QFont('Arial', 10))
        layout.addWidget(self.preview_text)
        
        # Ошибки
        self.errors_label = QLabel()
        self.errors_label.setStyleSheet('color: red;')
        self.errors_label.setWordWrap(True)
        layout.addWidget(self.errors_label)
        
        return widget
    
    def _load_template(self):
        """Загрузка данных существующего шаблона."""
        try:
            self.template_data = self.template_service.get_template_by_id(self.template_id)
            if self.template_data:
                self.name_edit.setText(self.template_data['name'])
                self.description_edit.setText(self.template_data.get('description', ''))
                self.category_combo.setCurrentText(self.template_data.get('category', 'general'))
                self.output_format_combo.setCurrentText(self.template_data.get('output_format', 'pdf'))
                self.template_edit.setPlainText(self.template_data['template_content'])
                self._update_formulas_table()
                self._update_preview()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка загрузки шаблона: {e}")
    
    def _setup_new_template(self):
        """Настройка нового шаблона."""
        self.template_data = {
            'name': '',
            'description': '',
            'category': 'general',
            'template_content': '',
            'formulas': [],
            'output_format': 'pdf'
        }
        
        # Базовый шаблон
        default_template = """# ПРОТОКОЛ ИСПЫТАНИЙ

**Номер заявки:** {{ request_number }}
**Дата:** {{ creation_date }}

## Сведения о материале
- **Марка:** {{ material_grade }}
- **Размер:** {{ material_size }}

## Результаты испытаний
{% for result in test_results %}
**{{ result.name }}:** {{ result.result }}
{% endfor %}

**Статус:** {{ lab_status }}
"""
        self.template_edit.setPlainText(default_template)
        self._update_preview()
    
    def _insert_variable(self):
        """Вставка переменной в шаблон."""
        dialog = VariableSelector(self.template_service, self)
        dialog.variable_selected.connect(self._on_variable_selected)
        dialog.exec_()
    
    def _on_variable_selected(self, variable_text: str):
        """Обработка выбора переменной."""
        cursor = self.template_edit.textCursor()
        cursor.insertText(variable_text)
        self.template_edit.setFocus()
    
    def _on_template_changed(self):
        """Обработка изменения шаблона."""
        if self.auto_preview_cb.isChecked():
            self.preview_timer.start(1000)  # Задержка 1 секунда
    
    def _update_preview(self):
        """Обновление превью."""
        try:
            # Тестовые данные для превью
            test_data = {
                'request_number': 'ЛР-2024-001',
                'creation_date': '01.01.2024',
                'material_grade': 'Ст3сп',
                'material_size': '12x100',
                'rolling_type': 'Лист',
                'heat_number': 'П123456',
                'test_results': [
                    {'name': 'Предел прочности', 'result': '450 МПа'},
                    {'name': 'Предел текучести', 'result': '300 МПа'},
                    {'name': 'Относительное удлинение', 'result': '25%'}
                ],
                'lab_status': 'ППСД пройден',
                'operator_name': 'Иванов И.И.',
                'test_date': '01.01.2024'
            }
            
            template_content = self.template_edit.toPlainText()
            result, errors = self.template_service.preview_protocol(template_content, test_data)
            
            self.preview_text.setPlainText(result)
            
            if errors:
                self.errors_label.setText("Ошибки:\n" + "\n".join(errors))
                self.errors_label.setVisible(True)
            else:
                self.errors_label.setVisible(False)
                
        except Exception as e:
            self.errors_label.setText(f"Ошибка превью: {e}")
            self.errors_label.setVisible(True)
    
    def _add_formula(self):
        """Добавление новой формулы."""
        dialog = FormulaEditor(parent=self)
        if dialog.exec_() == QDialog.Accepted:
            formula_data = dialog.get_formula_data()
            if not hasattr(self.template_data, 'formulas'):
                self.template_data['formulas'] = []
            self.template_data['formulas'].append(formula_data)
            self._update_formulas_table()
    
    def _edit_formula(self):
        """Редактирование выбранной формулы."""
        current_row = self.formulas_table.currentRow()
        if current_row >= 0:
            formula_data = self.template_data.get('formulas', [])[current_row]
            dialog = FormulaEditor(formula_data, self)
            if dialog.exec_() == QDialog.Accepted:
                updated_data = dialog.get_formula_data()
                self.template_data['formulas'][current_row] = updated_data
                self._update_formulas_table()
    
    def _remove_formula(self):
        """Удаление выбранной формулы."""
        current_row = self.formulas_table.currentRow()
        if current_row >= 0:
            reply = QMessageBox.question(
                self, 'Подтверждение',
                'Удалить выбранную формулу?',
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                del self.template_data['formulas'][current_row]
                self._update_formulas_table()
    
    def _on_formula_selection_changed(self):
        """Обработка изменения выбора формулы."""
        has_selection = self.formulas_table.currentRow() >= 0
        self.edit_formula_btn.setEnabled(has_selection)
        self.remove_formula_btn.setEnabled(has_selection)
    
    def _update_formulas_table(self):
        """Обновление таблицы формул."""
        formulas = self.template_data.get('formulas', [])
        self.formulas_table.setRowCount(len(formulas))
        
        for i, formula in enumerate(formulas):
            self.formulas_table.setItem(i, 0, QTableWidgetItem(formula.get('name', '')))
            self.formulas_table.setItem(i, 1, QTableWidgetItem(formula.get('display_name', '')))
            self.formulas_table.setItem(i, 2, QTableWidgetItem(formula.get('formula', '')))
            self.formulas_table.setItem(i, 3, QTableWidgetItem(formula.get('description', '')))
    
    def _save_template(self):
        """Сохранение шаблона."""
        try:
            # Сбор данных
            template_data = {
                'name': self.name_edit.text().strip(),
                'description': self.description_edit.text().strip(),
                'category': self.category_combo.currentText(),
                'template_content': self.template_edit.toPlainText(),
                'formulas': self.template_data.get('formulas', []),
                'output_format': self.output_format_combo.currentText()
            }
            
            if not template_data['name']:
                QMessageBox.warning(self, "Ошибка", "Укажите название шаблона")
                return
            
            if not template_data['template_content'].strip():
                QMessageBox.warning(self, "Ошибка", "Укажите содержимое шаблона")
                return
            
            # Сохранение
            user_login = 'current_user'  # TODO: получать из контекста
            
            if self.template_id:
                success = self.template_service.update_template(
                    self.template_id, template_data, user_login
                )
                if success:
                    QMessageBox.information(self, "Успех", "Шаблон успешно обновлен")
                    self.accept()
                else:
                    QMessageBox.warning(self, "Ошибка", "Не удалось обновить шаблон")
            else:
                template_id = self.template_service.create_template(template_data, user_login)
                if template_id:
                    QMessageBox.information(self, "Успех", f"Шаблон создан с ID: {template_id}")
                    self.accept()
                else:
                    QMessageBox.warning(self, "Ошибка", "Не удалось создать шаблон")
                    
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка сохранения шаблона: {e}")


class TemplateManager(QDialog):
    """Менеджер шаблонов протоколов."""
    
    def __init__(self, template_service: ProtocolTemplateService, parent=None):
        super().__init__(parent)
        self.template_service = template_service
        self._setup_ui()
        self._load_templates()
    
    def _setup_ui(self):
        """Настройка интерфейса."""
        self.setWindowTitle('Управление шаблонами протоколов')
        self.resize(800, 600)
        
        layout = QVBoxLayout(self)
        
        # Панель управления
        toolbar = QHBoxLayout()
        
        self.new_template_btn = QPushButton('Создать шаблон')
        self.new_template_btn.clicked.connect(self._create_template)
        toolbar.addWidget(self.new_template_btn)
        
        self.edit_template_btn = QPushButton('Редактировать')
        self.edit_template_btn.clicked.connect(self._edit_template)
        self.edit_template_btn.setEnabled(False)
        toolbar.addWidget(self.edit_template_btn)
        
        self.delete_template_btn = QPushButton('Удалить')
        self.delete_template_btn.clicked.connect(self._delete_template)
        self.delete_template_btn.setEnabled(False)
        toolbar.addWidget(self.delete_template_btn)
        
        toolbar.addStretch()
        
        self.refresh_btn = QPushButton('Обновить')
        self.refresh_btn.clicked.connect(self._load_templates)
        toolbar.addWidget(self.refresh_btn)
        
        layout.addLayout(toolbar)
        
        # Таблица шаблонов
        self.templates_table = QTableWidget(0, 6)
        self.templates_table.setHorizontalHeaderLabels([
            'ID', 'Название', 'Описание', 'Категория', 'Версия', 'Создан'
        ])
        self.templates_table.horizontalHeader().setStretchLastSection(True)
        self.templates_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.templates_table.itemSelectionChanged.connect(self._on_selection_changed)
        self.templates_table.itemDoubleClicked.connect(self._edit_template)
        layout.addWidget(self.templates_table)
        
        # Кнопка закрытия
        close_btn = QPushButton('Закрыть')
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
    
    def _load_templates(self):
        """Загрузка списка шаблонов."""
        try:
            templates = self.template_service.get_all_templates()
            self.templates_table.setRowCount(len(templates))
            
            for i, template in enumerate(templates):
                self.templates_table.setItem(i, 0, QTableWidgetItem(str(template['id'])))
                self.templates_table.setItem(i, 1, QTableWidgetItem(template['name']))
                self.templates_table.setItem(i, 2, QTableWidgetItem(template.get('description', '')))
                self.templates_table.setItem(i, 3, QTableWidgetItem(template['category']))
                self.templates_table.setItem(i, 4, QTableWidgetItem(str(template['version'])))
                self.templates_table.setItem(i, 5, QTableWidgetItem(template.get('created_at', '')))
                
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка загрузки шаблонов: {e}")
    
    def _on_selection_changed(self):
        """Обработка изменения выбора."""
        has_selection = self.templates_table.currentRow() >= 0
        self.edit_template_btn.setEnabled(has_selection)
        self.delete_template_btn.setEnabled(has_selection)
    
    def _create_template(self):
        """Создание нового шаблона."""
        dialog = TemplateEditor(self.template_service, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            self._load_templates()
    
    def _edit_template(self):
        """Редактирование выбранного шаблона."""
        current_row = self.templates_table.currentRow()
        if current_row >= 0:
            template_id = int(self.templates_table.item(current_row, 0).text())
            dialog = TemplateEditor(self.template_service, template_id, self)
            if dialog.exec_() == QDialog.Accepted:
                self._load_templates()
    
    def _delete_template(self):
        """Удаление выбранного шаблона."""
        current_row = self.templates_table.currentRow()
        if current_row >= 0:
            template_name = self.templates_table.item(current_row, 1).text()
            reply = QMessageBox.question(
                self, 'Подтверждение',
                f'Удалить шаблон "{template_name}"?',
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                try:
                    template_id = int(self.templates_table.item(current_row, 0).text())
                    user_login = 'current_user'  # TODO: получать из контекста
                    
                    success = self.template_service.delete_template(template_id, user_login)
                    if success:
                        QMessageBox.information(self, "Успех", "Шаблон удален")
                        self._load_templates()
                    else:
                        QMessageBox.warning(self, "Ошибка", "Не удалось удалить шаблон")
                        
                except Exception as e:
                    QMessageBox.critical(self, "Ошибка", f"Ошибка удаления: {e}") 
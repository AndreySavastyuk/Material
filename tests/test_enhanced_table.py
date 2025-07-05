"""
Тесты для улучшенного виджета таблицы.
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtCore import Qt, QPoint, QSettings
from PyQt5.QtTest import QTest

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from gui.widgets.enhanced_table import (
    EnhancedTableWidget, SortOrder, SortColumn, TableSettings,
    ColumnSettingsDialog, TableSettingsDialog, StickyHeaderView
)


class TestEnhancedTableWidget:
    """Тесты для улучшенного виджета таблицы."""
    
    @pytest.fixture
    def app(self):
        """Фикстура Qt приложения."""
        if not QApplication.instance():
            app = QApplication([])
        else:
            app = QApplication.instance()
        yield app
    
    @pytest.fixture
    def table_widget(self, app):
        """Фикстура виджета таблицы."""
        widget = EnhancedTableWidget()
        yield widget
        widget.close()
    
    def test_table_creation(self, table_widget):
        """Тест создания таблицы."""
        assert table_widget is not None
        assert isinstance(table_widget.settings, TableSettings)
        assert table_widget.sort_columns == []
        assert table_widget.column_groups == []
    
    def test_sticky_headers(self, table_widget):
        """Тест фиксированных заголовков."""
        horizontal_header = table_widget.horizontalHeader()
        vertical_header = table_widget.verticalHeader()
        
        assert isinstance(horizontal_header, StickyHeaderView)
        assert isinstance(vertical_header, StickyHeaderView)
        assert horizontal_header.sectionsClickable()
        assert horizontal_header.sectionsMovable()
    
    def test_sort_column_add(self, table_widget):
        """Тест добавления колонки сортировки."""
        # Настраиваем таблицу
        table_widget.setColumnCount(3)
        table_widget.setRowCount(2)
        
        # Добавляем сортировку по первой колонке
        table_widget._add_sort_column(0)
        
        assert len(table_widget.sort_columns) == 1
        assert table_widget.sort_columns[0].column == 0
        assert table_widget.sort_columns[0].order == SortOrder.ASCENDING
        assert table_widget.sort_columns[0].priority == 0
    
    def test_multiple_sort(self, table_widget):
        """Тест множественной сортировки."""
        table_widget.setColumnCount(3)
        table_widget.setRowCount(2)
        
        # Добавляем несколько колонок сортировки
        table_widget._add_sort_column(0)
        table_widget._add_sort_column(1)
        table_widget._add_sort_column(2)
        
        assert len(table_widget.sort_columns) == 3
        
        # Проверяем приоритеты
        priorities = [sc.priority for sc in table_widget.sort_columns]
        assert priorities == [0, 1, 2]
    
    def test_sort_order_toggle(self, table_widget):
        """Тест переключения порядка сортировки."""
        table_widget.setColumnCount(3)
        table_widget.setRowCount(2)
        
        # Первый клик - по возрастанию
        table_widget._add_sort_column(0)
        assert table_widget.sort_columns[0].order == SortOrder.ASCENDING
        
        # Второй клик - по убыванию
        table_widget._add_sort_column(0)
        assert table_widget.sort_columns[0].order == SortOrder.DESCENDING
        
        # Третий клик - снова по возрастанию
        table_widget._add_sort_column(0)
        assert table_widget.sort_columns[0].order == SortOrder.ASCENDING
    
    def test_single_sort_column(self, table_widget):
        """Тест единственной сортировки."""
        table_widget.setColumnCount(3)
        table_widget.setRowCount(2)
        
        # Добавляем множественную сортировку
        table_widget._add_sort_column(0)
        table_widget._add_sort_column(1)
        assert len(table_widget.sort_columns) == 2
        
        # Устанавливаем единственную сортировку
        table_widget._set_single_sort_column(2)
        assert len(table_widget.sort_columns) == 1
        assert table_widget.sort_columns[0].column == 2
    
    def test_clear_sorting(self, table_widget):
        """Тест очистки сортировки."""
        table_widget.setColumnCount(3)
        table_widget.setRowCount(2)
        
        # Добавляем сортировку
        table_widget._add_sort_column(0)
        table_widget._add_sort_column(1)
        assert len(table_widget.sort_columns) == 2
        
        # Очищаем
        table_widget._clear_sorting()
        assert len(table_widget.sort_columns) == 0
    
    @patch('gui.widgets.enhanced_table.QSettings')
    def test_save_settings(self, mock_qsettings, table_widget):
        """Тест сохранения настроек."""
        mock_settings = Mock()
        mock_qsettings.return_value = mock_settings
        
        # Настраиваем таблицу
        table_widget.setColumnCount(3)
        table_widget.setColumnWidth(0, 100)
        table_widget.setColumnWidth(1, 150)
        table_widget.setColumnHidden(2, True)
        
        # Добавляем сортировку
        table_widget._add_sort_column(0)
        
        # Сохраняем настройки
        table_widget.save_settings("test_table")
        
        # Проверяем вызов setValue
        mock_settings.setValue.assert_called_once()
        call_args = mock_settings.setValue.call_args
        assert call_args[0][0] == "test_table"
        
        # Проверяем сохраненные данные
        saved_data = json.loads(call_args[0][1])
        assert 'column_widths' in saved_data
        assert 'column_visibility' in saved_data
        assert 'sort_columns' in saved_data
    
    @patch('gui.widgets.enhanced_table.QSettings')
    def test_load_settings(self, mock_qsettings, table_widget):
        """Тест загрузки настроек."""
        mock_settings = Mock()
        mock_qsettings.return_value = mock_settings
        
        # Подготавливаем данные настроек
        settings_data = {
            'column_widths': {0: 100, 1: 150},
            'column_visibility': {0: True, 1: True, 2: False},
            'sort_columns': [
                {'column': 0, 'order': 'asc', 'priority': 0}
            ],
            'row_height': 30,
            'font_size': 10,
            'show_grid': False,
            'alternate_colors': False
        }
        mock_settings.value.return_value = json.dumps(settings_data)
        
        # Настраиваем таблицу
        table_widget.setColumnCount(3)
        table_widget.setRowCount(2)
        
        # Загружаем настройки
        table_widget.load_settings("test_table")
        
        # Проверяем результат
        assert table_widget.columnWidth(0) == 100
        assert table_widget.columnWidth(1) == 150
        assert table_widget.isColumnHidden(2) == True
        assert len(table_widget.sort_columns) == 1
        assert table_widget.sort_columns[0].column == 0
        assert table_widget.settings.row_height == 30
        assert table_widget.settings.font_size == 10
    
    @patch('gui.widgets.enhanced_table.QSettings')
    def test_load_settings_no_data(self, mock_qsettings, table_widget):
        """Тест загрузки настроек при отсутствии данных."""
        mock_settings = Mock()
        mock_qsettings.return_value = mock_settings
        mock_settings.value.return_value = None
        
        # Загружаем настройки
        table_widget.load_settings("test_table")
        
        # Проверяем что настройки по умолчанию не изменились
        assert table_widget.settings.row_height == 25
        assert table_widget.settings.font_size == 9
    
    def test_context_menu_actions(self, table_widget):
        """Тест действий контекстного меню."""
        table_widget.setColumnCount(3)
        table_widget.setRowCount(2)
        
        # Симулируем создание контекстного меню
        pos = QPoint(50, 50)
        
        # Проверяем что методы существуют и могут быть вызваны
        assert hasattr(table_widget, '_show_context_menu')
        assert hasattr(table_widget, '_hide_column')
        assert hasattr(table_widget, '_freeze_column')
        assert hasattr(table_widget, '_group_by_column')
    
    def test_copy_row(self, table_widget, app):
        """Тест копирования строки."""
        table_widget.setColumnCount(3)
        table_widget.setRowCount(2)
        
        # Заполняем данными
        from PyQt5.QtWidgets import QTableWidgetItem
        table_widget.setItem(0, 0, QTableWidgetItem("A1"))
        table_widget.setItem(0, 1, QTableWidgetItem("B1"))
        table_widget.setItem(0, 2, QTableWidgetItem("C1"))
        
        # Тестируем копирование
        with patch.object(app, 'clipboard') as mock_clipboard:
            mock_clipboard_obj = Mock()
            mock_clipboard.return_value = mock_clipboard_obj
            
            table_widget._copy_row(0)
            
            # Проверяем что setText был вызван с правильными данными
            mock_clipboard_obj.setText.assert_called_once_with("A1\tB1\tC1")
    
    def test_column_grouping_signal(self, table_widget):
        """Тест сигнала группировки колонок."""
        with patch.object(table_widget, 'column_grouped') as mock_signal:
            table_widget._group_by_column(2)
            mock_signal.emit.assert_called_once_with(2)
    
    def test_sort_changed_signal(self, table_widget):
        """Тест сигнала изменения сортировки."""
        table_widget.setColumnCount(3)
        
        with patch.object(table_widget, 'sort_changed') as mock_signal:
            table_widget._add_sort_column(1)
            mock_signal.emit.assert_called()
    
    def test_settings_changed_signal(self, table_widget):
        """Тест сигнала изменения настроек."""
        with patch.object(table_widget, 'settings_changed') as mock_signal:
            table_widget._on_column_resized(0, 100, 150)
            mock_signal.emit.assert_called_once()


class TestColumnSettingsDialog:
    """Тесты для диалога настроек колонок."""
    
    @pytest.fixture
    def app(self):
        """Фикстура Qt приложения."""
        if not QApplication.instance():
            app = QApplication([])
        else:
            app = QApplication.instance()
        yield app
    
    @pytest.fixture
    def table_widget(self, app):
        """Фикстура виджета таблицы."""
        widget = EnhancedTableWidget()
        widget.setColumnCount(3)
        widget.setHorizontalHeaderLabels(["Col1", "Col2", "Col3"])
        yield widget
        widget.close()
    
    def test_dialog_creation(self, table_widget):
        """Тест создания диалога."""
        dialog = ColumnSettingsDialog(table_widget)
        assert dialog is not None
        assert dialog.table == table_widget
        assert dialog.windowTitle() == "Настройки колонок"
        dialog.close()
    
    def test_dialog_initialization(self, table_widget):
        """Тест инициализации диалога с данными таблицы."""
        # Настраиваем таблицу
        table_widget.setColumnWidth(0, 100)
        table_widget.setColumnHidden(1, True)
        
        dialog = ColumnSettingsDialog(table_widget)
        
        # Проверяем что данные загружены правильно
        assert dialog.column_list.topLevelItemCount() == 3
        
        # Проверяем первую колонку
        item0 = dialog.column_list.topLevelItem(0)
        assert item0.text(0) == "Col1"
        assert item0.checkState(1) == Qt.Checked
        assert item0.text(2) == "100"
        
        # Проверяем скрытую колонку
        item1 = dialog.column_list.topLevelItem(1)
        assert item1.checkState(1) == Qt.Unchecked
        
        dialog.close()


class TestTableSettingsDialog:
    """Тесты для диалога настроек таблицы."""
    
    @pytest.fixture
    def app(self):
        """Фикстура Qt приложения."""
        if not QApplication.instance():
            app = QApplication([])
        else:
            app = QApplication.instance()
        yield app
    
    @pytest.fixture
    def table_widget(self, app):
        """Фикстура виджета таблицы."""
        widget = EnhancedTableWidget()
        yield widget
        widget.close()
    
    def test_dialog_creation(self, table_widget):
        """Тест создания диалога."""
        dialog = TableSettingsDialog(table_widget)
        assert dialog is not None
        assert dialog.table == table_widget
        assert dialog.windowTitle() == "Настройки таблицы"
        dialog.close()
    
    def test_dialog_initialization(self, table_widget):
        """Тест инициализации диалога с настройками таблицы."""
        # Изменяем настройки таблицы
        table_widget.settings.font_size = 12
        table_widget.settings.row_height = 30
        table_widget.settings.show_grid = False
        table_widget.settings.alternate_colors = False
        
        dialog = TableSettingsDialog(table_widget)
        
        # Проверяем что настройки загружены
        assert dialog.font_size_spin.value() == 12
        assert dialog.row_height_spin.value() == 30
        assert dialog.show_grid_check.isChecked() == False
        assert dialog.alternate_colors_check.isChecked() == False
        
        dialog.close()
    
    def test_reset_settings(self, table_widget):
        """Тест сброса настроек."""
        dialog = TableSettingsDialog(table_widget)
        
        # Изменяем значения
        dialog.font_size_spin.setValue(15)
        dialog.row_height_spin.setValue(40)
        dialog.show_grid_check.setChecked(False)
        dialog.alternate_colors_check.setChecked(False)
        
        # Сбрасываем
        dialog._reset_settings()
        
        # Проверяем сброс к значениям по умолчанию
        assert dialog.font_size_spin.value() == 9
        assert dialog.row_height_spin.value() == 25
        assert dialog.show_grid_check.isChecked() == True
        assert dialog.alternate_colors_check.isChecked() == True
        
        dialog.close()


class TestSortColumn:
    """Тесты для класса SortColumn."""
    
    def test_sort_column_creation(self):
        """Тест создания SortColumn."""
        sort_col = SortColumn(column=1, order=SortOrder.ASCENDING, priority=0)
        
        assert sort_col.column == 1
        assert sort_col.order == SortOrder.ASCENDING
        assert sort_col.priority == 0
    
    def test_sort_order_enum(self):
        """Тест enum SortOrder."""
        assert SortOrder.ASCENDING.value == "asc"
        assert SortOrder.DESCENDING.value == "desc"


class TestTableSettings:
    """Тесты для класса TableSettings."""
    
    def test_table_settings_creation(self):
        """Тест создания TableSettings."""
        settings = TableSettings(
            column_widths={0: 100, 1: 150},
            column_visibility={0: True, 1: False},
            sort_columns=[],
            groups=[],
            frozen_columns=1,
            row_height=30,
            font_size=10,
            show_grid=False,
            alternate_colors=False
        )
        
        assert settings.column_widths == {0: 100, 1: 150}
        assert settings.column_visibility == {0: True, 1: False}
        assert settings.frozen_columns == 1
        assert settings.row_height == 30
        assert settings.font_size == 10
        assert settings.show_grid == False
        assert settings.alternate_colors == False


if __name__ == '__main__':
    pytest.main([__file__]) 
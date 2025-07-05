"""
Тесты для асинхронных операций.
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from PyQt5.QtCore import QTimer
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

from utils.async_operations import (
    AsyncOperation, MaterialsLoadWorker, MaterialsSearchWorker,
    ProgressWidget, DebounceTimer
)
from services.materials_service import MaterialsService
from utils.exceptions import BusinessLogicError


class TestAsyncOperation:
    """Тесты базового класса AsyncOperation."""
    
    def test_operation_name(self):
        """Тест установки имени операции."""
        operation = AsyncOperation()
        operation.set_operation_name("Тестовая операция")
        assert operation._operation_name == "Тестовая операция"
    
    def test_cancellation(self):
        """Тест отмены операции."""
        operation = AsyncOperation()
        assert not operation.is_cancelled()
        
        operation.cancel()
        assert operation.is_cancelled()
        assert operation.check_cancellation()
    
    def test_pause_resume(self):
        """Тест приостановки и возобновления операции."""
        operation = AsyncOperation()
        assert not operation.is_paused()
        
        operation.pause()
        assert operation.is_paused()
        
        operation.resume()
        assert not operation.is_paused()


class TestMaterialsLoadWorker:
    """Тесты воркера загрузки материалов."""
    
    def test_init(self):
        """Тест инициализации воркера."""
        materials_service = Mock()
        worker = MaterialsLoadWorker(materials_service)
        
        assert worker.materials_service == materials_service
        assert worker._operation_name == "Загрузка материалов"
    
    def test_execute_success(self):
        """Тест успешного выполнения загрузки."""
        materials_service = Mock()
        materials = [{'id': 1, 'name': 'Материал 1'}]
        formatted_materials = [{'id': 1, 'name': 'Материал 1', 'formatted': True}]
        
        materials_service.get_all_materials.return_value = materials
        materials_service.format_materials_for_display.return_value = formatted_materials
        
        worker = MaterialsLoadWorker(materials_service)
        result = worker.execute()
        
        assert result == formatted_materials
        materials_service.get_all_materials.assert_called_once()
        materials_service.format_materials_for_display.assert_called_once_with(materials)
    
    def test_execute_with_cancellation(self):
        """Тест выполнения с отменой."""
        materials_service = Mock()
        worker = MaterialsLoadWorker(materials_service)
        
        # Имитируем отмену
        worker.cancel()
        
        result = worker.execute()
        assert result == []
        
        # Проверяем, что методы сервиса не вызывались
        materials_service.get_all_materials.assert_not_called()
        materials_service.format_materials_for_display.assert_not_called()
    
    def test_execute_with_error(self):
        """Тест выполнения с ошибкой."""
        materials_service = Mock()
        materials_service.get_all_materials.side_effect = Exception("Ошибка БД")
        
        worker = MaterialsLoadWorker(materials_service)
        
        with pytest.raises(BusinessLogicError) as exc_info:
            worker.execute()
        
        assert "Ошибка загрузки материалов" in str(exc_info.value)


class TestMaterialsSearchWorker:
    """Тесты воркера поиска материалов."""
    
    def test_init(self):
        """Тест инициализации воркера."""
        materials_service = Mock()
        search_text = "тест"
        worker = MaterialsSearchWorker(materials_service, search_text)
        
        assert worker.materials_service == materials_service
        assert worker.search_text == search_text
        assert worker._operation_name == "Поиск материалов: 'тест'"
    
    def test_execute_with_search_text(self):
        """Тест выполнения поиска с текстом."""
        materials_service = Mock()
        search_text = "материал"
        formatted_materials = [{'id': 1, 'name': 'Материал 1', 'formatted': True}]
        
        materials_service.search_materials_with_formatting.return_value = formatted_materials
        
        worker = MaterialsSearchWorker(materials_service, search_text)
        result = worker.execute()
        
        assert result == formatted_materials
        materials_service.search_materials_with_formatting.assert_called_once_with(search_text)
    
    def test_execute_with_short_text(self):
        """Тест выполнения поиска с коротким текстом."""
        materials_service = Mock()
        search_text = "а"  # Короткий текст
        materials = [{'id': 1, 'name': 'Материал 1'}]
        formatted_materials = [{'id': 1, 'name': 'Материал 1', 'formatted': True}]
        
        materials_service.get_all_materials.return_value = materials
        materials_service.format_materials_for_display.return_value = formatted_materials
        
        worker = MaterialsSearchWorker(materials_service, search_text)
        result = worker.execute()
        
        assert result == formatted_materials
        materials_service.get_all_materials.assert_called_once()
        materials_service.format_materials_for_display.assert_called_once_with(materials)
        # Поиск не должен вызываться для коротких текстов
        materials_service.search_materials_with_formatting.assert_not_called()
    
    def test_execute_with_cancellation(self):
        """Тест выполнения с отменой."""
        materials_service = Mock()
        worker = MaterialsSearchWorker(materials_service, "тест")
        
        # Имитируем отмену
        worker.cancel()
        
        result = worker.execute()
        assert result == []


class TestProgressWidget:
    """Тесты виджета прогресса."""
    
    def test_init(self):
        """Тест инициализации виджета."""
        widget = ProgressWidget()
        
        assert widget.progress_bar is not None
        assert widget.status_label is not None
        assert widget.cancel_button is not None
        assert not widget.isVisible()
        assert not widget.cancel_button.isEnabled()
    
    def test_start_operation(self):
        """Тест запуска операции."""
        widget = ProgressWidget()
        operation = Mock()
        
        widget.start_operation(operation)
        
        assert widget.isVisible()
        assert widget.cancel_button.isEnabled()
        assert widget.progress_bar.value() == 0
        assert widget.status_label.text() == "Запуск операции..."
    
    def test_update_progress(self):
        """Тест обновления прогресса."""
        widget = ProgressWidget()
        
        widget.update_progress(50)
        assert widget.progress_bar.value() == 50
    
    def test_update_status(self):
        """Тест обновления статуса."""
        widget = ProgressWidget()
        
        widget.update_status("Загрузка данных...")
        assert widget.status_label.text() == "Загрузка данных..."
    
    def test_operation_finished(self):
        """Тест завершения операции."""
        widget = ProgressWidget()
        
        # Сначала запускаем операцию
        widget.setVisible(True)
        widget.cancel_button.setEnabled(True)
        widget.progress_bar.setValue(50)
        widget.status_label.setText("Выполняется...")
        
        # Завершаем операцию
        widget.operation_finished()
        
        assert not widget.isVisible()
        assert not widget.cancel_button.isEnabled()
        assert widget.progress_bar.value() == 0
        assert widget.status_label.text() == "Готов"


class TestDebounceTimer:
    """Тесты таймера debounce."""
    
    def test_init(self):
        """Тест инициализации."""
        timer = DebounceTimer(500)
        assert timer.delay_ms == 500
        assert timer.callback is None
    
    def test_debounce_single_call(self):
        """Тест одиночного вызова debounce."""
        timer = DebounceTimer(100)
        callback = Mock()
        
        timer.debounce(callback, "arg1", kwarg1="value1")
        
        # Проверяем, что callback сохранен
        assert timer.callback == callback
        assert timer.args == ("arg1",)
        assert timer.kwargs == {"kwarg1": "value1"}
    
    def test_debounce_multiple_calls(self):
        """Тест множественных вызовов debounce."""
        timer = DebounceTimer(100)
        callback1 = Mock()
        callback2 = Mock()
        
        # Первый вызов
        timer.debounce(callback1, "arg1")
        
        # Второй вызов должен отменить первый
        timer.debounce(callback2, "arg2")
        
        # Проверяем, что сохранен только последний callback
        assert timer.callback == callback2
        assert timer.args == ("arg2",)
        
    def test_execute_callback_with_exception(self):
        """Тест выполнения callback с исключением."""
        timer = DebounceTimer(100)
        callback = Mock(side_effect=Exception("Ошибка в callback"))
        
        timer.callback = callback
        timer.args = ("arg1",)
        timer.kwargs = {}
        
        # Выполнение не должно вызвать исключение
        timer._execute_callback()
        
        # Callback должен быть вызван
        callback.assert_called_once_with("arg1")
        
        # Состояние должно быть очищено
        assert timer.callback is None
        assert timer.args is None
        assert timer.kwargs is None


# Фикстуры для тестов с Qt
@pytest.fixture
def app():
    """Фикстура QApplication для тестов."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class TestProgressWidgetQt:
    """Тесты виджета прогресса с Qt."""
    
    def test_widget_creation(self, app):
        """Тест создания виджета."""
        widget = ProgressWidget()
        assert widget is not None
        assert widget.progress_bar.minimum() == 0
        assert widget.progress_bar.maximum() == 100
        
    def test_signal_connections(self, app):
        """Тест подключения сигналов."""
        widget = ProgressWidget()
        operation = Mock()
        
        # Имитируем сигналы
        operation.progress_updated = Mock()
        operation.status_updated = Mock()
        operation.finished = Mock()
        
        # Подключаем сигналы
        operation.progress_updated.connect = Mock()
        operation.status_updated.connect = Mock()
        operation.finished.connect = Mock()
        
        widget.start_operation(operation)
        
        # Проверяем, что сигналы были подключены
        operation.progress_updated.connect.assert_called_once()
        operation.status_updated.connect.assert_called_once()
        operation.finished.connect.assert_called_once()
        

if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 
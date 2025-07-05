"""
Модуль для асинхронных операций с использованием QThread.

Предоставляет базовые классы для выполнения длительных операций
в фоновом режиме с возможностью отмены и отслеживания прогресса.
"""

import time
from typing import Any, Optional, Dict, List, Callable
from PyQt5.QtCore import QThread, pyqtSignal, QMutex, QWaitCondition, QTimer
from PyQt5.QtWidgets import QProgressBar, QLabel, QPushButton, QHBoxLayout, QWidget

from utils.logger import get_logger
from utils.exceptions import BusinessLogicError, ValidationError

logger = get_logger(__name__)


class AsyncOperation(QThread):
    """
    Базовый класс для асинхронных операций.
    
    Предоставляет:
    - Сигналы для прогресса, результата и ошибок
    - Механизм отмены операций
    - Базовые методы для переопределения
    """
    
    # Сигналы для взаимодействия с GUI
    progress_updated = pyqtSignal(int)  # Прогресс (0-100)
    status_updated = pyqtSignal(str)    # Текущий статус операции
    result_ready = pyqtSignal(object)   # Результат операции
    error_occurred = pyqtSignal(Exception)  # Ошибка
    finished = pyqtSignal()             # Завершение операции
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._cancelled = False
        self._mutex = QMutex()
        self._pause_condition = QWaitCondition()
        self._paused = False
        self._operation_name = "Операция"
        self._start_time = None
        
    def set_operation_name(self, name: str):
        """Устанавливает название операции."""
        self._operation_name = name
        
    def cancel(self):
        """Отменяет выполнение операции."""
        self._mutex.lock()
        try:
            self._cancelled = True
            if self._paused:
                self._pause_condition.wakeAll()
        finally:
            self._mutex.unlock()
        logger.info(f"Отмена операции: {self._operation_name}")
        
    def pause(self):
        """Приостанавливает выполнение операции."""
        self._mutex.lock()
        try:
            self._paused = True
        finally:
            self._mutex.unlock()
        logger.info(f"Приостановка операции: {self._operation_name}")
        
    def resume(self):
        """Возобновляет выполнение операции."""
        self._mutex.lock()
        try:
            self._paused = False
            self._pause_condition.wakeAll()
        finally:
            self._mutex.unlock()
        logger.info(f"Возобновление операции: {self._operation_name}")
        
    def is_cancelled(self) -> bool:
        """Проверяет, была ли отменена операция."""
        return self._cancelled
        
    def is_paused(self) -> bool:
        """Проверяет, приостановлена ли операция."""
        return self._paused
        
    def check_cancellation(self):
        """
        Проверяет отмену и приостановку операции.
        Должна вызываться в критических точках операции.
        """
        if self._cancelled:
            logger.info(f"Операция отменена: {self._operation_name}")
            return True
            
        if self._paused:
            logger.info(f"Операция приостановлена: {self._operation_name}")
            self._mutex.lock()
            self._pause_condition.wait(self._mutex)
            self._mutex.unlock()
            
        return False
        
    def update_progress(self, value: int, status: str = ""):
        """
        Обновляет прогресс операции.
        
        Args:
            value: Прогресс в процентах (0-100)
            status: Текущий статус операции
        """
        if not self._cancelled:
            self.progress_updated.emit(value)
            if status:
                self.status_updated.emit(status)
                
    def run(self):
        """
        Основной метод выполнения операции.
        Переопределяется в дочерних классах.
        """
        try:
            self._start_time = time.time()
            logger.info(f"Начало выполнения операции: {self._operation_name}")
            
            # Выполняем операцию
            result = self.execute()
            
            # Проверяем отмену перед отправкой результата
            if not self._cancelled:
                self.result_ready.emit(result)
                duration = time.time() - self._start_time
                logger.info(f"Операция завершена успешно: {self._operation_name} за {duration:.2f}с")
            else:
                logger.info(f"Операция отменена: {self._operation_name}")
                
        except Exception as e:
            logger.error(f"Ошибка в операции {self._operation_name}: {e}")
            self.error_occurred.emit(e)
        finally:
            self.finished.emit()
            
    def execute(self) -> Any:
        """
        Основная логика операции.
        Должна быть переопределена в дочерних классах.
        """
        raise NotImplementedError("Метод execute должен быть переопределен")


class MaterialsLoadWorker(AsyncOperation):
    """
    Воркер для загрузки материалов.
    """
    
    def __init__(self, materials_service, parent=None):
        super().__init__(parent)
        self.materials_service = materials_service
        self.set_operation_name("Загрузка материалов")
        
    def execute(self) -> List[Dict]:
        """Выполняет загрузку материалов."""
        try:
            self.update_progress(10, "Подключение к базе данных...")
            
            if self.check_cancellation():
                return []
                
            self.update_progress(30, "Получение списка материалов...")
            materials = self.materials_service.get_all_materials()
            
            if self.check_cancellation():
                return []
                
            self.update_progress(60, "Форматирование данных...")
            formatted_materials = self.materials_service.format_materials_for_display(materials)
            
            if self.check_cancellation():
                return []
                
            self.update_progress(90, "Завершение загрузки...")
            
            # Имитируем небольшую задержку для демонстрации
            time.sleep(0.1)
            
            self.update_progress(100, "Загрузка завершена")
            return formatted_materials
            
        except Exception as e:
            logger.error(f"Ошибка загрузки материалов: {e}")
            raise BusinessLogicError(
                message="Ошибка загрузки материалов",
                original_error=e
            )


class MaterialsSearchWorker(AsyncOperation):
    """
    Воркер для поиска материалов.
    """
    
    def __init__(self, materials_service, search_text: str, parent=None):
        super().__init__(parent)
        self.materials_service = materials_service
        self.search_text = search_text
        self.set_operation_name(f"Поиск материалов: '{search_text}'")
        
    def execute(self) -> List[Dict]:
        """Выполняет поиск материалов."""
        try:
            self.update_progress(20, "Выполнение поиска...")
            
            if self.check_cancellation():
                return []
                
            if len(self.search_text.strip()) < 2:
                # Возвращаем все материалы если поиск слишком короткий
                self.update_progress(50, "Загрузка всех материалов...")
                materials = self.materials_service.get_all_materials()
                formatted_materials = self.materials_service.format_materials_for_display(materials)
            else:
                # Выполняем поиск
                formatted_materials = self.materials_service.search_materials_with_formatting(self.search_text)
            
            if self.check_cancellation():
                return []
                
            self.update_progress(100, f"Найдено {len(formatted_materials)} материалов")
            return formatted_materials
            
        except Exception as e:
            logger.error(f"Ошибка поиска материалов: {e}")
            raise BusinessLogicError(
                message="Ошибка поиска материалов",
                original_error=e
            )


class ProgressWidget(QWidget):
    """
    Виджет для отображения прогресса операций.
    """
    
    cancel_requested = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._current_operation = None
        
    def _setup_ui(self):
        """Настраивает интерфейс виджета."""
        layout = QHBoxLayout(self)
        
        # Прогресс бар
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        
        # Статус операции
        self.status_label = QLabel("Готов")
        self.status_label.setMinimumWidth(200)
        layout.addWidget(self.status_label)
        
        # Кнопка отмены
        self.cancel_button = QPushButton("Отменить")
        self.cancel_button.clicked.connect(self.cancel_requested.emit)
        self.cancel_button.setEnabled(False)
        layout.addWidget(self.cancel_button)
        
        self.setVisible(False)
        
    def start_operation(self, operation: AsyncOperation):
        """
        Запускает отслеживание операции.
        
        Args:
            operation: Операция для отслеживания
        """
        self._current_operation = operation
        
        # Подключаем сигналы
        operation.progress_updated.connect(self.update_progress)
        operation.status_updated.connect(self.update_status)
        operation.finished.connect(self.operation_finished)
        
        # Подключаем отмену
        self.cancel_requested.connect(operation.cancel)
        
        # Показываем виджет
        self.setVisible(True)
        self.cancel_button.setEnabled(True)
        self.progress_bar.setValue(0)
        self.status_label.setText("Запуск операции...")
        
    def update_progress(self, value: int):
        """Обновляет прогресс."""
        self.progress_bar.setValue(value)
        
    def update_status(self, status: str):
        """Обновляет статус."""
        self.status_label.setText(status)
        
    def operation_finished(self):
        """Вызывается при завершении операции."""
        self.setVisible(False)
        self.cancel_button.setEnabled(False)
        self.progress_bar.setValue(0)
        self.status_label.setText("Готов")
        
        # Отключаем сигналы
        if self._current_operation:
            self._current_operation.progress_updated.disconnect(self.update_progress)
            self._current_operation.status_updated.disconnect(self.update_status)
            self._current_operation.finished.disconnect(self.operation_finished)
            self.cancel_requested.disconnect(self._current_operation.cancel)
            self._current_operation = None


class DebounceTimer:
    """
    Класс для реализации debounce функциональности.
    Задерживает выполнение операции до тех пор, пока не пройдет определенное время
    без новых вызовов.
    """
    
    def __init__(self, delay_ms: int = 300):
        self.delay_ms = delay_ms
        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.callback = None
        self.args = None
        self.kwargs = None
        
    def debounce(self, callback: Callable, *args, **kwargs):
        """
        Выполняет callback с задержкой.
        Если метод вызывается снова до истечения задержки,
        предыдущий вызов отменяется.
        """
        self.callback = callback
        self.args = args
        self.kwargs = kwargs
        
        # Останавливаем предыдущий таймер
        if self.timer.isActive():
            self.timer.stop()
            
        # Подключаем callback и запускаем таймер
        self.timer.timeout.connect(self._execute_callback)
        self.timer.start(self.delay_ms)
        
    def _execute_callback(self):
        """Выполняет отложенный callback."""
        if self.callback:
            try:
                self.callback(*self.args, **self.kwargs)
            except Exception as e:
                logger.error(f"Ошибка в debounce callback: {e}")
            finally:
                self.timer.timeout.disconnect(self._execute_callback)
                self.callback = None
                self.args = None
                self.kwargs = None 
"""
Расширенная система логирования для полноценной отладки приложения.
Включает профилирование, трассировку, структурированное логирование и мониторинг.
"""

import logging
import logging.handlers
import os
import json
import traceback
import functools
import time
import threading
import sys
from datetime import datetime
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path

from PyQt5.QtCore import QObject, pyqtSignal


class LogLevel(Enum):
    """Уровни логирования."""
    TRACE = 5
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50


@dataclass
class LogEntry:
    """Структурированная запись лога."""
    timestamp: str
    level: str
    logger_name: str
    module: str
    function: str
    line: int
    message: str
    extra_data: Optional[Dict[str, Any]] = None
    exception: Optional[str] = None
    thread_id: Optional[int] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None


@dataclass
class PerformanceMetrics:
    """Метрики производительности."""
    function_name: str
    execution_time: float
    memory_usage: Optional[float] = None
    cpu_usage: Optional[float] = None
    arguments: Optional[Dict[str, Any]] = None
    result_size: Optional[int] = None


class StructuredFormatter(logging.Formatter):
    """Форматтер для структурированного JSON логирования."""
    
    def __init__(self, include_extra: bool = True):
        super().__init__()
        self.include_extra = include_extra
    
    def format(self, record):
        """Форматирует запись в JSON."""
        # Базовая информация
        log_entry = LogEntry(
            timestamp=datetime.fromtimestamp(record.created).isoformat(),
            level=record.levelname,
            logger_name=record.name,
            module=record.module if hasattr(record, 'module') else '',
            function=record.funcName if hasattr(record, 'funcName') else '',
            line=record.lineno if hasattr(record, 'lineno') else 0,
            message=record.getMessage(),
            thread_id=record.thread if hasattr(record, 'thread') else None
        )
        
        # Дополнительные данные
        if self.include_extra and hasattr(record, 'extra_data'):
            log_entry.extra_data = record.extra_data
        
        if hasattr(record, 'user_id'):
            log_entry.user_id = record.user_id
            
        if hasattr(record, 'session_id'):
            log_entry.session_id = record.session_id
        
        # Информация об исключении
        if record.exc_info:
            log_entry.exception = self.formatException(record.exc_info)
        
        return json.dumps(asdict(log_entry), ensure_ascii=False, indent=None)


class ColoredConsoleFormatter(logging.Formatter):
    """Цветной форматтер для консольного вывода."""
    
    COLORS = {
        'TRACE': '\033[90m',      # Серый
        'DEBUG': '\033[36m',      # Циан
        'INFO': '\033[32m',       # Зеленый
        'WARNING': '\033[33m',    # Желтый
        'ERROR': '\033[31m',      # Красный
        'CRITICAL': '\033[91m',   # Ярко-красный
        'RESET': '\033[0m'        # Сброс
    }
    
    def format(self, record):
        """Форматирует запись с цветами."""
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        reset = self.COLORS['RESET']
        
        # Основной формат
        log_format = (
            f"{color}%(asctime)s{reset} | "
            f"{color}%(levelname)-8s{reset} | "
            f"%(name)-20s | "
            f"%(funcName)-15s:%(lineno)-3d | "
            f"%(message)s"
        )
        
        formatter = logging.Formatter(log_format, datefmt='%H:%M:%S')
        formatted = formatter.format(record)
        
        # Добавляем исключения
        if record.exc_info:
            formatted += f"\n{color}EXCEPTION:{reset}\n{self.formatException(record.exc_info)}"
        
        return formatted


class PerformanceLogger:
    """Логгер для мониторинга производительности."""
    
    def __init__(self, logger_name: str = 'performance'):
        self.logger = logging.getLogger(logger_name)
        self.metrics: List[PerformanceMetrics] = []
        self._lock = threading.Lock()
    
    def log_execution_time(self, func: Callable) -> Callable:
        """Декоратор для логирования времени выполнения функций."""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            
            try:
                result = func(*args, **kwargs)
                execution_time = time.perf_counter() - start_time
                
                # Определяем размер результата
                result_size = None
                if hasattr(result, '__len__'):
                    try:
                        result_size = len(result)
                    except:
                        pass
                
                # Создаем метрики
                metrics = PerformanceMetrics(
                    function_name=f"{func.__module__}.{func.__qualname__}",
                    execution_time=execution_time,
                    arguments=self._serialize_args(args, kwargs),
                    result_size=result_size
                )
                
                # Логируем
                self._log_metrics(metrics)
                
                return result
                
            except Exception as e:
                execution_time = time.perf_counter() - start_time
                
                self.logger.error(
                    f"Функция {func.__qualname__} завершилась с ошибкой за {execution_time:.4f}с",
                    extra={
                        'extra_data': {
                            'execution_time': execution_time,
                            'exception': str(e),
                            'arguments': self._serialize_args(args, kwargs)
                        }
                    }
                )
                raise
        
        return wrapper
    
    def _serialize_args(self, args, kwargs) -> Dict[str, Any]:
        """Сериализует аргументы функции для логирования."""
        try:
            serialized = {}
            
            # Позиционные аргументы
            if args:
                serialized['args'] = []
                for i, arg in enumerate(args):
                    try:
                        if hasattr(arg, '__dict__'):
                            serialized['args'].append(f"<{type(arg).__name__} object>")
                        else:
                            serialized['args'].append(str(arg)[:100])  # Ограничиваем длину
                    except:
                        serialized['args'].append(f"<unprintable {type(arg).__name__}>")
            
            # Именованные аргументы
            if kwargs:
                serialized['kwargs'] = {}
                for key, value in kwargs.items():
                    try:
                        if hasattr(value, '__dict__'):
                            serialized['kwargs'][key] = f"<{type(value).__name__} object>"
                        else:
                            serialized['kwargs'][key] = str(value)[:100]
                    except:
                        serialized['kwargs'][key] = f"<unprintable {type(value).__name__}>"
            
            return serialized
            
        except Exception:
            return {"error": "Failed to serialize arguments"}
    
    def _log_metrics(self, metrics: PerformanceMetrics):
        """Логирует метрики производительности."""
        with self._lock:
            self.metrics.append(metrics)
        
        # Определяем уровень логирования на основе времени выполнения
        if metrics.execution_time > 5.0:
            level = logging.WARNING
            message = f"МЕДЛЕННАЯ функция {metrics.function_name}: {metrics.execution_time:.4f}с"
        elif metrics.execution_time > 1.0:
            level = logging.INFO
            message = f"Функция {metrics.function_name}: {metrics.execution_time:.4f}с"
        else:
            level = logging.DEBUG
            message = f"Функция {metrics.function_name}: {metrics.execution_time:.4f}с"
        
        self.logger.log(level, message, extra={
            'extra_data': asdict(metrics)
        })
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Возвращает сводку по метрикам производительности."""
        with self._lock:
            if not self.metrics:
                return {"total_calls": 0}
            
            total_calls = len(self.metrics)
            total_time = sum(m.execution_time for m in self.metrics)
            avg_time = total_time / total_calls
            max_time = max(m.execution_time for m in self.metrics)
            min_time = min(m.execution_time for m in self.metrics)
            
            # Топ самых медленных функций
            sorted_metrics = sorted(self.metrics, key=lambda m: m.execution_time, reverse=True)
            slowest_functions = [
                {
                    "function": m.function_name,
                    "execution_time": m.execution_time
                }
                for m in sorted_metrics[:10]
            ]
            
            return {
                "total_calls": total_calls,
                "total_time": total_time,
                "average_time": avg_time,
                "max_time": max_time,
                "min_time": min_time,
                "slowest_functions": slowest_functions
            }


class DatabaseLogger:
    """Логгер для операций с базой данных."""
    
    def __init__(self, logger_name: str = 'database'):
        self.logger = logging.getLogger(logger_name)
    
    def log_query(self, query: str, params: Optional[tuple] = None, 
                  execution_time: Optional[float] = None):
        """Логирует SQL запрос."""
        message = f"SQL Query: {query[:200]}..."
        
        extra_data = {
            'query': query,
            'params': params,
            'execution_time': execution_time
        }
        
        if execution_time and execution_time > 1.0:
            self.logger.warning(f"МЕДЛЕННЫЙ запрос ({execution_time:.4f}с): {message}",
                              extra={'extra_data': extra_data})
        else:
            self.logger.debug(message, extra={'extra_data': extra_data})
    
    def log_connection(self, action: str, database_path: str):
        """Логирует подключение к базе данных."""
        self.logger.info(f"База данных {action}: {database_path}")
    
    def log_transaction(self, action: str, affected_rows: int = 0):
        """Логирует транзакции."""
        self.logger.info(f"Транзакция {action}, затронуто строк: {affected_rows}")


class UILogger:
    """Логгер для действий пользовательского интерфейса."""
    
    def __init__(self, logger_name: str = 'ui'):
        self.logger = logging.getLogger(logger_name)
    
    def log_user_action(self, action: str, widget: str, details: Optional[Dict] = None):
        """Логирует действия пользователя."""
        message = f"Пользователь: {action} в {widget}"
        
        extra_data = {
            'action': action,
            'widget': widget,
            'details': details or {}
        }
        
        self.logger.info(message, extra={'extra_data': extra_data})
    
    def log_window_event(self, event: str, window: str):
        """Логирует события окон."""
        self.logger.debug(f"Окно {window}: {event}")
    
    def log_error_dialog(self, title: str, message: str, error: Optional[Exception] = None):
        """Логирует ошибки, показанные пользователю."""
        self.logger.error(f"Ошибка показана пользователю: {title} - {message}",
                         extra={'extra_data': {'error': str(error) if error else None}})


class LogMonitor(QObject):
    """Монитор логов с Qt сигналами."""
    
    # Сигналы для интеграции с UI
    error_occurred = pyqtSignal(str, str)  # title, message
    warning_occurred = pyqtSignal(str)     # message
    performance_alert = pyqtSignal(str, float)  # function_name, execution_time
    
    def __init__(self):
        super().__init__()
        self.handlers: List[logging.Handler] = []
    
    def add_handler(self, handler: logging.Handler):
        """Добавляет обработчик для мониторинга."""
        if isinstance(handler, MonitoringHandler):
            handler.set_monitor(self)
        self.handlers.append(handler)
    
    def emit_error(self, title: str, message: str):
        """Генерирует сигнал ошибки."""
        self.error_occurred.emit(title, message)
    
    def emit_warning(self, message: str):
        """Генерирует сигнал предупреждения."""
        self.warning_occurred.emit(message)
    
    def emit_performance_alert(self, function_name: str, execution_time: float):
        """Генерирует сигнал о проблемах производительности."""
        self.performance_alert.emit(function_name, execution_time)


class MonitoringHandler(logging.Handler):
    """Обработчик для мониторинга критических событий."""
    
    def __init__(self):
        super().__init__()
        self.monitor: Optional[LogMonitor] = None
    
    def set_monitor(self, monitor: LogMonitor):
        """Устанавливает монитор для отправки сигналов."""
        self.monitor = monitor
    
    def emit(self, record):
        """Обрабатывает запись лога."""
        if not self.monitor:
            return
        
        try:
            # Ошибки и критические события
            if record.levelno >= logging.ERROR:
                title = f"Ошибка в {record.name}"
                message = record.getMessage()
                self.monitor.emit_error(title, message)
            
            # Предупреждения
            elif record.levelno == logging.WARNING:
                self.monitor.emit_warning(record.getMessage())
            
            # Проблемы производительности
            if (hasattr(record, 'extra_data') and 
                record.extra_data and 
                'execution_time' in record.extra_data):
                
                execution_time = record.extra_data['execution_time']
                if execution_time > 5.0:  # Более 5 секунд
                    function_name = record.extra_data.get('function_name', 'unknown')
                    self.monitor.emit_performance_alert(function_name, execution_time)
        
        except Exception:
            # Не должно генерировать исключения в логгере
            pass


class EnhancedLogManager:
    """Менеджер расширенной системы логирования."""
    
    def __init__(self, app_name: str = "MaterialControl", log_dir: str = "logs"):
        self.app_name = app_name
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        self.performance_logger = PerformanceLogger()
        self.database_logger = DatabaseLogger()
        self.ui_logger = UILogger()
        self.monitor = LogMonitor()
        
        self._setup_logging()
    
    def _setup_logging(self):
        """Настраивает систему логирования."""
        # Добавляем уровень TRACE
        logging.addLevelName(LogLevel.TRACE.value, 'TRACE')
        
        # Корневой логгер
        root_logger = logging.getLogger()
        root_logger.setLevel(LogLevel.TRACE.value)
        
        # Очищаем существующие обработчики
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Создаем обработчики
        self._create_file_handlers()
        self._create_console_handler()
        self._create_monitoring_handler()
    
    def _create_file_handlers(self):
        """Создает файловые обработчики."""
        # Основной лог файл с ротацией
        main_log_file = self.log_dir / f"{self.app_name.lower()}.log"
        main_handler = logging.handlers.RotatingFileHandler(
            main_log_file, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'
        )
        main_handler.setLevel(logging.DEBUG)
        main_handler.setFormatter(StructuredFormatter())
        
        # Лог только ошибок
        error_log_file = self.log_dir / f"{self.app_name.lower()}_errors.log"
        error_handler = logging.handlers.RotatingFileHandler(
            error_log_file, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(StructuredFormatter())
        
        # Лог производительности
        perf_log_file = self.log_dir / f"{self.app_name.lower()}_performance.log"
        perf_handler = logging.handlers.RotatingFileHandler(
            perf_log_file, maxBytes=5*1024*1024, backupCount=2, encoding='utf-8'
        )
        perf_handler.setLevel(logging.DEBUG)
        perf_handler.setFormatter(StructuredFormatter())
        perf_handler.addFilter(lambda record: 'performance' in record.name)
        
        # Добавляем к корневому логгеру
        root_logger = logging.getLogger()
        root_logger.addHandler(main_handler)
        root_logger.addHandler(error_handler)
        root_logger.addHandler(perf_handler)
    
    def _create_console_handler(self):
        """Создает консольный обработчик."""
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(ColoredConsoleFormatter())
        
        logging.getLogger().addHandler(console_handler)
    
    def _create_monitoring_handler(self):
        """Создает обработчик мониторинга."""
        monitoring_handler = MonitoringHandler()
        monitoring_handler.setLevel(logging.WARNING)
        
        self.monitor.add_handler(monitoring_handler)
        logging.getLogger().addHandler(monitoring_handler)
    
    def get_logger(self, name: str) -> logging.Logger:
        """Получает логгер с заданным именем."""
        return logging.getLogger(name)
    
    def log_system_info(self):
        """Логирует информацию о системе при запуске."""
        import platform
        import psutil
        
        logger = self.get_logger('system')
        
        system_info = {
            'platform': platform.platform(),
            'python_version': platform.python_version(),
            'cpu_count': psutil.cpu_count(),
            'memory_total': psutil.virtual_memory().total,
            'memory_available': psutil.virtual_memory().available,
            'disk_usage': dict(psutil.disk_usage('/'))
        }
        
        logger.info("Запуск приложения", extra={'extra_data': system_info})
    
    def create_performance_decorator(self):
        """Создает декоратор для мониторинга производительности."""
        return self.performance_logger.log_execution_time
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Возвращает сводку по производительности."""
        return self.performance_logger.get_metrics_summary()
    
    def log_user_action(self, action: str, widget: str, details: Optional[Dict] = None,
                       user_id: Optional[str] = None):
        """Логирует действие пользователя."""
        logger = self.get_logger('user_actions')
        
        extra = {'extra_data': {'action': action, 'widget': widget, 'details': details}}
        if user_id:
            extra['user_id'] = user_id
        
        logger.info(f"Действие пользователя: {action} в {widget}", extra=extra)
    
    def log_database_operation(self, operation: str, table: str, 
                             affected_rows: int = 0, execution_time: float = 0):
        """Логирует операцию с базой данных."""
        logger = self.get_logger('database')
        
        extra_data = {
            'operation': operation,
            'table': table,
            'affected_rows': affected_rows,
            'execution_time': execution_time
        }
        
        message = f"БД операция: {operation} в таблице {table}"
        if execution_time > 1.0:
            logger.warning(f"МЕДЛЕННАЯ {message} ({execution_time:.4f}с)",
                         extra={'extra_data': extra_data})
        else:
            logger.debug(message, extra={'extra_data': extra_data})
    
    def log_error_with_context(self, error: Exception, context: str, 
                             extra_data: Optional[Dict] = None):
        """Логирует ошибку с контекстом."""
        logger = self.get_logger('errors')
        
        error_data = {
            'error_type': type(error).__name__,
            'error_message': str(error),
            'context': context,
            'traceback': traceback.format_exc(),
            'extra_data': extra_data
        }
        
        logger.error(f"Ошибка в {context}: {error}", extra={'extra_data': error_data})


# Глобальный менеджер логирования
_log_manager: Optional[EnhancedLogManager] = None


def initialize_logging(app_name: str = "MaterialControl", log_dir: str = "logs", 
                      enable_performance: bool = True) -> EnhancedLogManager:
    """Инициализирует расширенную систему логирования."""
    global _log_manager
    
    if _log_manager is None:
        _log_manager = EnhancedLogManager(app_name, log_dir)
        
        if enable_performance:
            # Устанавливаем минимальный уровень для performance логгера
            performance_logger = logging.getLogger('performance')
            performance_logger.setLevel(logging.DEBUG)
        
        # Логируем информацию о системе при инициализации
        try:
            _log_manager.log_system_info()
        except Exception as e:
            # Fallback логирование если что-то пошло не так
            logging.basicConfig(level=logging.INFO)
            logging.error(f"Ошибка инициализации расширенного логирования: {e}")
    
    return _log_manager


def get_enhanced_logger(name: str) -> logging.Logger:
    """Получает расширенный логгер."""
    if _log_manager is None:
        initialize_logging()
    
    return _log_manager.get_logger(name)


def performance_monitor(func: Callable) -> Callable:
    """Декоратор для мониторинга производительности функций."""
    if _log_manager is None:
        initialize_logging()
    
    return _log_manager.create_performance_decorator()(func)


def log_user_action(action: str, widget: str, details: Optional[Dict] = None,
                   user_id: Optional[str] = None):
    """Удобная функция для логирования действий пользователя."""
    if _log_manager is None:
        initialize_logging()
    
    _log_manager.log_user_action(action, widget, details, user_id)


def log_database_operation(operation: str, table: str, 
                         affected_rows: int = 0, execution_time: float = 0):
    """Удобная функция для логирования операций с БД."""
    if _log_manager is None:
        initialize_logging()
    
    _log_manager.log_database_operation(operation, table, affected_rows, execution_time)


def log_error_with_context(error: Exception, context: str, 
                         extra_data: Optional[Dict] = None):
    """Удобная функция для логирования ошибок с контекстом."""
    if _log_manager is None:
        initialize_logging()
    
    _log_manager.log_error_with_context(error, context, extra_data)


# Пример использования
if __name__ == "__main__":
    # Инициализация
    log_manager = initialize_logging("TestApp", "test_logs")
    
    # Получение логгеров
    logger = get_enhanced_logger('test_module')
    
    # Примеры логирования
    logger.info("Тестовое сообщение")
    logger.debug("Отладочная информация", extra={'extra_data': {'key': 'value'}})
    
    # Тест производительности
    @performance_monitor
    def test_function():
        time.sleep(0.1)
        return "result"
    
    result = test_function()
    
    # Сводка производительности
    summary = log_manager.get_performance_summary()
    print("Performance Summary:", summary) 
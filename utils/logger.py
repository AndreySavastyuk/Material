"""
Система логирования для приложения "Система контроля материалов".

Поддерживает:
- Ротацию логов
- Разные уровни логирования для модулей
- Аудит критических операций
- Форматирование сообщений
- Конфигурацию через config.ini
"""

import logging
import logging.handlers
import os
from typing import Optional, Dict, Any
from datetime import datetime
from pathlib import Path

from utils.config import config_manager


class ColoredFormatter(logging.Formatter):
    """Форматтер с цветным выводом для консоли."""
    
    # Цветовые коды ANSI
    COLORS = {
        'DEBUG': '\033[36m',     # Голубой
        'INFO': '\033[32m',      # Зеленый
        'WARNING': '\033[33m',   # Желтый
        'ERROR': '\033[31m',     # Красный
        'CRITICAL': '\033[35m',  # Фиолетовый
        'RESET': '\033[0m'       # Сброс цвета
    }
    
    def format(self, record):
        # Добавляем цвет к уровню логирования
        if hasattr(record, 'levelname'):
            color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
            record.levelname = f"{color}{record.levelname}{self.COLORS['RESET']}"
        
        return super().format(record)


class AuditLogger:
    """Специальный логгер для аудита критических операций."""
    
    def __init__(self, audit_file: str = "audit.log"):
        """
        Инициализация аудит логгера.
        
        Args:
            audit_file: Путь к файлу аудита
        """
        self.audit_file = audit_file
        self._setup_audit_logger()
    
    def _setup_audit_logger(self):
        """Настройка логгера аудита."""
        self.logger = logging.getLogger('audit')
        self.logger.setLevel(logging.INFO)
        
        # Удаляем существующие обработчики
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        
        # Создаем обработчик файла с ротацией
        handler = logging.handlers.RotatingFileHandler(
            self.audit_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        
        # Специальный формат для аудита
        formatter = logging.Formatter(
            '%(asctime)s | %(user)s | %(action)s | %(object_id)s | %(description)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        
        # Не передавать логи в родительские логгеры
        self.logger.propagate = False
    
    def log_action(self, user: Dict[str, Any], action: str, object_id: int, description: str):
        """
        Логирование действия пользователя.
        
        Args:
            user: Данные пользователя
            action: Действие (create, update, delete и т.д.)
            object_id: ID объекта
            description: Описание действия
        """
        extra = {
            'user': user.get('login', 'unknown'),
            'action': action,
            'object_id': object_id,
            'description': description
        }
        
        self.logger.info('User action', extra=extra)


class AppLogger:
    """Основной класс для управления логированием приложения."""
    
    # Конфигурация уровней логирования для модулей
    MODULE_LEVELS = {
        'gui': logging.INFO,
        'db': logging.DEBUG,
        'services': logging.INFO,
        'repositories': logging.DEBUG,
        'utils': logging.WARNING,
        'migrations': logging.INFO,
        'lab': logging.INFO,
        'otk': logging.INFO,
        'audit': logging.INFO,
    }
    
    def __init__(self):
        """Инициализация системы логирования."""
        self.loggers: Dict[str, logging.Logger] = {}
        self.audit_logger = AuditLogger()
        self._setup_logging()
    
    def _get_log_level_from_config(self) -> int:
        """Получение уровня логирования из конфигурации."""
        level_str = config_manager.get('LOGGING', 'level', 'INFO').upper()
        return getattr(logging, level_str, logging.INFO)
    
    def _get_log_file_from_config(self) -> str:
        """Получение пути к файлу логов из конфигурации."""
        return config_manager.get('LOGGING', 'file', 'app.log')
    
    def _get_max_bytes_from_config(self) -> int:
        """Получение максимального размера файла логов."""
        return config_manager.get_int('LOGGING', 'max_bytes', 10 * 1024 * 1024)  # 10MB
    
    def _get_backup_count_from_config(self) -> int:
        """Получение количества backup файлов."""
        return config_manager.get_int('LOGGING', 'backup_count', 5)
    
    def _setup_logging(self):
        """Настройка основной системы логирования."""
        # Получаем настройки из конфигурации
        log_level = self._get_log_level_from_config()
        log_file = self._get_log_file_from_config()
        max_bytes = self._get_max_bytes_from_config()
        backup_count = self._get_backup_count_from_config()
        
        # Создаем директорию для логов если не существует
        log_dir = Path(log_file).parent
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Корневой логгер
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)
        
        # Удаляем существующие обработчики
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Форматтер для файлов
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Форматтер для консоли (с цветами)
        console_formatter = ColoredFormatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
        
        # Обработчик файла с ротацией
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(log_level)
        
        # Обработчик консоли
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(logging.INFO)  # В консоль выводим только INFO+
        
        # Добавляем обработчики
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)
        
        # Настраиваем логгеры для внешних библиотек
        self._setup_external_loggers()
    
    def _setup_external_loggers(self):
        """Настройка логгеров для внешних библиотек."""
        # Отключаем избыточное логирование SQLite
        logging.getLogger('sqlite3').setLevel(logging.WARNING)
        
        # Настройка для PyQt5
        logging.getLogger('PyQt5').setLevel(logging.WARNING)
        
        # Настройка для requests (если используется)
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        logging.getLogger('requests').setLevel(logging.WARNING)
    
    def get_logger(self, name: str) -> logging.Logger:
        """
        Получение логгера для модуля.
        
        Args:
            name: Имя модуля (gui, db, services и т.д.)
            
        Returns:
            Настроенный логгер
        """
        if name not in self.loggers:
            logger = logging.getLogger(name)
            
            # Устанавливаем уровень логирования для модуля
            module_level = self.MODULE_LEVELS.get(name, logging.INFO)
            logger.setLevel(module_level)
            
            self.loggers[name] = logger
        
        return self.loggers[name]
    
    def get_module_logger(self, module_path: str) -> logging.Logger:
        """
        Получение логгера на основе пути модуля.
        
        Args:
            module_path: Путь к модулю (например, 'gui.main_window')
            
        Returns:
            Настроенный логгер
        """
        # Определяем основной модуль из пути
        main_module = module_path.split('.')[0]
        return self.get_logger(main_module)
    
    def log_audit(self, user: Dict[str, Any], action: str, object_id: int, description: str):
        """
        Логирование в аудит.
        
        Args:
            user: Данные пользователя
            action: Действие
            object_id: ID объекта
            description: Описание
        """
        self.audit_logger.log_action(user, action, object_id, description)
    
    def set_level(self, module: str, level: int):
        """
        Установка уровня логирования для модуля.
        
        Args:
            module: Имя модуля
            level: Уровень логирования
        """
        if module in self.loggers:
            self.loggers[module].setLevel(level)
        
        # Обновляем конфигурацию
        self.MODULE_LEVELS[module] = level


# Глобальный экземпляр системы логирования
app_logger = AppLogger()


def get_logger(name: str = None) -> logging.Logger:
    """
    Удобная функция для получения логгера.
    
    Args:
        name: Имя модуля или None для автоопределения
        
    Returns:
        Настроенный логгер
    """
    if name is None:
        import inspect
        frame = inspect.currentframe().f_back
        module_name = frame.f_globals.get('__name__', 'unknown')
        name = module_name.split('.')[0] if '.' in module_name else module_name
    
    return app_logger.get_logger(name)


def log_audit(user: Dict[str, Any], action: str, object_id: int, description: str):
    """
    Удобная функция для аудит логирования.
    
    Args:
        user: Данные пользователя
        action: Действие
        object_id: ID объекта
        description: Описание
    """
    app_logger.log_audit(user, action, object_id, description)


def setup_development_logging():
    """Настройка логирования для разработки (более подробное)."""
    app_logger.set_level('db', logging.DEBUG)
    app_logger.set_level('repositories', logging.DEBUG)
    app_logger.set_level('services', logging.DEBUG)


def setup_production_logging():
    """Настройка логирования для продакшена (менее подробное)."""
    app_logger.set_level('db', logging.INFO)
    app_logger.set_level('repositories', logging.INFO)
    app_logger.set_level('services', logging.INFO)
    app_logger.set_level('utils', logging.ERROR)


def log_performance(func):
    """
    Декоратор для логирования времени выполнения функций.
    
    Args:
        func: Функция для логирования
        
    Returns:
        Обернутая функция
    """
    import functools
    import time
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logger = get_logger()
        start_time = time.time()
        
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            
            if execution_time > 1.0:  # Логируем только медленные операции
                logger.warning(
                    f"Медленная операция: {func.__name__} выполнялась {execution_time:.2f} сек"
                )
            else:
                logger.debug(f"{func.__name__} выполнилась за {execution_time:.2f} сек")
            
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(
                f"Ошибка в {func.__name__} после {execution_time:.2f} сек: {e}"
            )
            raise
    
    return wrapper


# Пример использования в коде:
# from utils.logger import get_logger, log_audit, log_performance
#
# logger = get_logger('gui')
# logger.info("Запуск главного окна")
#
# @log_performance
# def slow_function():
#     time.sleep(2)
#
# log_audit(user, 'create_material', material_id, 'Создан новый материал') 
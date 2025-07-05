"""
Тесты для системы логирования.
"""

import pytest
import logging
import tempfile
import os
from unittest.mock import patch, MagicMock
from pathlib import Path

from utils.logger import (
    AppLogger, AuditLogger, get_logger, log_audit,
    setup_development_logging, setup_production_logging,
    log_performance
)


@pytest.mark.unit
class TestAppLogger:
    """Тесты для основного класса логирования."""
    
    def test_app_logger_initialization(self):
        """Тест инициализации AppLogger."""
        app_logger = AppLogger()
        
        assert app_logger is not None
        assert app_logger.loggers == {}
        assert app_logger.audit_logger is not None
    
    def test_get_logger_creates_new_logger(self):
        """Тест создания нового логгера."""
        app_logger = AppLogger()
        
        logger = app_logger.get_logger('test_module')
        
        assert logger is not None
        assert 'test_module' in app_logger.loggers
        assert isinstance(logger, logging.Logger)
    
    def test_get_logger_returns_existing_logger(self):
        """Тест возврата существующего логгера."""
        app_logger = AppLogger()
        
        logger1 = app_logger.get_logger('test_module')
        logger2 = app_logger.get_logger('test_module')
        
        assert logger1 is logger2
    
    def test_module_levels_configuration(self):
        """Тест конфигурации уровней логирования для модулей."""
        app_logger = AppLogger()
        
        # Проверяем, что уровни модулей настроены
        assert 'gui' in app_logger.MODULE_LEVELS
        assert 'db' in app_logger.MODULE_LEVELS
        assert 'services' in app_logger.MODULE_LEVELS
        
        # Проверяем, что логгер получает правильный уровень
        db_logger = app_logger.get_logger('db')
        assert db_logger.level == app_logger.MODULE_LEVELS['db']
    
    def test_set_level(self):
        """Тест установки уровня логирования."""
        app_logger = AppLogger()
        
        logger = app_logger.get_logger('test_module')
        original_level = logger.level
        
        app_logger.set_level('test_module', logging.CRITICAL)
        
        assert logger.level == logging.CRITICAL
        assert app_logger.MODULE_LEVELS['test_module'] == logging.CRITICAL


@pytest.mark.unit
class TestAuditLogger:
    """Тесты для аудит логгера."""
    
    def test_audit_logger_initialization(self):
        """Тест инициализации AuditLogger."""
        with tempfile.NamedTemporaryFile(suffix='.log', delete=False) as tmp_file:
            audit_file = tmp_file.name
        
        try:
            audit_logger = AuditLogger(audit_file)
            
            assert audit_logger is not None
            assert audit_logger.audit_file == audit_file
            assert audit_logger.logger is not None
            
            # Закрываем обработчики для освобождения файла
            for handler in audit_logger.logger.handlers:
                handler.close()
            
        finally:
            if os.path.exists(audit_file):
                try:
                    os.unlink(audit_file)
                except PermissionError:
                    # Игнорируем ошибку на Windows
                    pass
    
    def test_log_action(self):
        """Тест логирования действий."""
        with tempfile.NamedTemporaryFile(suffix='.log', delete=False) as tmp_file:
            audit_file = tmp_file.name
        
        try:
            audit_logger = AuditLogger(audit_file)
            
            user = {'login': 'test_user', 'role': 'admin'}
            audit_logger.log_action(user, 'create', 123, 'Test action')
            
            # Закрываем обработчики для освобождения файла
            for handler in audit_logger.logger.handlers:
                handler.close()
            
            # Проверяем, что файл создан и содержит запись
            assert os.path.exists(audit_file)
            
            with open(audit_file, 'r', encoding='utf-8') as f:
                content = f.read()
                assert 'test_user' in content
                assert 'create' in content
                assert '123' in content
                assert 'Test action' in content
                
        finally:
            if os.path.exists(audit_file):
                try:
                    os.unlink(audit_file)
                except PermissionError:
                    # Игнорируем ошибку на Windows
                    pass


@pytest.mark.unit
class TestLoggerFunctions:
    """Тесты для вспомогательных функций логирования."""
    
    def test_get_logger_function(self):
        """Тест функции get_logger."""
        logger = get_logger('test_module')
        
        assert logger is not None
        assert isinstance(logger, logging.Logger)
    
    def test_get_logger_auto_detection(self):
        """Тест автоопределения имени модуля."""
        logger = get_logger()
        
        assert logger is not None
        assert isinstance(logger, logging.Logger)
    
    def test_log_audit_function(self):
        """Тест функции log_audit."""
        user = {'login': 'test_user'}
        
        # Не должно вызывать исключений
        log_audit(user, 'test_action', 1, 'Test description')
    
    def test_setup_development_logging(self):
        """Тест настройки логирования для разработки."""
        # Не должно вызывать исключений
        setup_development_logging()
    
    def test_setup_production_logging(self):
        """Тест настройки логирования для продакшена."""
        # Не должно вызывать исключений
        setup_production_logging()


@pytest.mark.unit
class TestLogPerformanceDecorator:
    """Тесты для декоратора логирования производительности."""
    
    def test_log_performance_fast_function(self):
        """Тест декоратора для быстрой функции."""
        @log_performance
        def fast_function():
            return "result"
        
        result = fast_function()
        assert result == "result"
    
    def test_log_performance_slow_function(self):
        """Тест декоратора для медленной функции."""
        import time
        
        @log_performance
        def slow_function():
            time.sleep(0.1)  # Небольшая задержка для теста
            return "slow_result"
        
        result = slow_function()
        assert result == "slow_result"
    
    def test_log_performance_exception(self):
        """Тест декоратора при исключении."""
        @log_performance
        def failing_function():
            raise ValueError("Test error")
        
        with pytest.raises(ValueError, match="Test error"):
            failing_function()


@pytest.mark.integration
class TestLoggerIntegration:
    """Интеграционные тесты для системы логирования."""
    
    def test_logger_with_config_manager(self):
        """Тест интеграции с менеджером конфигурации."""
        with patch('utils.config.config_manager') as mock_config:
            mock_config.get.return_value = 'DEBUG'
            mock_config.get_int.return_value = 1024
            
            app_logger = AppLogger()
            
            assert app_logger is not None
    
    def test_multiple_loggers_different_modules(self):
        """Тест создания логгеров для разных модулей."""
        gui_logger = get_logger('gui')
        db_logger = get_logger('db')
        services_logger = get_logger('services')
        
        assert gui_logger != db_logger
        assert db_logger != services_logger
        assert gui_logger != services_logger
    
    def test_log_rotation(self):
        """Тест ротации логов."""
        import tempfile
        import shutil
        
        temp_dir = tempfile.mkdtemp()
        
        try:
            log_file = os.path.join(temp_dir, 'test.log')
            
            # Создаем логгер с маленьким размером файла для теста
            import logging.handlers
            
            logger = logging.getLogger('test_rotation')
            logger.handlers.clear()  # Очищаем существующие обработчики
            
            handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=100,  # Очень маленький размер для теста
                backupCount=2
            )
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
            
            # Записываем много данных чтобы вызвать ротацию
            for i in range(20):
                logger.info(f"Test log message {i} with some extra text to make it longer")
            
            # Закрываем обработчик
            handler.close()
            logger.removeHandler(handler)
            
            # Проверяем, что файлы ротации созданы
            files = os.listdir(temp_dir)
            log_files = [f for f in files if f.startswith('test.log')]
            
            assert len(log_files) > 1  # Должен быть основной файл и бэкапы
            
        finally:
            # Очищаем временную директорию
            try:
                shutil.rmtree(temp_dir)
            except PermissionError:
                # Игнорируем ошибку на Windows
                pass


@pytest.mark.unit
class TestColoredFormatter:
    """Тесты для цветного форматтера."""
    
    def test_colored_formatter_adds_colors(self):
        """Тест добавления цветов к сообщениям."""
        from utils.logger import ColoredFormatter
        
        formatter = ColoredFormatter('%(levelname)s - %(message)s')
        
        # Создаем тестовую запись
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='',
            lineno=0,
            msg='Test message',
            args=(),
            exc_info=None
        )
        
        formatted = formatter.format(record)
        
        # Проверяем, что цветовые коды добавлены
        assert '\033[32m' in formatted  # Зеленый цвет для INFO
        assert '\033[0m' in formatted   # Сброс цвета 
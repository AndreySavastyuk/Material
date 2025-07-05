"""
Тесты для декораторов и обработчиков ошибок.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
from PyQt5.QtWidgets import QWidget, QApplication, QMessageBox
from PyQt5.QtCore import QTimer

from utils.error_handlers import (
    ErrorHandler, handle_gui_errors, handle_database_errors,
    handle_validation_errors, safe_execute, create_error_message,
    show_success_message, show_error, show_warning, show_info,
    confirm_action, error_handler
)
from utils.exceptions import (
    BaseApplicationError, ValidationError, DatabaseError,
    DuplicateRecordError, IntegrityConstraintError,
    ErrorSeverity, ErrorCategory
)


# Фикстура для QApplication (нужна для Qt виджетов)
@pytest.fixture(scope="session")
def qapp():
    """Создает QApplication для тестов."""
    import sys
    if not QApplication.instance():
        app = QApplication(sys.argv)
    else:
        app = QApplication.instance()
    yield app


@pytest.mark.unit
class TestErrorHandler:
    """Тесты класса ErrorHandler."""
    
    def setup_method(self):
        """Настройка для каждого теста."""
        self.handler = ErrorHandler()
    
    def test_initialization(self):
        """Тест инициализации обработчика."""
        assert self.handler.logger is not None
        assert self.handler._error_counters == {}
        assert self.handler._suppressed_errors == set()
    
    @patch('utils.error_handlers.QMessageBox')
    def test_handle_error_basic(self, mock_message_box):
        """Тест базовой обработки ошибки."""
        error = BaseApplicationError("Test error")
        
        result = self.handler.handle_error(error)
        
        assert result is True
        assert error.error_code in self.handler._error_counters
        assert self.handler._error_counters[error.error_code] == 1
    
    @patch('utils.error_handlers.QMessageBox')
    def test_handle_error_with_context(self, mock_message_box):
        """Тест обработки ошибки с контекстом."""
        error = ValidationError("Validation failed")
        context = "test_function"
        
        result = self.handler.handle_error(error, context=context)
        
        assert result is True
    
    @patch('utils.error_handlers.QMessageBox')
    def test_handle_error_with_user_data(self, mock_message_box):
        """Тест обработки ошибки с данными пользователя."""
        error = BaseApplicationError(
            "Critical error",
            severity=ErrorSeverity.CRITICAL
        )
        user_data = {'login': 'test_user', 'role': 'admin'}
        
        with patch('utils.error_handlers.log_audit') as mock_audit:
            result = self.handler.handle_error(error, user_data=user_data)
            
            assert result is True
            mock_audit.assert_called_once()
    
    def test_wrap_standard_exception_value_error(self):
        """Тест оборачивания ValueError."""
        error = ValueError("Invalid value")
        
        wrapped = self.handler._wrap_standard_exception(error)
        
        assert isinstance(wrapped, ValidationError)
        assert wrapped.original_error == error
    
    def test_wrap_standard_exception_file_not_found(self):
        """Тест оборачивания FileNotFoundError."""
        error = FileNotFoundError("File not found")
        
        wrapped = self.handler._wrap_standard_exception(error)
        
        assert isinstance(wrapped, BaseApplicationError)
        assert wrapped.category == ErrorCategory.FILE_SYSTEM
        assert wrapped.original_error == error
    
    def test_wrap_standard_exception_unknown(self):
        """Тест оборачивания неизвестного исключения."""
        error = RuntimeError("Unknown error")
        
        wrapped = self.handler._wrap_standard_exception(error)
        
        assert isinstance(wrapped, BaseApplicationError)
        assert wrapped.original_error == error
    
    def test_error_counters(self):
        """Тест счетчиков ошибок."""
        error = BaseApplicationError("Test error", error_code="TEST_001")
        
        # Первая ошибка
        self.handler._update_error_counters(error)
        assert self.handler._error_counters["TEST_001"] == 1
        assert "TEST_001" not in self.handler._suppressed_errors
        
        # Повторные ошибки
        for _ in range(3):
            self.handler._update_error_counters(error)
        
        assert self.handler._error_counters["TEST_001"] == 4
        assert "TEST_001" in self.handler._suppressed_errors
    
    def test_get_error_statistics(self):
        """Тест получения статистики ошибок."""
        error1 = BaseApplicationError("Error 1", error_code="TEST_001")
        error2 = BaseApplicationError("Error 2", error_code="TEST_002")
        
        self.handler._update_error_counters(error1)
        self.handler._update_error_counters(error2)
        self.handler._update_error_counters(error1)
        
        stats = self.handler.get_error_statistics()
        
        assert stats["TEST_001"] == 2
        assert stats["TEST_002"] == 1
    
    def test_reset_error_counters(self):
        """Тест сброса счетчиков ошибок."""
        error = BaseApplicationError("Test error", error_code="TEST_001")
        
        self.handler._update_error_counters(error)
        assert len(self.handler._error_counters) > 0
        
        self.handler.reset_error_counters()
        
        assert len(self.handler._error_counters) == 0
        assert len(self.handler._suppressed_errors) == 0


@pytest.mark.unit
class TestGuiErrorDecorator:
    """Тесты декоратора handle_gui_errors."""
    
    def test_decorator_success(self):
        """Тест успешного выполнения функции."""
        @handle_gui_errors()
        def test_function():
            return "success"
        
        result = test_function()
        assert result == "success"
    
    @patch('utils.error_handlers.error_handler')
    def test_decorator_with_exception(self, mock_handler):
        """Тест обработки исключения декоратором."""
        @handle_gui_errors()
        def test_function():
            raise ValueError("Test error")
        
        result = test_function()
        
        assert result is None  # Исключение подавлено
        mock_handler.handle_error.assert_called_once()
    
    @patch('utils.error_handlers.error_handler')
    def test_decorator_no_suppress(self, mock_handler):
        """Тест декоратора без подавления исключений."""
        @handle_gui_errors(suppress_exceptions=False)
        def test_function():
            raise ValueError("Test error")
        
        with pytest.raises(ValueError):
            test_function()
        
        mock_handler.handle_error.assert_called_once()
    
    @patch('utils.error_handlers.error_handler')
    def test_decorator_no_dialog(self, mock_handler):
        """Тест декоратора без показа диалога."""
        @handle_gui_errors(show_dialog=False)
        def test_function():
            raise ValueError("Test error")
        
        test_function()
        
        # Проверяем, что обработчик вызван без parent_widget
        args, kwargs = mock_handler.handle_error.call_args
        assert kwargs['parent_widget'] is None
    
    @patch('utils.error_handlers.error_handler')
    def test_decorator_with_context(self, mock_handler):
        """Тест декоратора с контекстом."""
        @handle_gui_errors(context="test_context")
        def test_function():
            raise ValueError("Test error")
        
        test_function()
        
        args, kwargs = mock_handler.handle_error.call_args
        assert kwargs['context'] == "test_context"


@pytest.mark.unit
class TestDatabaseErrorDecorator:
    """Тесты декоратора handle_database_errors."""
    
    def test_decorator_success(self):
        """Тест успешного выполнения функции."""
        @handle_database_errors("test operation")
        def test_function():
            return "success"
        
        result = test_function()
        assert result == "success"
    
    def test_decorator_unique_constraint(self):
        """Тест обработки UNIQUE constraint ошибки."""
        @handle_database_errors("create user")
        def test_function():
            raise Exception("UNIQUE constraint failed")
        
        with pytest.raises(DuplicateRecordError) as exc_info:
            test_function()
        
        assert "create user" in str(exc_info.value)
    
    def test_decorator_foreign_key_constraint(self):
        """Тест обработки FOREIGN KEY constraint ошибки."""
        @handle_database_errors("delete record")
        def test_function():
            raise Exception("FOREIGN KEY constraint failed")
        
        with pytest.raises(IntegrityConstraintError) as exc_info:
            test_function()
        
        assert "delete record" in str(exc_info.value)
    
    def test_decorator_general_db_error(self):
        """Тест обработки общей ошибки БД."""
        @handle_database_errors("update record")
        def test_function():
            raise Exception("Database error")
        
        with pytest.raises(DatabaseError) as exc_info:
            test_function()
        
        assert "update record" in str(exc_info.value)


@pytest.mark.unit
class TestValidationErrorDecorator:
    """Тесты декоратора handle_validation_errors."""
    
    def test_decorator_success(self):
        """Тест успешного выполнения функции."""
        @handle_validation_errors
        def test_function():
            return "success"
        
        result = test_function()
        assert result == "success"
    
    def test_decorator_with_value_error(self):
        """Тест обработки ValueError."""
        @handle_validation_errors
        def test_function():
            raise ValueError("Invalid value")
        
        with pytest.raises(ValidationError) as exc_info:
            test_function()
        
        assert "test_function" in str(exc_info.value)
    
    def test_decorator_with_non_value_error(self):
        """Тест обработки не ValueError исключения."""
        @handle_validation_errors
        def test_function():
            raise RuntimeError("Runtime error")
        
        with pytest.raises(RuntimeError):
            test_function()


@pytest.mark.unit
class TestSafeExecute:
    """Тесты функции safe_execute."""
    
    def test_safe_execute_success(self):
        """Тест успешного выполнения."""
        def test_function(x, y):
            return x + y
        
        result = safe_execute(test_function, 2, 3)
        assert result == 5
    
    def test_safe_execute_with_exception(self):
        """Тест обработки исключения."""
        def test_function():
            raise ValueError("Error")
        
        result = safe_execute(test_function, default_value="default")
        assert result == "default"
    
    def test_safe_execute_with_kwargs(self):
        """Тест с ключевыми аргументами."""
        def test_function(x, y=1):
            return x * y
        
        result = safe_execute(test_function, 5, y=3)
        assert result == 15
    
    def test_safe_execute_with_error_message(self):
        """Тест с сообщением об ошибке."""
        def test_function():
            raise ValueError("Error")
        
        with patch('utils.error_handlers.logger') as mock_logger:
            result = safe_execute(
                test_function,
                default_value=None,
                error_message="Custom error message"
            )
            
            assert result is None
            assert mock_logger.error.call_count == 2  # Две записи в лог


@pytest.mark.unit
class TestMessageBoxFunctions:
    """Тесты функций для отображения сообщений."""
    
    @patch('utils.error_handlers.QMessageBox')
    def test_create_error_message(self, mock_message_box):
        """Тест создания сообщения об ошибке."""
        mock_msg = Mock()
        mock_message_box.return_value = mock_msg
        
        result = create_error_message(
            "Error Title",
            "Error Message",
            "Error Details"
        )
        
        assert result == mock_msg
        mock_msg.setIcon.assert_called_with(QMessageBox.Critical)
        mock_msg.setWindowTitle.assert_called_with("Error Title")
        mock_msg.setText.assert_called_with("Error Message")
        mock_msg.setDetailedText.assert_called_with("Error Details")
    
    @patch('utils.error_handlers.QMessageBox')
    def test_show_error(self, mock_message_box):
        """Тест показа ошибки."""
        show_error("Test error message")
        
        mock_message_box.critical.assert_called_once_with(
            None, "Ошибка", "Test error message"
        )
    
    @patch('utils.error_handlers.QMessageBox')
    def test_show_warning(self, mock_message_box):
        """Тест показа предупреждения."""
        show_warning("Test warning message")
        
        mock_message_box.warning.assert_called_once_with(
            None, "Предупреждение", "Test warning message"
        )
    
    @patch('utils.error_handlers.QMessageBox')
    def test_show_info(self, mock_message_box):
        """Тест показа информации."""
        show_info("Test info message")
        
        mock_message_box.information.assert_called_once_with(
            None, "Информация", "Test info message"
        )
    
    @patch('utils.error_handlers.QMessageBox')
    def test_confirm_action_yes(self, mock_message_box):
        """Тест подтверждения действия (Да)."""
        mock_message_box.question.return_value = QMessageBox.Yes
        
        result = confirm_action("Confirm this action?")
        
        assert result is True
        mock_message_box.question.assert_called_once()
    
    @patch('utils.error_handlers.QMessageBox')
    def test_confirm_action_no(self, mock_message_box):
        """Тест подтверждения действия (Нет)."""
        mock_message_box.question.return_value = QMessageBox.No
        
        result = confirm_action("Confirm this action?")
        
        assert result is False
        mock_message_box.question.assert_called_once()


@pytest.mark.integration
class TestErrorHandlerIntegration:
    """Интеграционные тесты обработчика ошибок."""
    
    def test_full_error_handling_chain(self):
        """Тест полной цепочки обработки ошибок."""
        handler = ErrorHandler()
        
        # Создаем ошибку с полной информацией
        error = ValidationError(
            "Test validation error",
            field_name="email",
            field_value="invalid@",
            suggestions=["Check email format"]
        )
        
        with patch('utils.error_handlers.QMessageBox') as mock_message_box:
            result = handler.handle_error(error, context="test_context")
            
            assert result is True
            assert error.error_code in handler._error_counters
    
    @patch('utils.error_handlers.error_handler')
    def test_decorator_integration_with_qt_widget(self, mock_handler):
        """Тест интеграции декоратора с Qt виджетом."""
        
        class TestWidget(QWidget):
            def __init__(self):
                super().__init__()
                self.user = {'login': 'test_user'}
            
            @handle_gui_errors()
            def test_method(self):
                raise ValueError("Test error")
        
        widget = TestWidget()
        widget.test_method()
        
        # Проверяем, что обработчик вызван
        mock_handler.handle_error.assert_called_once()
        
        # Проверяем параметры
        args, kwargs = mock_handler.handle_error.call_args
        assert isinstance(args[0], ValueError)
        assert kwargs['user_data'] == {'login': 'test_user'}
    
    def test_multiple_error_suppression(self):
        """Тест подавления повторяющихся ошибок."""
        handler = ErrorHandler()
        error = BaseApplicationError("Repeating error", error_code="REPEAT_001")
        
        with patch('utils.error_handlers.QMessageBox') as mock_message_box:
            # Первые несколько ошибок должны показываться
            for i in range(3):
                handler.handle_error(error)
            
            # После 3 ошибок они должны подавляться
            handler.handle_error(error)
            handler.handle_error(error)
            
            assert error.error_code in handler._suppressed_errors
            assert handler._error_counters[error.error_code] == 5
    
    def test_error_severity_handling(self):
        """Тест обработки разных уровней серьезности."""
        handler = ErrorHandler()
        
        errors = [
            BaseApplicationError("Low", severity=ErrorSeverity.LOW),
            BaseApplicationError("Medium", severity=ErrorSeverity.MEDIUM),
            BaseApplicationError("High", severity=ErrorSeverity.HIGH),
            BaseApplicationError("Critical", severity=ErrorSeverity.CRITICAL)
        ]
        
        with patch('utils.error_handlers.QMessageBox'):
            for error in errors:
                result = handler.handle_error(error)
                assert result is True


@pytest.mark.unit
class TestErrorDialogComponents:
    """Тесты компонентов диалога ошибок."""
    
    def test_error_dialog_creation(self, qapp):
        """Тест создания диалога ошибок."""
        error = BaseApplicationError(
            "Test error",
            user_message="User friendly message",
            suggestions=["Try this", "Try that"]
        )
        
        from utils.error_handlers import ErrorDialog
        dialog = ErrorDialog(error)
        
        assert dialog.error == error
        assert dialog.windowTitle() == "Детали ошибки"
        assert dialog.isModal()
    
    def test_error_dialog_format_technical_details(self, qapp):
        """Тест форматирования технических деталей."""
        error = BaseApplicationError(
            "Test error",
            error_code="TEST_001",
            details={"key": "value"}
        )
        
        from utils.error_handlers import ErrorDialog
        dialog = ErrorDialog(error)
        
        details = dialog._format_technical_details()
        
        assert "TEST_001" in details
        assert "Test error" in details
        assert "key: value" in details 
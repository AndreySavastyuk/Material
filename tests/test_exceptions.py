"""
Тесты для системы обработки исключений.
"""

import pytest
from typing import Dict, Any
from unittest.mock import Mock, patch, MagicMock

from utils.exceptions import (
    BaseApplicationError, ValidationError, RequiredFieldError,
    InvalidFormatError, ValueOutOfRangeError, DatabaseError,
    ConnectionError, RecordNotFoundError, IntegrityConstraintError,
    DuplicateRecordError, BusinessLogicError, InsufficientPermissionsError,
    RecordInUseError, InvalidOperationError, AuthenticationError,
    InvalidCredentialsError, SessionExpiredError, NetworkError,
    TimeoutError, ServiceUnavailableError, FileSystemError,
    FileNotFoundError, FileAccessError, DiskSpaceError,
    ConfigurationError, MissingConfigurationError, InvalidConfigurationError,
    ExternalServiceError, TelegramError, ErrorSeverity, ErrorCategory,
    wrap_exception, is_user_error, get_error_suggestions
)


@pytest.mark.unit
class TestBaseApplicationError:
    """Тесты базового класса исключений."""
    
    def test_basic_initialization(self):
        """Тест базовой инициализации."""
        error = BaseApplicationError("Test message")
        
        assert error.message == "Test message"
        assert error.error_code is not None
        assert error.severity == ErrorSeverity.MEDIUM
        assert error.category == ErrorCategory.SYSTEM
        assert error.details == {}
        assert error.user_message is not None
        assert error.suggestions == []
        assert error.original_error is None
    
    def test_full_initialization(self):
        """Тест полной инициализации с параметрами."""
        original_error = ValueError("Original")
        details = {"key": "value"}
        suggestions = ["Fix this", "Try that"]
        
        error = BaseApplicationError(
            message="Test message",
            error_code="TEST_001",
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.VALIDATION,
            details=details,
            user_message="User message",
            suggestions=suggestions,
            original_error=original_error
        )
        
        assert error.message == "Test message"
        assert error.error_code == "TEST_001"
        assert error.severity == ErrorSeverity.HIGH
        assert error.category == ErrorCategory.VALIDATION
        assert error.details == details
        assert error.user_message == "User message"
        assert error.suggestions == suggestions
        assert error.original_error == original_error
    
    def test_to_dict(self):
        """Тест преобразования в словарь."""
        error = BaseApplicationError(
            "Test message",
            error_code="TEST_001",
            severity=ErrorSeverity.HIGH
        )
        
        result = error.to_dict()
        
        assert result['error_code'] == "TEST_001"
        assert result['message'] == "Test message"
        assert result['severity'] == "high"
        assert result['category'] == "system"
        assert isinstance(result['details'], dict)
        assert isinstance(result['suggestions'], list)
    
    def test_str_representation(self):
        """Тест строкового представления."""
        error = BaseApplicationError("Test message", error_code="TEST_001")
        
        assert str(error) == "[TEST_001] Test message"


@pytest.mark.unit
class TestValidationErrors:
    """Тесты ошибок валидации."""
    
    def test_validation_error(self):
        """Тест базовой ошибки валидации."""
        error = ValidationError("Invalid data", field_name="email", field_value="invalid")
        
        assert error.category == ErrorCategory.VALIDATION
        assert error.field_name == "email"
        assert error.field_value == "invalid"
        assert "field_name" in error.details
        assert error.details["field_name"] == "email"
    
    def test_required_field_error(self):
        """Тест ошибки обязательного поля."""
        error = RequiredFieldError("Field required", field_name="name")
        
        assert isinstance(error, ValidationError)
        assert "обязательно" in error.user_message.lower()
    
    def test_invalid_format_error(self):
        """Тест ошибки неверного формата."""
        error = InvalidFormatError("Invalid format", field_name="date")
        
        assert isinstance(error, ValidationError)
        assert "формат" in error.user_message.lower()
    
    def test_value_out_of_range_error(self):
        """Тест ошибки значения вне диапазона."""
        error = ValueOutOfRangeError(
            "Value out of range",
            field_name="age",
            field_value=150,
            min_value=0,
            max_value=120
        )
        
        assert isinstance(error, ValidationError)
        assert error.min_value == 0
        assert error.max_value == 120
        assert "0" in error.user_message
        assert "120" in error.user_message


@pytest.mark.unit
class TestDatabaseErrors:
    """Тесты ошибок базы данных."""
    
    def test_database_error(self):
        """Тест базовой ошибки БД."""
        error = DatabaseError("DB error")
        
        assert error.category == ErrorCategory.DATABASE
        assert error.severity == ErrorSeverity.HIGH
    
    def test_connection_error(self):
        """Тест ошибки подключения."""
        error = ConnectionError("Connection failed")
        
        assert isinstance(error, DatabaseError)
        assert "подключ" in error.user_message.lower()
    
    def test_record_not_found_error(self):
        """Тест ошибки отсутствия записи."""
        error = RecordNotFoundError(
            "Record not found",
            table_name="users",
            record_id=123
        )
        
        assert isinstance(error, DatabaseError)
        assert error.table_name == "users"
        assert error.record_id == 123
        assert "users" in error.user_message
    
    def test_integrity_constraint_error(self):
        """Тест ошибки целостности."""
        error = IntegrityConstraintError("Constraint violation")
        
        assert isinstance(error, DatabaseError)
        assert "целостност" in error.user_message.lower()
    
    def test_duplicate_record_error(self):
        """Тест ошибки дублирования."""
        error = DuplicateRecordError("Duplicate record")
        
        assert isinstance(error, DatabaseError)
        assert "существует" in error.user_message.lower()


@pytest.mark.unit
class TestBusinessLogicErrors:
    """Тесты ошибок бизнес-логики."""
    
    def test_business_logic_error(self):
        """Тест базовой ошибки бизнес-логики."""
        error = BusinessLogicError("Business rule violation")
        
        assert error.category == ErrorCategory.BUSINESS_LOGIC
        assert error.severity == ErrorSeverity.MEDIUM
    
    def test_insufficient_permissions_error(self):
        """Тест ошибки недостатка прав."""
        error = InsufficientPermissionsError(
            "No permission",
            required_permission="admin"
        )
        
        assert isinstance(error, BusinessLogicError)
        assert error.category == ErrorCategory.AUTHORIZATION
        assert error.required_permission == "admin"
        assert "прав" in error.user_message.lower()
    
    def test_record_in_use_error(self):
        """Тест ошибки использования записи."""
        error = RecordInUseError(
            "Record in use",
            record_type="supplier",
            used_in=["materials", "orders"]
        )
        
        assert isinstance(error, BusinessLogicError)
        assert error.record_type == "supplier"
        assert error.used_in == ["materials", "orders"]
        assert "supplier" in error.user_message
    
    def test_invalid_operation_error(self):
        """Тест ошибки недопустимой операции."""
        error = InvalidOperationError(
            "Invalid operation",
            operation="delete",
            current_state="active"
        )
        
        assert isinstance(error, BusinessLogicError)
        assert error.operation == "delete"
        assert error.current_state == "active"


@pytest.mark.unit
class TestAuthenticationErrors:
    """Тесты ошибок аутентификации."""
    
    def test_authentication_error(self):
        """Тест базовой ошибки аутентификации."""
        error = AuthenticationError("Auth failed")
        
        assert error.category == ErrorCategory.AUTHENTICATION
        assert error.severity == ErrorSeverity.HIGH
    
    def test_invalid_credentials_error(self):
        """Тест ошибки неверных учетных данных."""
        error = InvalidCredentialsError("Invalid login")
        
        assert isinstance(error, AuthenticationError)
        assert "пароль" in error.user_message.lower()
    
    def test_session_expired_error(self):
        """Тест ошибки истечения сессии."""
        error = SessionExpiredError("Session expired")
        
        assert isinstance(error, AuthenticationError)
        assert "сессия" in error.user_message.lower()


@pytest.mark.unit
class TestNetworkErrors:
    """Тесты сетевых ошибок."""
    
    def test_network_error(self):
        """Тест базовой сетевой ошибки."""
        error = NetworkError("Network failed")
        
        assert error.category == ErrorCategory.NETWORK
        assert error.severity == ErrorSeverity.MEDIUM
    
    def test_timeout_error(self):
        """Тест ошибки таймаута."""
        error = TimeoutError("Request timeout")
        
        assert isinstance(error, NetworkError)
        assert "время" in error.user_message.lower()
    
    def test_service_unavailable_error(self):
        """Тест ошибки недоступности сервиса."""
        error = ServiceUnavailableError("Service down")
        
        assert isinstance(error, NetworkError)
        assert "недоступен" in error.user_message.lower()


@pytest.mark.unit
class TestFileSystemErrors:
    """Тесты ошибок файловой системы."""
    
    def test_file_system_error(self):
        """Тест базовой ошибки файловой системы."""
        error = FileSystemError("File error", file_path="/path/to/file")
        
        assert error.category == ErrorCategory.FILE_SYSTEM
        assert error.file_path == "/path/to/file"
        assert "/path/to/file" in error.details['file_path']
    
    def test_file_not_found_error(self):
        """Тест ошибки отсутствия файла."""
        error = FileNotFoundError("File not found", file_path="/missing/file")
        
        assert isinstance(error, FileSystemError)
        assert "/missing/file" in error.user_message
    
    def test_file_access_error(self):
        """Тест ошибки доступа к файлу."""
        error = FileAccessError("Access denied", file_path="/protected/file")
        
        assert isinstance(error, FileSystemError)
        assert "доступ" in error.user_message.lower()
    
    def test_disk_space_error(self):
        """Тест ошибки недостатка места."""
        error = DiskSpaceError("No space left")
        
        assert isinstance(error, FileSystemError)
        assert "мест" in error.user_message.lower()


@pytest.mark.unit
class TestConfigurationErrors:
    """Тесты ошибок конфигурации."""
    
    def test_configuration_error(self):
        """Тест базовой ошибки конфигурации."""
        error = ConfigurationError("Config error")
        
        assert error.category == ErrorCategory.CONFIGURATION
        assert error.severity == ErrorSeverity.HIGH
    
    def test_missing_configuration_error(self):
        """Тест ошибки отсутствия конфигурации."""
        error = MissingConfigurationError(
            "Missing config",
            config_key="database.host"
        )
        
        assert isinstance(error, ConfigurationError)
        assert error.config_key == "database.host"
        assert "database.host" in error.user_message
    
    def test_invalid_configuration_error(self):
        """Тест ошибки неверной конфигурации."""
        error = InvalidConfigurationError("Invalid config")
        
        assert isinstance(error, ConfigurationError)
        assert "конфигурац" in error.user_message.lower()


@pytest.mark.unit
class TestExternalServiceErrors:
    """Тесты ошибок внешних сервисов."""
    
    def test_external_service_error(self):
        """Тест базовой ошибки внешнего сервиса."""
        error = ExternalServiceError("Service error", service_name="API")
        
        assert error.category == ErrorCategory.EXTERNAL_SERVICE
        assert error.service_name == "API"
        assert "API" in error.user_message
    
    def test_telegram_error(self):
        """Тест ошибки Telegram."""
        error = TelegramError("Telegram failed")
        
        assert isinstance(error, ExternalServiceError)
        assert error.service_name == "Telegram"
        assert "Telegram" in error.user_message


@pytest.mark.unit
class TestUtilityFunctions:
    """Тесты вспомогательных функций."""
    
    def test_wrap_exception(self):
        """Тест оборачивания исключения."""
        original = ValueError("Original error")
        wrapped = wrap_exception(original, ValidationError)
        
        assert isinstance(wrapped, ValidationError)
        assert wrapped.original_error == original
        assert "Original error" in wrapped.message
    
    def test_wrap_exception_default_class(self):
        """Тест оборачивания с классом по умолчанию."""
        original = ValueError("Original error")
        wrapped = wrap_exception(original)
        
        assert isinstance(wrapped, BaseApplicationError)
        assert wrapped.original_error == original
    
    def test_is_user_error_true(self):
        """Тест определения пользовательской ошибки (True)."""
        validation_error = ValidationError("Validation failed")
        business_error = BusinessLogicError("Business rule violated")
        auth_error = AuthenticationError("Auth failed")
        
        assert is_user_error(validation_error) is True
        assert is_user_error(business_error) is True
        assert is_user_error(auth_error) is True
    
    def test_is_user_error_false(self):
        """Тест определения пользовательской ошибки (False)."""
        db_error = DatabaseError("DB failed")
        system_error = BaseApplicationError("System error")
        standard_error = ValueError("Standard error")
        
        assert is_user_error(db_error) is False
        assert is_user_error(system_error) is False
        assert is_user_error(standard_error) is False
    
    def test_get_error_suggestions_custom_error(self):
        """Тест получения предложений для кастомной ошибки."""
        suggestions = ["Fix this", "Try that"]
        error = BaseApplicationError("Error", suggestions=suggestions)
        
        result = get_error_suggestions(error)
        
        assert result == suggestions
    
    def test_get_error_suggestions_standard_errors(self):
        """Тест получения предложений для стандартных ошибок."""
        # Используем встроенные исключения Python
        import builtins
        
        value_error = ValueError("Invalid value")
        file_error = builtins.FileNotFoundError("File not found")
        permission_error = PermissionError("Access denied")
        connection_error = builtins.ConnectionError("Connection failed")
        
        value_suggestions = get_error_suggestions(value_error)
        file_suggestions = get_error_suggestions(file_error)
        permission_suggestions = get_error_suggestions(permission_error)
        connection_suggestions = get_error_suggestions(connection_error)
        
        assert len(value_suggestions) > 0
        assert len(file_suggestions) > 0
        assert len(permission_suggestions) > 0
        assert len(connection_suggestions) > 0
        
        assert "данных" in value_suggestions[0].lower()
        assert "файл" in file_suggestions[0].lower()
        assert "права" in permission_suggestions[0].lower()
        assert "сет" in connection_suggestions[0].lower()  # "сети" содержит "сет"
    
    def test_get_error_suggestions_unknown_error(self):
        """Тест получения предложений для неизвестной ошибки."""
        unknown_error = RuntimeError("Unknown error")
        
        result = get_error_suggestions(unknown_error)
        
        assert result == []


@pytest.mark.unit
class TestErrorSeverityAndCategory:
    """Тесты для перечислений уровней и категорий ошибок."""
    
    def test_error_severity_values(self):
        """Тест значений уровней ошибок."""
        assert ErrorSeverity.LOW.value == "low"
        assert ErrorSeverity.MEDIUM.value == "medium"
        assert ErrorSeverity.HIGH.value == "high"
        assert ErrorSeverity.CRITICAL.value == "critical"
    
    def test_error_category_values(self):
        """Тест значений категорий ошибок."""
        assert ErrorCategory.VALIDATION.value == "validation"
        assert ErrorCategory.DATABASE.value == "database"
        assert ErrorCategory.BUSINESS_LOGIC.value == "business_logic"
        assert ErrorCategory.NETWORK.value == "network"
        assert ErrorCategory.FILE_SYSTEM.value == "file_system"
        assert ErrorCategory.AUTHENTICATION.value == "authentication"
        assert ErrorCategory.AUTHORIZATION.value == "authorization"
        assert ErrorCategory.CONFIGURATION.value == "configuration"
        assert ErrorCategory.EXTERNAL_SERVICE.value == "external_service"
        assert ErrorCategory.SYSTEM.value == "system"


@pytest.mark.integration
class TestErrorIntegration:
    """Интеграционные тесты системы ошибок."""
    
    def test_error_chain(self):
        """Тест цепочки ошибок."""
        # Создаем цепочку: стандартная ошибка -> кастомная ошибка
        original = ValueError("Invalid input")
        validation_error = ValidationError(
            "Validation failed",
            field_name="email",
            original_error=original
        )
        business_error = BusinessLogicError(
            "Business rule violated",
            original_error=validation_error
        )
        
        # Проверяем, что цепочка сохранена
        assert business_error.original_error == validation_error
        assert validation_error.original_error == original
        
        # Проверяем информацию в ошибках
        assert business_error.category == ErrorCategory.BUSINESS_LOGIC
        assert validation_error.category == ErrorCategory.VALIDATION
        assert validation_error.field_name == "email"
    
    def test_error_serialization(self):
        """Тест сериализации ошибок."""
        error = ValidationError(
            "Validation failed",
            field_name="email",
            field_value="invalid@",
            suggestions=["Check email format", "Use valid domain"]
        )
        
        # Сериализуем в словарь
        error_dict = error.to_dict()
        
        # Проверяем все поля
        assert error_dict['error_code'] is not None
        assert error_dict['message'] == "Validation failed"
        assert error_dict['category'] == "validation"
        assert error_dict['severity'] == "medium"
        assert "field_name" in error_dict['details']
        assert len(error_dict['suggestions']) == 2 
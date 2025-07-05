"""
Система обработки исключений для приложения "Система контроля материалов".

Содержит иерархию кастомных исключений и утилиты для их обработки.
"""

from typing import Dict, Any, Optional, List
from enum import Enum


class ErrorSeverity(Enum):
    """Уровни важности ошибок."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Категории ошибок."""
    VALIDATION = "validation"
    DATABASE = "database"
    BUSINESS_LOGIC = "business_logic"
    NETWORK = "network"
    FILE_SYSTEM = "file_system"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    CONFIGURATION = "configuration"
    EXTERNAL_SERVICE = "external_service"
    SYSTEM = "system"


class BaseApplicationError(Exception):
    """
    Базовое исключение для всех ошибок приложения.
    
    Содержит дополнительную информацию для централизованной обработки.
    """
    
    def __init__(
        self,
        message: str,
        error_code: str = None,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        category: ErrorCategory = ErrorCategory.SYSTEM,
        details: Optional[Dict[str, Any]] = None,
        user_message: Optional[str] = None,
        suggestions: Optional[List[str]] = None,
        original_error: Optional[Exception] = None
    ):
        """
        Инициализация базового исключения.
        
        Args:
            message: Техническое сообщение об ошибке
            error_code: Уникальный код ошибки
            severity: Уровень важности
            category: Категория ошибки
            details: Дополнительная информация
            user_message: Сообщение для пользователя
            suggestions: Предложения по исправлению
            original_error: Исходное исключение
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self._generate_error_code()
        self.severity = severity
        self.category = category
        self.details = details or {}
        self.user_message = user_message or self._generate_user_message()
        self.suggestions = suggestions or []
        self.original_error = original_error
    
    def _generate_error_code(self) -> str:
        """Генерация кода ошибки."""
        class_name = self.__class__.__name__
        return f"{class_name.upper()}_001"
    
    def _generate_user_message(self) -> str:
        """Генерация сообщения для пользователя."""
        return "Произошла ошибка при выполнении операции."
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование исключения в словарь."""
        return {
            'error_code': self.error_code,
            'message': self.message,
            'user_message': self.user_message,
            'severity': self.severity.value,
            'category': self.category.value,
            'details': self.details,
            'suggestions': self.suggestions,
            'original_error': str(self.original_error) if self.original_error else None
        }
    
    def __str__(self) -> str:
        """Строковое представление исключения."""
        return f"[{self.error_code}] {self.message}"


# =============================================================================
# Валидационные исключения
# =============================================================================

class ValidationError(BaseApplicationError):
    """Ошибки валидации данных."""
    
    def __init__(
        self,
        message: str,
        field_name: str = None,
        field_value: Any = None,
        **kwargs
    ):
        kwargs.setdefault('severity', ErrorSeverity.MEDIUM)
        kwargs.setdefault('category', ErrorCategory.VALIDATION)
        
        # Устанавливаем атрибуты до вызова super().__init__
        self.field_name = field_name
        self.field_value = field_value
        
        super().__init__(message, **kwargs)
        
        if field_name:
            self.details.update({
                'field_name': field_name,
                'field_value': field_value
            })
    
    def _generate_user_message(self) -> str:
        if hasattr(self, 'field_name') and self.field_name:
            return f"Некорректные данные в поле '{self.field_name}'"
        return "Некорректные данные в форме"


class RequiredFieldError(ValidationError):
    """Ошибка отсутствия обязательного поля."""
    
    def _generate_user_message(self) -> str:
        if self.field_name:
            return f"Поле '{self.field_name}' обязательно для заполнения"
        return "Не все обязательные поля заполнены"


class InvalidFormatError(ValidationError):
    """Ошибка неверного формата данных."""
    
    def _generate_user_message(self) -> str:
        if self.field_name:
            return f"Неверный формат данных в поле '{self.field_name}'"
        return "Неверный формат данных"


class ValueOutOfRangeError(ValidationError):
    """Ошибка значения вне допустимого диапазона."""
    
    def __init__(
        self,
        message: str,
        field_name: str = None,
        field_value: Any = None,
        min_value: Any = None,
        max_value: Any = None,
        **kwargs
    ):
        # Устанавливаем атрибуты до вызова super().__init__
        self.min_value = min_value
        self.max_value = max_value
        
        super().__init__(message, field_name, field_value, **kwargs)
        
        if min_value is not None or max_value is not None:
            self.details.update({
                'min_value': min_value,
                'max_value': max_value
            })
    
    def _generate_user_message(self) -> str:
        if (hasattr(self, 'field_name') and self.field_name and 
            hasattr(self, 'min_value') and hasattr(self, 'max_value') and 
            self.min_value is not None and self.max_value is not None):
            return f"Значение поля '{self.field_name}' должно быть от {self.min_value} до {self.max_value}"
        elif hasattr(self, 'field_name') and self.field_name:
            return f"Значение поля '{self.field_name}' вне допустимого диапазона"
        return "Значение вне допустимого диапазона"


# =============================================================================
# Ошибки базы данных
# =============================================================================

class DatabaseError(BaseApplicationError):
    """Ошибки работы с базой данных."""
    
    def __init__(self, message: str, **kwargs):
        kwargs.setdefault('severity', ErrorSeverity.HIGH)
        kwargs.setdefault('category', ErrorCategory.DATABASE)
        super().__init__(message, **kwargs)
    
    def _generate_user_message(self) -> str:
        return "Ошибка при работе с базой данных"


class ConnectionError(DatabaseError):
    """Ошибка подключения к базе данных."""
    
    def _generate_user_message(self) -> str:
        return "Не удалось подключиться к базе данных"


class RecordNotFoundError(DatabaseError):
    """Ошибка отсутствия записи."""
    
    def __init__(
        self,
        message: str,
        table_name: str = None,
        record_id: Any = None,
        **kwargs
    ):
        kwargs.setdefault('severity', ErrorSeverity.MEDIUM)
        
        # Устанавливаем атрибуты до вызова super().__init__
        self.table_name = table_name
        self.record_id = record_id
        
        super().__init__(message, **kwargs)
        
        if table_name or record_id:
            self.details.update({
                'table_name': table_name,
                'record_id': record_id
            })
    
    def _generate_user_message(self) -> str:
        if hasattr(self, 'table_name') and self.table_name:
            return f"Запись не найдена в таблице '{self.table_name}'"
        return "Запись не найдена"


class IntegrityConstraintError(DatabaseError):
    """Ошибка нарушения целостности данных."""
    
    def _generate_user_message(self) -> str:
        return "Нарушение целостности данных. Проверьте связанные записи."


class DuplicateRecordError(DatabaseError):
    """Ошибка дублирования записи."""
    
    def _generate_user_message(self) -> str:
        return "Запись с такими данными уже существует"


# =============================================================================
# Бизнес-логика
# =============================================================================

class BusinessLogicError(BaseApplicationError):
    """Ошибки бизнес-логики."""
    
    def __init__(self, message: str, **kwargs):
        kwargs.setdefault('severity', ErrorSeverity.MEDIUM)
        kwargs.setdefault('category', ErrorCategory.BUSINESS_LOGIC)
        super().__init__(message, **kwargs)
    
    def _generate_user_message(self) -> str:
        return "Операция не может быть выполнена"


class InsufficientPermissionsError(BusinessLogicError):
    """Ошибка недостатка прав доступа."""
    
    def __init__(self, message: str, required_permission: str = None, **kwargs):
        kwargs.setdefault('severity', ErrorSeverity.HIGH)
        kwargs.setdefault('category', ErrorCategory.AUTHORIZATION)
        
        # Устанавливаем атрибуты до вызова super().__init__
        self.required_permission = required_permission
        
        super().__init__(message, **kwargs)
        
        if required_permission:
            self.details['required_permission'] = required_permission
    
    def _generate_user_message(self) -> str:
        return "У вас недостаточно прав для выполнения этой операции"


class RecordInUseError(BusinessLogicError):
    """Ошибка попытки удаления используемой записи."""
    
    def __init__(
        self,
        message: str,
        record_type: str = None,
        used_in: List[str] = None,
        **kwargs
    ):
        # Устанавливаем атрибуты до вызова super().__init__
        self.record_type = record_type
        self.used_in = used_in or []
        
        super().__init__(message, **kwargs)
        
        if record_type or used_in:
            self.details.update({
                'record_type': record_type,
                'used_in': used_in
            })
    
    def _generate_user_message(self) -> str:
        if (hasattr(self, 'record_type') and hasattr(self, 'used_in') and 
            self.record_type and self.used_in):
            return f"Нельзя удалить {self.record_type}: используется в {', '.join(self.used_in)}"
        return "Нельзя удалить: запись используется в других местах"


class InvalidOperationError(BusinessLogicError):
    """Ошибка недопустимой операции."""
    
    def __init__(
        self,
        message: str,
        operation: str = None,
        current_state: str = None,
        **kwargs
    ):
        # Устанавливаем атрибуты до вызова super().__init__
        self.operation = operation
        self.current_state = current_state
        
        super().__init__(message, **kwargs)
        
        if operation or current_state:
            self.details.update({
                'operation': operation,
                'current_state': current_state
            })
    
    def _generate_user_message(self) -> str:
        if hasattr(self, 'operation') and self.operation:
            return f"Операция '{self.operation}' не может быть выполнена"
        return "Недопустимая операция"


# =============================================================================
# Аутентификация и авторизация
# =============================================================================

class AuthenticationError(BaseApplicationError):
    """Ошибки аутентификации."""
    
    def __init__(self, message: str, **kwargs):
        kwargs.setdefault('severity', ErrorSeverity.HIGH)
        kwargs.setdefault('category', ErrorCategory.AUTHENTICATION)
        super().__init__(message, **kwargs)
    
    def _generate_user_message(self) -> str:
        return "Ошибка аутентификации"


class InvalidCredentialsError(AuthenticationError):
    """Ошибка неверных учетных данных."""
    
    def _generate_user_message(self) -> str:
        return "Неверное имя пользователя или пароль"


class SessionExpiredError(AuthenticationError):
    """Ошибка истечения сессии."""
    
    def _generate_user_message(self) -> str:
        return "Сессия истекла. Необходимо войти в систему заново."


class SecurityError(AuthenticationError):
    """Ошибки безопасности (brute force, подозрительная активность и т.д.)."""
    
    def __init__(
        self,
        message: str,
        security_reason: str = None,
        **kwargs
    ):
        kwargs.setdefault('severity', ErrorSeverity.HIGH)
        kwargs.setdefault('category', ErrorCategory.AUTHORIZATION)
        
        # Устанавливаем атрибуты до вызова super().__init__
        self.security_reason = security_reason
        
        super().__init__(message, **kwargs)
        
        if security_reason:
            self.details['security_reason'] = security_reason
    
    def _generate_user_message(self) -> str:
        return "Обнаружена подозрительная активность. Доступ ограничен."


# =============================================================================
# Сетевые ошибки
# =============================================================================

class NetworkError(BaseApplicationError):
    """Сетевые ошибки."""
    
    def __init__(self, message: str, **kwargs):
        kwargs.setdefault('severity', ErrorSeverity.MEDIUM)
        kwargs.setdefault('category', ErrorCategory.NETWORK)
        super().__init__(message, **kwargs)
    
    def _generate_user_message(self) -> str:
        return "Ошибка сетевого подключения"


class TimeoutError(NetworkError):
    """Ошибка таймаута."""
    
    def _generate_user_message(self) -> str:
        return "Превышено время ожидания ответа"


class ServiceUnavailableError(NetworkError):
    """Ошибка недоступности сервиса."""
    
    def _generate_user_message(self) -> str:
        return "Сервис временно недоступен"


# =============================================================================
# Файловая система
# =============================================================================

class FileSystemError(BaseApplicationError):
    """Ошибки файловой системы."""
    
    def __init__(self, message: str, file_path: str = None, **kwargs):
        kwargs.setdefault('severity', ErrorSeverity.MEDIUM)
        kwargs.setdefault('category', ErrorCategory.FILE_SYSTEM)
        
        # Устанавливаем атрибуты до вызова super().__init__
        self.file_path = file_path
        
        super().__init__(message, **kwargs)
        
        if file_path:
            self.details['file_path'] = file_path
    
    def _generate_user_message(self) -> str:
        return "Ошибка при работе с файлом"


class FileNotFoundError(FileSystemError):
    """Ошибка отсутствия файла."""
    
    def _generate_user_message(self) -> str:
        if hasattr(self, 'file_path') and self.file_path:
            return f"Файл не найден: {self.file_path}"
        return "Файл не найден"


class FileAccessError(FileSystemError):
    """Ошибка доступа к файлу."""
    
    def _generate_user_message(self) -> str:
        if hasattr(self, 'file_path') and self.file_path:
            return f"Нет доступа к файлу: {self.file_path}"
        return "Нет доступа к файлу"


class DiskSpaceError(FileSystemError):
    """Ошибка недостатка места на диске."""
    
    def _generate_user_message(self) -> str:
        return "Недостаточно места на диске"


# =============================================================================
# Конфигурация
# =============================================================================

class ConfigurationError(BaseApplicationError):
    """Ошибки конфигурации."""
    
    def __init__(self, message: str, **kwargs):
        kwargs.setdefault('severity', ErrorSeverity.HIGH)
        kwargs.setdefault('category', ErrorCategory.CONFIGURATION)
        super().__init__(message, **kwargs)
    
    def _generate_user_message(self) -> str:
        return "Ошибка конфигурации приложения"


class MissingConfigurationError(ConfigurationError):
    """Ошибка отсутствия конфигурации."""
    
    def __init__(
        self,
        message: str,
        config_key: str = None,
        **kwargs
    ):
        # Устанавливаем атрибуты до вызова super().__init__
        self.config_key = config_key
        
        super().__init__(message, **kwargs)
        
        if config_key:
            self.details['config_key'] = config_key
    
    def _generate_user_message(self) -> str:
        if hasattr(self, 'config_key') and self.config_key:
            return f"Отсутствует настройка: {self.config_key}"
        return "Отсутствует обязательная настройка"


class InvalidConfigurationError(ConfigurationError):
    """Ошибка неверной конфигурации."""
    
    def _generate_user_message(self) -> str:
        return "Неверная конфигурация приложения"


# =============================================================================
# Внешние сервисы
# =============================================================================

class ExternalServiceError(BaseApplicationError):
    """Ошибки внешних сервисов."""
    
    def __init__(
        self,
        message: str,
        service_name: str = None,
        **kwargs
    ):
        kwargs.setdefault('severity', ErrorSeverity.MEDIUM)
        kwargs.setdefault('category', ErrorCategory.EXTERNAL_SERVICE)
        
        # Устанавливаем атрибуты до вызова super().__init__
        self.service_name = service_name
        
        super().__init__(message, **kwargs)
        
        if service_name:
            self.details['service_name'] = service_name
    
    def _generate_user_message(self) -> str:
        if hasattr(self, 'service_name') and self.service_name:
            return f"Ошибка при работе с сервисом: {self.service_name}"
        return "Ошибка при работе с внешним сервисом"


class TelegramError(ExternalServiceError):
    """Ошибки Telegram бота."""
    
    def __init__(self, message: str, **kwargs):
        kwargs.setdefault('service_name', 'Telegram')
        super().__init__(message, **kwargs)
    
    def _generate_user_message(self) -> str:
        return "Ошибка при отправке Telegram уведомления"


# =============================================================================
# Утилиты для работы с исключениями
# =============================================================================

def wrap_exception(original_exception: Exception, error_class: type = None) -> BaseApplicationError:
    """
    Оборачивает стандартное исключение в кастомное.
    
    Args:
        original_exception: Исходное исключение
        error_class: Класс для обертывания (по умолчанию BaseApplicationError)
        
    Returns:
        Обернутое исключение
    """
    if error_class is None:
        error_class = BaseApplicationError
    
    return error_class(
        message=str(original_exception),
        original_error=original_exception
    )


def is_user_error(exception: Exception) -> bool:
    """
    Проверяет, является ли исключение ошибкой пользователя.
    
    Args:
        exception: Исключение для проверки
        
    Returns:
        True если это пользовательская ошибка
    """
    if isinstance(exception, BaseApplicationError):
        return exception.category in [
            ErrorCategory.VALIDATION,
            ErrorCategory.BUSINESS_LOGIC,
            ErrorCategory.AUTHENTICATION,
            ErrorCategory.AUTHORIZATION
        ]
    return False


def get_error_suggestions(exception: Exception) -> List[str]:
    """
    Получает предложения по исправлению ошибки.
    
    Args:
        exception: Исключение
        
    Returns:
        Список предложений
    """
    if isinstance(exception, BaseApplicationError):
        return exception.suggestions
    
    # Общие предложения для стандартных исключений
    suggestions = []
    
    # Используем полное имя класса для избежания конфликта
    exception_name = exception.__class__.__name__
    
    if isinstance(exception, ValueError):
        suggestions.append("Проверьте правильность введенных данных")
    elif exception_name == 'FileNotFoundError':  # Встроенный FileNotFoundError
        suggestions.append("Убедитесь, что файл существует")
    elif isinstance(exception, PermissionError):
        suggestions.append("Проверьте права доступа к файлу")
    elif exception_name == 'ConnectionError':  # Может быть встроенный
        suggestions.append("Проверьте подключение к сети")
    
    return suggestions 
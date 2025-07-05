"""
Декораторы и обработчики ошибок для GUI компонентов.

Предоставляет централизованную обработку ошибок с user-friendly сообщениями.
"""

import functools
import traceback
from typing import Callable, Any, Optional, Dict, Union, List
from PyQt5.QtWidgets import (
    QMessageBox, QWidget, QDialog, QApplication, QVBoxLayout, 
    QHBoxLayout, QLabel, QPushButton, QTextEdit, QCheckBox
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon, QPixmap

from utils.exceptions import (
    BaseApplicationError, ValidationError, DatabaseError, 
    BusinessLogicError, NetworkError, FileSystemError,
    ErrorSeverity, ErrorCategory, is_user_error, get_error_suggestions
)
from utils.logger import get_logger, log_audit


logger = get_logger('utils')


class ErrorDialog(QDialog):
    """Диалог для отображения детальной информации об ошибках."""
    
    def __init__(self, error: BaseApplicationError, parent: QWidget = None):
        super().__init__(parent)
        self.error = error
        self.setWindowTitle("Детали ошибки")
        self.setFixedSize(600, 400)
        self.setModal(True)
        self._setup_ui()
        
    def _setup_ui(self):
        """Настройка пользовательского интерфейса."""
        layout = QVBoxLayout(self)
        
        # Заголовок с иконкой
        header_layout = QHBoxLayout()
        
        # Иконка в зависимости от серьезности
        icon_label = QLabel()
        icon = self._get_severity_icon()
        if icon:
            icon_label.setPixmap(icon.pixmap(32, 32))
        
        # Сообщение для пользователя
        message_label = QLabel(self.error.user_message)
        message_label.setWordWrap(True)
        message_label.setStyleSheet("QLabel { font-weight: bold; font-size: 14px; }")
        
        header_layout.addWidget(icon_label)
        header_layout.addWidget(message_label)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        
        # Предложения по исправлению
        if self.error.suggestions:
            suggestions_label = QLabel("Рекомендации:")
            suggestions_label.setStyleSheet("QLabel { font-weight: bold; }")
            layout.addWidget(suggestions_label)
            
            for suggestion in self.error.suggestions:
                suggestion_label = QLabel(f"• {suggestion}")
                suggestion_label.setWordWrap(True)
                layout.addWidget(suggestion_label)
            
            layout.addWidget(QLabel(""))  # Пустая строка
        
        # Кнопка для показа технических деталей
        self.details_button = QPushButton("Показать технические детали")
        self.details_button.setCheckable(True)
        self.details_button.toggled.connect(self._toggle_details)
        layout.addWidget(self.details_button)
        
        # Поле для технических деталей
        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setMaximumHeight(150)
        self.details_text.hide()
        
        details_content = self._format_technical_details()
        self.details_text.setPlainText(details_content)
        
        layout.addWidget(self.details_text)
        
        # Кнопки управления
        buttons_layout = QHBoxLayout()
        
        copy_button = QPushButton("Копировать детали")
        copy_button.clicked.connect(self._copy_details)
        
        close_button = QPushButton("Закрыть")
        close_button.clicked.connect(self.accept)
        close_button.setDefault(True)
        
        buttons_layout.addWidget(copy_button)
        buttons_layout.addStretch()
        buttons_layout.addWidget(close_button)
        
        layout.addLayout(buttons_layout)
        
    def _get_severity_icon(self) -> Optional[QIcon]:
        """Получает иконку в зависимости от серьезности ошибки."""
        try:
            if self.error.severity == ErrorSeverity.CRITICAL:
                return self.style().standardIcon(self.style().SP_MessageBoxCritical)
            elif self.error.severity == ErrorSeverity.HIGH:
                return self.style().standardIcon(self.style().SP_MessageBoxWarning)
            elif self.error.severity == ErrorSeverity.MEDIUM:
                return self.style().standardIcon(self.style().SP_MessageBoxInformation)
            else:
                return self.style().standardIcon(self.style().SP_MessageBoxQuestion)
        except Exception:
            return None
    
    def _toggle_details(self, checked: bool):
        """Переключает видимость технических деталей."""
        if checked:
            self.details_text.show()
            self.details_button.setText("Скрыть технические детали")
            self.resize(600, 550)
        else:
            self.details_text.hide()
            self.details_button.setText("Показать технические детали")
            self.resize(600, 400)
    
    def _format_technical_details(self) -> str:
        """Форматирует технические детали ошибки."""
        lines = []
        
        lines.append(f"Код ошибки: {self.error.error_code}")
        lines.append(f"Категория: {self.error.category.value}")
        lines.append(f"Уровень: {self.error.severity.value}")
        lines.append(f"Сообщение: {self.error.message}")
        
        if self.error.details:
            lines.append("\nДетали:")
            for key, value in self.error.details.items():
                lines.append(f"  {key}: {value}")
        
        if self.error.original_error:
            lines.append(f"\nИсходная ошибка: {self.error.original_error}")
            
        return "\n".join(lines)
    
    def _copy_details(self):
        """Копирует детали ошибки в буфер обмена."""
        clipboard = QApplication.clipboard()
        clipboard.setText(self._format_technical_details())
        
        # Показываем уведомление
        QMessageBox.information(self, "Скопировано", "Детали ошибки скопированы в буфер обмена")


class ErrorHandler:
    """Централизованный обработчик ошибок."""
    
    def __init__(self):
        self.logger = get_logger('error_handler')
        self._error_counters: Dict[str, int] = {}
        self._suppressed_errors: set = set()
        
    def handle_error(
        self,
        error: Exception,
        context: str = None,
        parent_widget: QWidget = None,
        user_data: Dict[str, Any] = None
    ) -> bool:
        """
        Централизованная обработка ошибок.
        
        Args:
            error: Исключение для обработки
            context: Контекст возникновения ошибки
            parent_widget: Родительский виджет для диалогов
            user_data: Данные пользователя для аудита
            
        Returns:
            True если ошибка была обработана
        """
        try:
            # Преобразуем в базовую ошибку приложения если нужно
            if isinstance(error, BaseApplicationError):
                app_error = error
            else:
                app_error = self._wrap_standard_exception(error)
            
            # Логируем ошибку
            self._log_error(app_error, context, user_data)
            
            # Обновляем счетчики
            self._update_error_counters(app_error)
            
            # Показываем пользователю
            self._show_error_to_user(app_error, parent_widget)
            
            return True
            
        except Exception as e:
            # Критическая ошибка в обработчике ошибок
            self.logger.critical(f"Ошибка в обработчике ошибок: {e}")
            self._show_critical_error(parent_widget)
            return False
    
    def _wrap_standard_exception(self, error: Exception) -> BaseApplicationError:
        """Оборачивает стандартные исключения в кастомные."""
        # Определяем тип ошибки по исходному исключению
        if isinstance(error, ValueError):
            return ValidationError(
                message=str(error),
                original_error=error
            )
        elif isinstance(error, FileNotFoundError):
            return FileSystemError(
                message=str(error),
                original_error=error
            )
        elif isinstance(error, PermissionError):
            return FileSystemError(
                message=str(error),
                original_error=error
            )
        elif isinstance(error, ConnectionError):
            return NetworkError(
                message=str(error),
                original_error=error
            )
        else:
            return BaseApplicationError(
                message=str(error),
                original_error=error
            )
    
    def _log_error(
        self,
        error: BaseApplicationError,
        context: str = None,
        user_data: Dict[str, Any] = None
    ):
        """Логирует ошибку."""
        log_message = f"[{error.error_code}] {error.message}"
        if context:
            log_message = f"{context}: {log_message}"
        
        # Выбираем уровень логирования
        if error.severity == ErrorSeverity.CRITICAL:
            self.logger.critical(log_message)
        elif error.severity == ErrorSeverity.HIGH:
            self.logger.error(log_message)
        elif error.severity == ErrorSeverity.MEDIUM:
            self.logger.warning(log_message)
        else:
            self.logger.info(log_message)
        
        # Логируем детали
        if error.details:
            self.logger.debug(f"Детали ошибки: {error.details}")
        
        # Аудит для критических ошибок
        if error.severity in [ErrorSeverity.CRITICAL, ErrorSeverity.HIGH] and user_data:
            try:
                log_audit(
                    user_data,
                    'error_occurred',
                    0,
                    f"Ошибка {error.error_code}: {error.message}"
                )
            except Exception as e:
                self.logger.error(f"Ошибка аудита: {e}")
    
    def _update_error_counters(self, error: BaseApplicationError):
        """Обновляет счетчики ошибок."""
        error_key = error.error_code
        self._error_counters[error_key] = self._error_counters.get(error_key, 0) + 1
        
        # Подавляем повторяющиеся ошибки
        if self._error_counters[error_key] > 3:
            self._suppressed_errors.add(error_key)
    
    def _show_error_to_user(self, error: BaseApplicationError, parent_widget: QWidget = None):
        """Показывает ошибку пользователю."""
        # Проверяем, не подавлена ли ошибка
        if error.error_code in self._suppressed_errors:
            return
        
        # Выбираем способ отображения
        if error.severity == ErrorSeverity.CRITICAL:
            self._show_critical_error_dialog(error, parent_widget)
        elif error.severity == ErrorSeverity.HIGH:
            self._show_error_dialog(error, parent_widget)
        elif is_user_error(error):
            self._show_user_error_dialog(error, parent_widget)
        else:
            self._show_info_dialog(error, parent_widget)
    
    def _show_critical_error_dialog(self, error: BaseApplicationError, parent: QWidget = None):
        """Показывает диалог критической ошибки."""
        dialog = ErrorDialog(error, parent)
        dialog.exec_()
    
    def _show_error_dialog(self, error: BaseApplicationError, parent: QWidget = None):
        """Показывает диалог ошибки."""
        msg = QMessageBox(parent)
        msg.setIcon(QMessageBox.Critical)
        msg.setWindowTitle("Ошибка")
        msg.setText(error.user_message)
        
        if error.suggestions:
            msg.setInformativeText("\n".join(f"• {s}" for s in error.suggestions))
        
        msg.setDetailedText(f"Код ошибки: {error.error_code}\n{error.message}")
        msg.exec_()
    
    def _show_user_error_dialog(self, error: BaseApplicationError, parent: QWidget = None):
        """Показывает диалог пользовательской ошибки."""
        msg = QMessageBox(parent)
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle("Внимание")
        msg.setText(error.user_message)
        
        if error.suggestions:
            msg.setInformativeText("\n".join(f"• {s}" for s in error.suggestions))
        
        msg.exec_()
    
    def _show_info_dialog(self, error: BaseApplicationError, parent: QWidget = None):
        """Показывает информационный диалог."""
        msg = QMessageBox(parent)
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle("Информация")
        msg.setText(error.user_message)
        msg.exec_()
    
    def _show_critical_error(self, parent: QWidget = None):
        """Показывает критическую ошибку обработчика."""
        msg = QMessageBox(parent)
        msg.setIcon(QMessageBox.Critical)
        msg.setWindowTitle("Критическая ошибка")
        msg.setText("Произошла критическая ошибка в системе обработки ошибок.")
        msg.setInformativeText("Обратитесь к администратору системы.")
        msg.exec_()
    
    def get_error_statistics(self) -> Dict[str, int]:
        """Возвращает статистику ошибок."""
        return self._error_counters.copy()
    
    def reset_error_counters(self):
        """Сбрасывает счетчики ошибок."""
        self._error_counters.clear()
        self._suppressed_errors.clear()


# Глобальный экземпляр обработчика ошибок
error_handler = ErrorHandler()


def handle_gui_errors(
    show_dialog: bool = True,
    context: str = None,
    log_errors: bool = True,
    suppress_exceptions: bool = True
):
    """
    Декоратор для обработки ошибок в GUI методах.
    
    Args:
        show_dialog: Показывать диалог ошибки
        context: Контекст для логирования
        log_errors: Логировать ошибки
        suppress_exceptions: Подавлять исключения
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Пытаемся получить parent widget из self
                parent_widget = None
                if args and hasattr(args[0], 'parent'):
                    parent_widget = args[0].parent()
                elif args and isinstance(args[0], QWidget):
                    parent_widget = args[0]
                
                # Пытаемся получить пользовательские данные
                user_data = None
                if args and hasattr(args[0], 'user'):
                    user_data = args[0].user
                
                # Определяем контекст
                func_context = context or f"{func.__module__}.{func.__name__}"
                
                if log_errors:
                    # Обрабатываем ошибку
                    error_handler.handle_error(
                        e,
                        context=func_context,
                        parent_widget=parent_widget if show_dialog else None,
                        user_data=user_data
                    )
                
                if not suppress_exceptions:
                    raise
                
                return None
        
        return wrapper
    return decorator


def handle_database_errors(operation: str = None):
    """
    Декоратор для обработки ошибок базы данных.
    
    Args:
        operation: Описание операции
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Преобразуем в database ошибку
                if "UNIQUE constraint failed" in str(e):
                    from utils.exceptions import DuplicateRecordError
                    raise DuplicateRecordError(
                        f"Дублирование записи при {operation or 'операции с БД'}",
                        original_error=e
                    )
                elif "FOREIGN KEY constraint failed" in str(e):
                    from utils.exceptions import IntegrityConstraintError
                    raise IntegrityConstraintError(
                        f"Нарушение связей при {operation or 'операции с БД'}",
                        original_error=e
                    )
                else:
                    from utils.exceptions import DatabaseError
                    raise DatabaseError(
                        f"Ошибка БД при {operation or 'операции'}",
                        original_error=e
                    )
        
        return wrapper
    return decorator


def handle_validation_errors(func: Callable) -> Callable:
    """Декоратор для обработки ошибок валидации."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValueError as e:
            from utils.exceptions import ValidationError
            raise ValidationError(
                f"Ошибка валидации в {func.__name__}",
                original_error=e
            )
    
    return wrapper


def safe_execute(
    func: Callable,
    *args,
    default_value: Any = None,
    error_message: str = None,
    **kwargs
) -> Any:
    """
    Безопасно выполняет функцию с обработкой ошибок.
    
    Args:
        func: Функция для выполнения
        *args: Аргументы функции
        default_value: Значение по умолчанию при ошибке
        error_message: Сообщение об ошибке
        **kwargs: Ключевые аргументы функции
        
    Returns:
        Результат выполнения функции или значение по умолчанию
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logger.error(f"Ошибка в safe_execute: {e}")
        if error_message:
            logger.error(error_message)
        return default_value


def create_error_message(
    title: str,
    message: str,
    details: str = None,
    parent: QWidget = None
) -> QMessageBox:
    """
    Создает стандартизованное сообщение об ошибке.
    
    Args:
        title: Заголовок
        message: Основное сообщение
        details: Детали ошибки
        parent: Родительский виджет
        
    Returns:
        Настроенный QMessageBox
    """
    msg = QMessageBox(parent)
    msg.setIcon(QMessageBox.Critical)
    msg.setWindowTitle(title)
    msg.setText(message)
    
    if details:
        msg.setDetailedText(details)
    
    return msg


def show_success_message(
    title: str,
    message: str,
    parent: QWidget = None,
    auto_close: int = None
):
    """
    Показывает сообщение об успешном выполнении операции.
    
    Args:
        title: Заголовок
        message: Сообщение
        parent: Родительский виджет
        auto_close: Автоматическое закрытие через N секунд
    """
    msg = QMessageBox(parent)
    msg.setIcon(QMessageBox.Information)
    msg.setWindowTitle(title)
    msg.setText(message)
    
    if auto_close:
        # Автоматическое закрытие
        QTimer.singleShot(auto_close * 1000, msg.close)
    
    msg.exec_()


# Функции для быстрого использования
def show_error(message: str, parent: QWidget = None, title: str = "Ошибка"):
    """Быстрый показ ошибки."""
    QMessageBox.critical(parent, title, message)


def show_warning(message: str, parent: QWidget = None, title: str = "Предупреждение"):
    """Быстрый показ предупреждения."""
    QMessageBox.warning(parent, title, message)


def show_info(message: str, parent: QWidget = None, title: str = "Информация"):
    """Быстрый показ информации."""
    QMessageBox.information(parent, title, message)


def confirm_action(
    message: str,
    parent: QWidget = None,
    title: str = "Подтверждение"
) -> bool:
    """
    Запрашивает подтверждение действия.
    
    Returns:
        True если пользователь подтвердил
    """
    reply = QMessageBox.question(
        parent,
        title,
        message,
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.No
    )
    return reply == QMessageBox.Yes 
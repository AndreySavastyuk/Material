"""
Интеграционный модуль для объединения всех UX систем.

Объединяет:
- Tooltip Manager - система подсказок
- Hotkey Manager - горячие клавиши  
- Help System - контекстная справка
- Undo/Redo Manager - отмена/повтор действий
- AutoComplete Manager - автозаполнение

Обеспечивает единую точку настройки и управления всеми UX системами.
"""

import os
from typing import Dict, Any, Optional, Callable, List
from PyQt5.QtWidgets import QMainWindow, QWidget, QLineEdit, QMessageBox, QAction
from PyQt5.QtCore import Qt, QObject, pyqtSignal
from PyQt5.QtGui import QKeySequence

from utils.logger import get_logger
from .tooltip_manager import (
    get_tooltip_manager, register_tooltips_for_window, TooltipManager
)
from .hotkey_manager import (
    get_hotkey_manager, register_window_hotkeys, HotkeyManager
)
from .help_system import (
    get_help_system, show_context_help, HelpSystem, create_help_content_files
)
from .undo_redo_manager import (
    get_undo_redo_manager, create_data_command, UndoRedoManager
)
from .autocomplete_manager import (
    get_autocomplete_manager, create_autocomplete_line_edit, 
    setup_autocomplete_for_widget, AutoCompleteManager
)

logger = get_logger('gui.ux_integration')


class UXSystemsManager(QObject):
    """
    Главный менеджер всех UX систем.
    
    Координирует работу:
    - Tooltips
    - Горячих клавиш
    - Справочной системы
    - Undo/Redo
    - Автозаполнения
    """
    
    # Сигналы для координации между системами
    action_performed = pyqtSignal(str, dict)  # action_name, context
    help_requested = pyqtSignal(str)  # context
    
    def __init__(self, main_window: QMainWindow, user_role: str = "user"):
        super().__init__()
        self.main_window = main_window
        self.user_role = user_role
        
        # Менеджеры подсистем
        self.tooltip_manager: Optional[TooltipManager] = None
        self.hotkey_manager: Optional[HotkeyManager] = None
        self.help_system: Optional[HelpSystem] = None
        self.undo_redo_manager: Optional[UndoRedoManager] = None
        self.autocomplete_manager: Optional[AutoCompleteManager] = None
        
        # Настройки интеграции
        self.integration_config = {
            'enable_tooltips': True,
            'enable_hotkeys': True,
            'enable_help': True,
            'enable_undo_redo': True,
            'enable_autocomplete': True,
            'auto_save_undo': True,
            'tooltip_language': 'ru',
            'max_undo_commands': 100
        }
        
        # Инициализируем системы
        self._initialize_systems()
        
        logger.info(f"UXSystemsManager инициализирован для роли: {user_role}")
    
    def _initialize_systems(self):
        """Инициализирует все UX системы."""
        try:
            # Tooltips
            if self.integration_config['enable_tooltips']:
                self.tooltip_manager = get_tooltip_manager(
                    self.integration_config['tooltip_language']
                )
                logger.debug("Tooltip система инициализирована")
            
            # Горячие клавиши
            if self.integration_config['enable_hotkeys']:
                self.hotkey_manager = get_hotkey_manager(self.main_window)
                self._setup_default_hotkeys()
                logger.debug("Система горячих клавиш инициализирована")
            
            # Справочная система
            if self.integration_config['enable_help']:
                self.help_system = get_help_system(self.user_role, self.main_window)
                create_help_content_files()
                logger.debug("Справочная система инициализирована")
            
            # Undo/Redo
            if self.integration_config['enable_undo_redo']:
                self.undo_redo_manager = get_undo_redo_manager(
                    self.integration_config['max_undo_commands'],
                    self.integration_config['auto_save_undo']
                )
                self._setup_undo_redo_ui()
                logger.debug("Система Undo/Redo инициализирована")
            
            # Автозаполнение
            if self.integration_config['enable_autocomplete']:
                self.autocomplete_manager = get_autocomplete_manager()
                logger.debug("Система автозаполнения инициализирована")
            
            # Подключаем системы друг к другу
            self._connect_systems()
            
        except Exception as e:
            logger.error(f"Ошибка инициализации UX систем: {e}")
            QMessageBox.warning(
                self.main_window,
                "Предупреждение",
                f"Некоторые системы улучшения интерфейса могут работать неполноценно:\n{e}"
            )
    
    def _setup_default_hotkeys(self):
        """Настраивает горячие клавиши по умолчанию."""
        if not self.hotkey_manager:
            return
        
        # Системные горячие клавиши
        hotkey_callbacks = {
            'F1': self._show_context_help,
            'Ctrl+Z': self._undo_action,
            'Ctrl+Y': self._redo_action,
            'Ctrl+?': self._show_hotkeys_help,
            'Ctrl+H': self._toggle_ux_help,
            'F11': self._toggle_fullscreen
        }
        
        # Регистрируем callback'и
        register_window_hotkeys(self.main_window, hotkey_callbacks)
    
    def _setup_undo_redo_ui(self):
        """Настраивает UI для Undo/Redo."""
        if not self.undo_redo_manager or not hasattr(self.main_window, 'menuBar'):
            return
        
        try:
            # Ищем меню "Правка" или создаем его
            edit_menu = None
            for action in self.main_window.menuBar().actions():
                if action.text().lower() in ['правка', 'edit', '&правка', '&edit']:
                    edit_menu = action.menu()
                    break
            
            if not edit_menu:
                edit_menu = self.main_window.menuBar().addMenu("Правка")
            
            # Добавляем действия Undo/Redo
            self.undo_action = QAction("Отменить", self.main_window)
            self.undo_action.setShortcut(QKeySequence.Undo)
            self.undo_action.setEnabled(False)
            self.undo_action.triggered.connect(self._undo_action)
            
            self.redo_action = QAction("Повторить", self.main_window)
            self.redo_action.setShortcut(QKeySequence.Redo)
            self.redo_action.setEnabled(False)
            self.redo_action.triggered.connect(self._redo_action)
            
            # Добавляем в меню
            edit_menu.addAction(self.undo_action)
            edit_menu.addAction(self.redo_action)
            edit_menu.addSeparator()
            
            # Подключаем обновление состояния
            self.undo_redo_manager.state_changed.connect(self._update_undo_redo_actions)
            
        except Exception as e:
            logger.error(f"Ошибка настройки UI для Undo/Redo: {e}")
    
    def _connect_systems(self):
        """Подключает системы друг к другу."""
        # Подключаем сигналы между системами
        self.action_performed.connect(self._on_action_performed)
        self.help_requested.connect(self._on_help_requested)
        
        if self.undo_redo_manager:
            self.undo_redo_manager.command_executed.connect(
                lambda cmd: self.action_performed.emit("command_executed", {"command": cmd})
            )
    
    def register_window(self, window: QMainWindow, user_role: str = None):
        """
        Регистрирует окно для всех UX систем.
        
        Args:
            window: Окно для регистрации
            user_role: Роль пользователя (опционально)
        """
        role = user_role or self.user_role
        
        try:
            # Tooltips
            if self.tooltip_manager:
                register_tooltips_for_window(window, role)
                logger.debug(f"Tooltips зарегистрированы для окна")
            
            # Горячие клавиши
            if self.hotkey_manager:
                # Уже зарегистрированы в _setup_default_hotkeys
                pass
            
            # Контекстная справка
            if self.help_system:
                # Справка доступна через F1
                pass
                
        except Exception as e:
            logger.error(f"Ошибка регистрации окна в UX системах: {e}")
    
    def create_enhanced_line_edit(self, category: str, parent: QWidget = None) -> QLineEdit:
        """
        Создает улучшенное поле ввода со всеми UX функциями.
        
        Args:
            category: Категория для автозаполнения
            parent: Родительский виджет
            
        Returns:
            Поле ввода с подсказками и автозаполнением
        """
        # Создаем поле с автозаполнением
        if self.autocomplete_manager:
            line_edit = create_autocomplete_line_edit(category, parent)
        else:
            line_edit = QLineEdit(parent)
        
        # Добавляем tooltip
        if self.tooltip_manager:
            self.tooltip_manager.register_widget(
                line_edit,
                category,
                "fields",
                user_role=self.user_role
            )
        
        return line_edit
    
    def create_undo_command(self, description: str, operation_type: str, 
                           table_name: str, record_id: Any,
                           old_data: Dict = None, new_data: Dict = None,
                           execute_callback: Callable = None, 
                           undo_callback: Callable = None):
        """
        Создает команду для системы Undo/Redo.
        
        Args:
            description: Описание операции
            operation_type: Тип операции ('insert', 'update', 'delete')
            table_name: Название таблицы
            record_id: ID записи
            old_data: Старые данные
            new_data: Новые данные
            execute_callback: Callback для выполнения
            undo_callback: Callback для отмены
            
        Returns:
            Команда для выполнения
        """
        if not self.undo_redo_manager:
            return None
        
        return create_data_command(
            description=description,
            operation_type=operation_type,
            table_name=table_name,
            record_id=record_id,
            old_data=old_data,
            new_data=new_data,
            execute_callback=execute_callback,
            undo_callback=undo_callback
        )
    
    def execute_undoable_action(self, command):
        """
        Выполняет действие с возможностью отмены.
        
        Args:
            command: Команда для выполнения
            
        Returns:
            True если команда выполнена успешно
        """
        if not self.undo_redo_manager or not command:
            return False
        
        return self.undo_redo_manager.execute_command(command)
    
    def begin_command_group(self, description: str):
        """
        Начинает группу команд.
        
        Args:
            description: Описание группы
        """
        if self.undo_redo_manager:
            self.undo_redo_manager.begin_group(description)
    
    def end_command_group(self):
        """Заканчивает группу команд."""
        if self.undo_redo_manager:
            return self.undo_redo_manager.end_group()
        return False
    
    def add_autocomplete_suggestion(self, text: str, category: str, weight: float = 1.0):
        """
        Добавляет предложение в автозаполнение.
        
        Args:
            text: Текст предложения
            category: Категория
            weight: Вес предложения
        """
        if self.autocomplete_manager:
            self.autocomplete_manager.add_suggestion(text, category, weight)
    
    def show_help_dialog(self):
        """Показывает диалог справки."""
        if self.help_system:
            self.help_system.show()
    
    def show_context_help(self, context: str):
        """
        Показывает контекстную справку.
        
        Args:
            context: Контекст справки
        """
        if self.help_system:
            self.help_system.show_context_help(context)
        else:
            show_context_help(context, self.user_role, self.main_window)
    
    def configure_tooltips(self, language: str = "ru"):
        """
        Настраивает систему подсказок.
        
        Args:
            language: Язык подсказок
        """
        if self.tooltip_manager:
            self.tooltip_manager.set_language(language)
    
    def configure_hotkeys(self):
        """Показывает диалог настройки горячих клавиш."""
        if self.hotkey_manager:
            self.hotkey_manager.show_configuration_dialog(self.main_window)
    
    def get_ux_statistics(self) -> Dict[str, Any]:
        """Возвращает статистику использования UX систем."""
        stats = {
            'systems': {
                'tooltips': self.tooltip_manager is not None,
                'hotkeys': self.hotkey_manager is not None,
                'help': self.help_system is not None,
                'undo_redo': self.undo_redo_manager is not None,
                'autocomplete': self.autocomplete_manager is not None
            }
        }
        
        # Собираем детальную статистику
        if self.undo_redo_manager:
            stats['undo_redo'] = self.undo_redo_manager.get_memory_usage()
        
        if self.autocomplete_manager:
            stats['autocomplete'] = self.autocomplete_manager.get_statistics()
        
        if self.hotkey_manager:
            stats['hotkeys'] = {
                'total_actions': len(self.hotkey_manager.get_all_actions()),
                'categories': len(self.hotkey_manager.get_categories())
            }
        
        return stats
    
    # Callback'и для горячих клавиш
    def _show_context_help(self):
        """Показывает контекстную справку (F1)."""
        # Определяем текущий контекст
        focused_widget = self.main_window.focusWidget()
        context = "general"
        
        if focused_widget:
            widget_name = focused_widget.objectName()
            if "material" in widget_name.lower():
                context = "materials"
            elif "lab" in widget_name.lower():
                context = "lab"
            elif "otk" in widget_name.lower():
                context = "otk"
        
        self.show_context_help(context)
        logger.debug(f"Показана контекстная справка для: {context}")
    
    def _undo_action(self):
        """Отменяет последнее действие."""
        if self.undo_redo_manager and self.undo_redo_manager.can_undo():
            success = self.undo_redo_manager.undo()
            if success:
                logger.debug("Действие отменено")
            else:
                QMessageBox.warning(
                    self.main_window,
                    "Ошибка",
                    "Не удалось отменить действие"
                )
    
    def _redo_action(self):
        """Повторяет отмененное действие."""
        if self.undo_redo_manager and self.undo_redo_manager.can_redo():
            success = self.undo_redo_manager.redo()
            if success:
                logger.debug("Действие повторено")
            else:
                QMessageBox.warning(
                    self.main_window,
                    "Ошибка",
                    "Не удалось повторить действие"
                )
    
    def _show_hotkeys_help(self):
        """Показывает справку по горячим клавишам."""
        if self.help_system:
            self.help_system.show_hotkeys_help()
            self.help_system.show()
        elif self.hotkey_manager:
            self.hotkey_manager._show_simple_hotkeys_list()
    
    def _toggle_ux_help(self):
        """Переключает отображение справки по UX."""
        if self.help_system:
            if self.help_system.isVisible():
                self.help_system.hide()
            else:
                self.help_system.show()
    
    def _toggle_fullscreen(self):
        """Переключает полноэкранный режим."""
        if self.main_window.isFullScreen():
            self.main_window.showNormal()
        else:
            self.main_window.showFullScreen()
    
    def _update_undo_redo_actions(self):
        """Обновляет состояние действий Undo/Redo."""
        if not hasattr(self, 'undo_action') or not hasattr(self, 'redo_action'):
            return
        
        if self.undo_redo_manager:
            # Undo
            can_undo = self.undo_redo_manager.can_undo()
            self.undo_action.setEnabled(can_undo)
            self.undo_action.setText(self.undo_redo_manager.get_undo_text())
            
            # Redo
            can_redo = self.undo_redo_manager.can_redo()
            self.redo_action.setEnabled(can_redo)
            self.redo_action.setText(self.undo_redo_manager.get_redo_text())
    
    def _on_action_performed(self, action_name: str, context: Dict[str, Any]):
        """Обработчик выполнения действий."""
        logger.debug(f"Действие выполнено: {action_name} с контекстом: {context}")
    
    def _on_help_requested(self, context: str):
        """Обработчик запроса справки."""
        self.show_context_help(context)
        logger.debug(f"Запрошена справка для контекста: {context}")


# Глобальный экземпляр менеджера UX систем
_ux_manager = None


def get_ux_manager(main_window: QMainWindow = None, user_role: str = "user") -> UXSystemsManager:
    """Возвращает глобальный экземпляр менеджера UX систем."""
    global _ux_manager
    if _ux_manager is None and main_window:
        _ux_manager = UXSystemsManager(main_window, user_role)
    return _ux_manager


def setup_ux_for_window(window: QMainWindow, user_role: str = "user") -> UXSystemsManager:
    """
    Настраивает все UX системы для окна.
    
    Args:
        window: Главное окно приложения
        user_role: Роль пользователя
        
    Returns:
        Менеджер UX систем
    """
    ux_manager = UXSystemsManager(window, user_role)
    ux_manager.register_window(window, user_role)
    
    logger.info(f"UX системы настроены для окна с ролью: {user_role}")
    return ux_manager


def create_enhanced_line_edit(category: str, parent: QWidget = None) -> QLineEdit:
    """
    Удобная функция для создания улучшенного поля ввода.
    
    Args:
        category: Категория для автозаполнения
        parent: Родительский виджет
        
    Returns:
        Поле ввода с автозаполнением и подсказками
    """
    global _ux_manager
    if _ux_manager:
        return _ux_manager.create_enhanced_line_edit(category, parent)
    else:
        # Fallback
        return create_autocomplete_line_edit(category, parent)


def execute_undoable_action(description: str, operation_type: str, table_name: str,
                           record_id: Any, old_data: Dict = None, new_data: Dict = None,
                           execute_callback: Callable = None, undo_callback: Callable = None) -> bool:
    """
    Удобная функция для выполнения действия с возможностью отмены.
    
    Args:
        description: Описание операции
        operation_type: Тип операции
        table_name: Название таблицы
        record_id: ID записи
        old_data: Старые данные
        new_data: Новые данные
        execute_callback: Callback для выполнения
        undo_callback: Callback для отмены
        
    Returns:
        True если операция выполнена успешно
    """
    global _ux_manager
    if _ux_manager:
        command = _ux_manager.create_undo_command(
            description, operation_type, table_name, record_id,
            old_data, new_data, execute_callback, undo_callback
        )
        if command:
            return _ux_manager.execute_undoable_action(command)
    
    return False 
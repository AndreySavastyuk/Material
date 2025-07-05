"""
Система управления горячими клавишами для улучшения пользовательского опыта.

Особенности:
- Глобальные и локальные горячие клавиши
- Конфликт-менеджер для избежания дублирования
- Контекстные комбинации для разных режимов
- Настраиваемые пользователем комбинации
- Справка по горячим клавишам
"""

import os
import json
from typing import Dict, Any, Optional, List, Callable, Union
from PyQt5.QtWidgets import (
    QWidget, QApplication, QShortcut, QDialog, QVBoxLayout, 
    QHBoxLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QLineEdit, QGroupBox, QCheckBox, QMessageBox
)
from PyQt5.QtCore import Qt, QObject, pyqtSignal
from PyQt5.QtGui import QKeySequence, QFont
from utils.logger import get_logger

logger = get_logger('gui.hotkey_manager')


class HotkeyConflictException(Exception):
    """Исключение для конфликтов горячих клавиш."""
    pass


class HotkeyAction:
    """
    Класс для описания действия горячей клавиши.
    """
    
    def __init__(self, key_sequence: str, callback: Callable, 
                 description: str, category: str = "general",
                 context: str = "global", enabled: bool = True):
        self.key_sequence = key_sequence
        self.callback = callback
        self.description = description
        self.category = category
        self.context = context
        self.enabled = enabled
        self.shortcut: Optional[QShortcut] = None
    
    def __str__(self):
        return f"{self.key_sequence} - {self.description}"


class HotkeyConfigDialog(QDialog):
    """
    Диалог настройки горячих клавиш.
    """
    
    hotkeys_changed = pyqtSignal()
    
    def __init__(self, hotkey_manager, parent=None):
        super().__init__(parent)
        self.hotkey_manager = hotkey_manager
        self.setWindowTitle("Настройка горячих клавиш")
        self.setModal(True)
        self.resize(700, 500)
        
        self._setup_ui()
        self._load_hotkeys()
    
    def _setup_ui(self):
        """Настройка интерфейса диалога."""
        layout = QVBoxLayout()
        
        # Заголовок
        title = QLabel("Настройка горячих клавиш")
        title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        layout.addWidget(title)
        
        # Поиск
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Поиск:"))
        
        self.search_line = QLineEdit()
        self.search_line.setPlaceholderText("Введите название действия или комбинацию клавиш...")
        self.search_line.textChanged.connect(self._filter_hotkeys)
        search_layout.addWidget(self.search_line)
        
        layout.addLayout(search_layout)
        
        # Таблица горячих клавиш
        self.hotkeys_table = QTableWidget()
        self.hotkeys_table.setColumnCount(4)
        self.hotkeys_table.setHorizontalHeaderLabels([
            "Действие", "Категория", "Горячая клавиша", "Включено"
        ])
        
        # Настройка заголовков
        header = self.hotkeys_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        
        self.hotkeys_table.itemDoubleClicked.connect(self._edit_hotkey)
        layout.addWidget(self.hotkeys_table)
        
        # Кнопки управления
        buttons_layout = QHBoxLayout()
        
        self.reset_button = QPushButton("Сбросить к умолчанию")
        self.reset_button.clicked.connect(self._reset_to_defaults)
        buttons_layout.addWidget(self.reset_button)
        
        buttons_layout.addStretch()
        
        self.save_button = QPushButton("Сохранить")
        self.save_button.clicked.connect(self._save_changes)
        buttons_layout.addWidget(self.save_button)
        
        self.cancel_button = QPushButton("Отмена")
        self.cancel_button.clicked.connect(self.reject)
        buttons_layout.addWidget(self.cancel_button)
        
        layout.addLayout(buttons_layout)
        
        # Справка
        help_group = QGroupBox("Справка")
        help_layout = QVBoxLayout()
        
        help_text = QLabel("""
        <b>Как настроить горячие клавиши:</b><br>
        • Дважды щелкните по строке для редактирования<br>
        • Используйте стандартные модификаторы: Ctrl, Alt, Shift<br>
        • Примеры: Ctrl+N, Alt+F4, Shift+Delete<br>
        • Снимите галочку для отключения горячей клавиши
        """)
        help_text.setWordWrap(True)
        help_layout.addWidget(help_text)
        
        help_group.setLayout(help_layout)
        layout.addWidget(help_group)
        
        self.setLayout(layout)
    
    def _load_hotkeys(self):
        """Загружает горячие клавиши в таблицу."""
        actions = self.hotkey_manager.get_all_actions()
        self.hotkeys_table.setRowCount(len(actions))
        
        for row, action in enumerate(actions):
            # Действие
            desc_item = QTableWidgetItem(action.description)
            desc_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            self.hotkeys_table.setItem(row, 0, desc_item)
            
            # Категория
            cat_item = QTableWidgetItem(action.category)
            cat_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            self.hotkeys_table.setItem(row, 1, cat_item)
            
            # Горячая клавиша
            key_item = QTableWidgetItem(action.key_sequence)
            self.hotkeys_table.setItem(row, 2, key_item)
            
            # Включено
            enabled_checkbox = QCheckBox()
            enabled_checkbox.setChecked(action.enabled)
            self.hotkeys_table.setCellWidget(row, 3, enabled_checkbox)
            
            # Сохраняем ссылку на действие
            desc_item.setData(Qt.UserRole, action)
    
    def _filter_hotkeys(self, text: str):
        """Фильтрует горячие клавиши по тексту."""
        for row in range(self.hotkeys_table.rowCount()):
            description = self.hotkeys_table.item(row, 0).text().lower()
            hotkey = self.hotkeys_table.item(row, 2).text().lower()
            
            visible = (text.lower() in description or text.lower() in hotkey)
            self.hotkeys_table.setRowHidden(row, not visible)
    
    def _edit_hotkey(self, item):
        """Редактирует горячую клавишу."""
        if item.column() != 2:  # Только колонка с горячими клавишами
            return
        
        action = self.hotkeys_table.item(item.row(), 0).data(Qt.UserRole)
        
        # Диалог ввода новой комбинации
        from PyQt5.QtWidgets import QInputDialog
        
        new_sequence, ok = QInputDialog.getText(
            self,
            "Изменить горячую клавишу",
            f"Введите новую комбинацию для '{action.description}':",
            text=action.key_sequence
        )
        
        if ok and new_sequence:
            # Проверяем валидность комбинации
            if QKeySequence(new_sequence).isEmpty():
                QMessageBox.warning(
                    self,
                    "Ошибка",
                    "Недопустимая комбинация клавиш!"
                )
                return
            
            # Проверяем конфликты
            if self.hotkey_manager.has_conflict(new_sequence, action):
                result = QMessageBox.question(
                    self,
                    "Конфликт горячих клавиш",
                    f"Комбинация '{new_sequence}' уже используется.\nЗаменить?",
                    QMessageBox.Yes | QMessageBox.No
                )
                
                if result == QMessageBox.No:
                    return
            
            # Обновляем
            item.setText(new_sequence)
    
    def _reset_to_defaults(self):
        """Сбрасывает горячие клавиши к умолчанию."""
        result = QMessageBox.question(
            self,
            "Сброс к умолчанию",
            "Вернуть все горячие клавиши к значениям по умолчанию?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if result == QMessageBox.Yes:
            self.hotkey_manager.reset_to_defaults()
            self._load_hotkeys()
    
    def _save_changes(self):
        """Сохраняет изменения."""
        try:
            # Собираем изменения из таблицы
            for row in range(self.hotkeys_table.rowCount()):
                action = self.hotkeys_table.item(row, 0).data(Qt.UserRole)
                new_sequence = self.hotkeys_table.item(row, 2).text()
                enabled_checkbox = self.hotkeys_table.cellWidget(row, 3)
                
                # Обновляем действие
                self.hotkey_manager.update_action(
                    action.key_sequence,
                    new_sequence,
                    enabled_checkbox.isChecked()
                )
            
            self.hotkeys_changed.emit()
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Ошибка сохранения",
                f"Не удалось сохранить настройки:\n{str(e)}"
            )


class HotkeyManager(QObject):
    """
    Менеджер системы горячих клавиш.
    
    Особенности:
    - Управление глобальными и локальными горячими клавишами
    - Предотвращение конфликтов
    - Контекстные комбинации
    - Настройка пользователем
    - Сохранение в конфигурацию
    """
    
    hotkey_triggered = pyqtSignal(str)  # Сигнал срабатывания горячей клавиши
    
    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.parent_widget = parent
        self.actions: Dict[str, HotkeyAction] = {}
        self.shortcuts: Dict[str, QShortcut] = {}
        self.config_file = "resources/hotkeys_config.json"
        self.current_context = "global"
        
        # Загружаем конфигурацию
        self._load_configuration()
        
        # Создаем действия по умолчанию
        self._create_default_actions()
        
        logger.info("HotkeyManager инициализирован")
    
    def _load_configuration(self):
        """Загружает конфигурацию горячих клавиш."""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                logger.debug(f"Загружена конфигурация горячих клавиш: {len(config)} действий")
                
                # Восстанавливаем действия из конфигурации
                # (callback'и будут добавлены позже через register_action)
                
            except Exception as e:
                logger.error(f"Ошибка загрузки конфигурации горячих клавиш: {e}")
    
    def _create_default_actions(self):
        """Создает действия по умолчанию."""
        default_actions = [
            # Файл
            ("Ctrl+N", "Создать новый", "file", self._placeholder_callback),
            ("Ctrl+O", "Открыть", "file", self._placeholder_callback),
            ("Ctrl+S", "Сохранить", "file", self._placeholder_callback),
            ("Ctrl+Shift+S", "Сохранить как", "file", self._placeholder_callback),
            ("Ctrl+Q", "Выход", "file", self._placeholder_callback),
            
            # Редактирование
            ("Ctrl+Z", "Отменить", "edit", self._placeholder_callback),
            ("Ctrl+Y", "Повторить", "edit", self._placeholder_callback),
            ("Ctrl+C", "Копировать", "edit", self._placeholder_callback),
            ("Ctrl+V", "Вставить", "edit", self._placeholder_callback),
            ("Ctrl+X", "Вырезать", "edit", self._placeholder_callback),
            ("Delete", "Удалить", "edit", self._placeholder_callback),
            ("Ctrl+A", "Выделить все", "edit", self._placeholder_callback),
            
            # Навигация
            ("F5", "Обновить", "navigation", self._placeholder_callback),
            ("Ctrl+F", "Поиск", "navigation", self._placeholder_callback),
            ("Ctrl+G", "Перейти к", "navigation", self._placeholder_callback),
            ("Escape", "Отмена/Закрыть", "navigation", self._placeholder_callback),
            
            # Вид
            ("Ctrl+T", "Переключить тему", "view", self._placeholder_callback),
            ("F11", "Полноэкранный режим", "view", self._placeholder_callback),
            ("Ctrl+Plus", "Увеличить масштаб", "view", self._placeholder_callback),
            ("Ctrl+Minus", "Уменьшить масштаб", "view", self._placeholder_callback),
            ("Ctrl+0", "Сбросить масштаб", "view", self._placeholder_callback),
            
            # Справка
            ("F1", "Справка", "help", self._placeholder_callback),
            ("Ctrl+?", "Горячие клавиши", "help", self._show_hotkeys_help),
            
            # Специфичные для приложения
            ("Ctrl+M", "Материалы", "app", self._placeholder_callback),
            ("Ctrl+L", "Лаборатория", "app", self._placeholder_callback),
            ("Ctrl+R", "Отчеты", "app", self._placeholder_callback),
            ("Ctrl+U", "Пользователи", "app", self._placeholder_callback),
        ]
        
        for key_seq, desc, category, callback in default_actions:
            action = HotkeyAction(key_seq, callback, desc, category)
            self.actions[key_seq] = action
    
    def _placeholder_callback(self):
        """Заглушка для callback'ов."""
        pass
    
    def register_action(self, key_sequence: str, callback: Callable,
                       description: str, category: str = "general",
                       context: str = "global", force: bool = False) -> bool:
        """
        Регистрирует новое действие горячей клавиши.
        
        Args:
            key_sequence: Комбинация клавиш (например, "Ctrl+N")
            callback: Функция для вызова
            description: Описание действия
            category: Категория действия
            context: Контекст использования
            force: Принудительная перезапись существующего действия
            
        Returns:
            True если действие зарегистрировано успешно
        """
        if key_sequence in self.actions and not force:
            logger.warning(f"Горячая клавиша {key_sequence} уже зарегистрирована")
            return False
        
        # Создаем действие
        action = HotkeyAction(key_sequence, callback, description, category, context)
        
        # Проверяем валидность комбинации
        if QKeySequence(key_sequence).isEmpty():
            logger.error(f"Недопустимая комбинация клавиш: {key_sequence}")
            return False
        
        # Регистрируем действие
        self.actions[key_sequence] = action
        
        # Создаем QShortcut
        self._create_shortcut(action)
        
        logger.debug(f"Зарегистрирована горячая клавиша: {key_sequence} - {description}")
        return True
    
    def _create_shortcut(self, action: HotkeyAction):
        """Создает QShortcut для действия."""
        if not self.parent_widget or not action.enabled:
            return
        
        try:
            shortcut = QShortcut(QKeySequence(action.key_sequence), self.parent_widget)
            shortcut.activated.connect(lambda: self._handle_shortcut(action))
            
            action.shortcut = shortcut
            self.shortcuts[action.key_sequence] = shortcut
            
        except Exception as e:
            logger.error(f"Ошибка создания shortcut для {action.key_sequence}: {e}")
    
    def _handle_shortcut(self, action: HotkeyAction):
        """Обрабатывает срабатывание горячей клавиши."""
        try:
            # Проверяем контекст
            if action.context != "global" and action.context != self.current_context:
                return
            
            logger.debug(f"Срабатывание горячей клавиши: {action.key_sequence}")
            
            # Вызываем callback
            if action.callback:
                action.callback()
            
            # Отправляем сигнал
            self.hotkey_triggered.emit(action.key_sequence)
            
        except Exception as e:
            logger.error(f"Ошибка обработки горячей клавиши {action.key_sequence}: {e}")
    
    def unregister_action(self, key_sequence: str) -> bool:
        """
        Отменяет регистрацию действия.
        
        Args:
            key_sequence: Комбинация клавиш
            
        Returns:
            True если действие успешно удалено
        """
        if key_sequence not in self.actions:
            return False
        
        # Удаляем shortcut
        if key_sequence in self.shortcuts:
            shortcut = self.shortcuts[key_sequence]
            shortcut.setEnabled(False)
            del self.shortcuts[key_sequence]
        
        # Удаляем действие
        del self.actions[key_sequence]
        
        logger.debug(f"Отменена регистрация горячей клавиши: {key_sequence}")
        return True
    
    def update_action(self, old_sequence: str, new_sequence: str, enabled: bool = True):
        """
        Обновляет действие горячей клавиши.
        
        Args:
            old_sequence: Старая комбинация
            new_sequence: Новая комбинация
            enabled: Включено ли действие
        """
        if old_sequence not in self.actions:
            return
        
        action = self.actions[old_sequence]
        
        # Удаляем старый shortcut
        if old_sequence in self.shortcuts:
            self.shortcuts[old_sequence].setEnabled(False)
            del self.shortcuts[old_sequence]
        
        # Обновляем действие
        action.key_sequence = new_sequence
        action.enabled = enabled
        
        # Перемещаем в словаре
        del self.actions[old_sequence]
        self.actions[new_sequence] = action
        
        # Создаем новый shortcut
        if enabled:
            self._create_shortcut(action)
        
        logger.debug(f"Обновлена горячая клавиша: {old_sequence} -> {new_sequence}")
    
    def set_context(self, context: str):
        """
        Устанавливает текущий контекст.
        
        Args:
            context: Название контекста
        """
        self.current_context = context
        logger.debug(f"Установлен контекст горячих клавиш: {context}")
    
    def enable_action(self, key_sequence: str, enabled: bool = True):
        """
        Включает/выключает действие.
        
        Args:
            key_sequence: Комбинация клавиш
            enabled: Включить или выключить
        """
        if key_sequence in self.actions:
            action = self.actions[key_sequence]
            action.enabled = enabled
            
            if key_sequence in self.shortcuts:
                self.shortcuts[key_sequence].setEnabled(enabled)
    
    def has_conflict(self, key_sequence: str, exclude_action: HotkeyAction = None) -> bool:
        """
        Проверяет конфликт горячих клавиш.
        
        Args:
            key_sequence: Комбинация для проверки
            exclude_action: Действие для исключения из проверки
            
        Returns:
            True если есть конфликт
        """
        for action in self.actions.values():
            if action.key_sequence == key_sequence:
                if exclude_action is None or action != exclude_action:
                    return True
        return False
    
    def get_actions_by_category(self, category: str) -> List[HotkeyAction]:
        """Возвращает действия по категории."""
        return [action for action in self.actions.values() if action.category == category]
    
    def get_all_actions(self) -> List[HotkeyAction]:
        """Возвращает все действия."""
        return list(self.actions.values())
    
    def get_categories(self) -> List[str]:
        """Возвращает список всех категорий."""
        categories = set(action.category for action in self.actions.values())
        return sorted(list(categories))
    
    def save_configuration(self):
        """Сохраняет конфигурацию горячих клавиш."""
        try:
            config = {}
            
            for key_sequence, action in self.actions.items():
                config[key_sequence] = {
                    'description': action.description,
                    'category': action.category,
                    'context': action.context,
                    'enabled': action.enabled
                }
            
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Конфигурация горячих клавиш сохранена: {self.config_file}")
            
        except Exception as e:
            logger.error(f"Ошибка сохранения конфигурации горячих клавиш: {e}")
    
    def reset_to_defaults(self):
        """Сбрасывает горячие клавиши к значениям по умолчанию."""
        # Очищаем текущие
        for shortcut in self.shortcuts.values():
            shortcut.setEnabled(False)
        
        self.actions.clear()
        self.shortcuts.clear()
        
        # Создаем заново
        self._create_default_actions()
        
        # Пересоздаем shortcuts
        for action in self.actions.values():
            if action.enabled:
                self._create_shortcut(action)
        
        logger.info("Горячие клавиши сброшены к значениям по умолчанию")
    
    def show_configuration_dialog(self, parent=None):
        """Показывает диалог настройки горячих клавиш."""
        dialog = HotkeyConfigDialog(self, parent or self.parent_widget)
        dialog.hotkeys_changed.connect(self.save_configuration)
        dialog.exec_()
    
    def _show_hotkeys_help(self):
        """Показывает справку по горячим клавишам."""
        try:
            from .help_system import get_help_system
            help_system = get_help_system()
            help_system.show_hotkeys_help()
        except ImportError:
            # Fallback - простое окно со списком
            self._show_simple_hotkeys_list()
    
    def _show_simple_hotkeys_list(self):
        """Показывает простой список горячих клавиш."""
        from PyQt5.QtWidgets import QDialog, QTextEdit, QVBoxLayout, QPushButton
        
        dialog = QDialog(self.parent_widget)
        dialog.setWindowTitle("Горячие клавиши")
        dialog.resize(500, 400)
        
        layout = QVBoxLayout()
        
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        
        # Формируем текст со всеми горячими клавишами
        text = "<h2>Горячие клавиши</h2>"
        
        categories = self.get_categories()
        for category in categories:
            text += f"<h3>{category.title()}</h3><ul>"
            
            actions = self.get_actions_by_category(category)
            for action in sorted(actions, key=lambda a: a.description):
                if action.enabled:
                    text += f"<li><b>{action.key_sequence}</b> - {action.description}</li>"
            
            text += "</ul>"
        
        text_edit.setHtml(text)
        layout.addWidget(text_edit)
        
        close_button = QPushButton("Закрыть")
        close_button.clicked.connect(dialog.close)
        layout.addWidget(close_button)
        
        dialog.setLayout(layout)
        dialog.exec_()


# Глобальный экземпляр менеджера горячих клавиш
_hotkey_manager = None


def get_hotkey_manager(parent: QWidget = None) -> HotkeyManager:
    """Возвращает глобальный экземпляр менеджера горячих клавиш."""
    global _hotkey_manager
    if _hotkey_manager is None:
        _hotkey_manager = HotkeyManager(parent)
    return _hotkey_manager


def register_window_hotkeys(window, callbacks: Dict[str, Callable] = None):
    """
    Удобная функция для регистрации горячих клавиш для окна.
    
    Args:
        window: Главное окно приложения
        callbacks: Словарь callback'ов для действий
    """
    hotkey_manager = get_hotkey_manager(window)
    
    if callbacks:
        for key_sequence, callback in callbacks.items():
            if key_sequence in hotkey_manager.actions:
                action = hotkey_manager.actions[key_sequence]
                action.callback = callback
                # Пересоздаем shortcut с новым callback
                if action.shortcut:
                    action.shortcut.activated.disconnect()
                    action.shortcut.activated.connect(lambda seq=key_sequence: callback())
    
    logger.info(f"Горячие клавиши зарегистрированы для окна: {len(hotkey_manager.actions)} действий") 
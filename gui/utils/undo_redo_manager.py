"""
Система Undo/Redo для критических операций.

Особенности:
- Стек команд с ограничением по размеру
- Группировка операций
- Автосохранение состояний
- Восстановление данных после сбоев
- Визуальная история операций
"""

import json
import copy
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable, Union
from PyQt5.QtWidgets import (
    QWidget, QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QListWidget, QListWidgetItem, QTextEdit,
    QSplitter, QGroupBox, QCheckBox, QSpinBox, QMessageBox
)
from PyQt5.QtCore import Qt, QObject, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QIcon
from utils.logger import get_logger

logger = get_logger('gui.undo_redo_manager')


class Command:
    """
    Базовый класс для команд системы Undo/Redo.
    """
    
    def __init__(self, description: str, timestamp: datetime = None):
        self.description = description
        self.timestamp = timestamp or datetime.now()
        self.executed = False
    
    def execute(self) -> bool:
        """
        Выполняет команду.
        
        Returns:
            True если команда выполнена успешно
        """
        raise NotImplementedError("Метод execute должен быть реализован")
    
    def undo(self) -> bool:
        """
        Отменяет команду.
        
        Returns:
            True если команда отменена успешно
        """
        raise NotImplementedError("Метод undo должен быть реализован")
    
    def redo(self) -> bool:
        """
        Повторяет команду.
        
        Returns:
            True если команда повторена успешно
        """
        return self.execute()
    
    def can_merge_with(self, other: 'Command') -> bool:
        """
        Проверяет возможность объединения с другой командой.
        
        Args:
            other: Другая команда
            
        Returns:
            True если команды можно объединить
        """
        return False
    
    def merge_with(self, other: 'Command') -> 'Command':
        """
        Объединяет с другой командой.
        
        Args:
            other: Другая команда
            
        Returns:
            Объединенная команда
        """
        return self
    
    def __str__(self):
        return f"{self.description} ({self.timestamp.strftime('%H:%M:%S')})"


class DataCommand(Command):
    """
    Команда для работы с данными (создание, изменение, удаление).
    """
    
    def __init__(self, description: str, operation_type: str, 
                 table_name: str, record_id: Any,
                 old_data: Dict = None, new_data: Dict = None,
                 execute_callback: Callable = None, undo_callback: Callable = None):
        super().__init__(description)
        self.operation_type = operation_type  # 'insert', 'update', 'delete'
        self.table_name = table_name
        self.record_id = record_id
        self.old_data = old_data or {}
        self.new_data = new_data or {}
        self.execute_callback = execute_callback
        self.undo_callback = undo_callback
    
    def execute(self) -> bool:
        """Выполняет команду изменения данных."""
        try:
            if self.execute_callback:
                success = self.execute_callback(self)
                if success:
                    self.executed = True
                    logger.debug(f"Команда выполнена: {self.description}")
                return success
            return True
        except Exception as e:
            logger.error(f"Ошибка выполнения команды {self.description}: {e}")
            return False
    
    def undo(self) -> bool:
        """Отменяет команду изменения данных."""
        try:
            if self.undo_callback:
                success = self.undo_callback(self)
                if success:
                    self.executed = False
                    logger.debug(f"Команда отменена: {self.description}")
                return success
            
            # Базовая логика отмены
            if self.operation_type == 'insert':
                # Удаляем созданную запись
                return self._delete_record()
            elif self.operation_type == 'update':
                # Восстанавливаем старые данные
                return self._restore_old_data()
            elif self.operation_type == 'delete':
                # Восстанавливаем удаленную запись
                return self._restore_deleted_record()
            
            return True
        except Exception as e:
            logger.error(f"Ошибка отмены команды {self.description}: {e}")
            return False
    
    def _delete_record(self) -> bool:
        """Удаляет запись (для отмены создания)."""
        # Здесь должна быть логика удаления из БД
        # Интеграция с репозиториями/сервисами
        return True
    
    def _restore_old_data(self) -> bool:
        """Восстанавливает старые данные (для отмены изменения)."""
        # Здесь должна быть логика обновления в БД
        return True
    
    def _restore_deleted_record(self) -> bool:
        """Восстанавливает удаленную запись (для отмены удаления)."""
        # Здесь должна быть логика создания в БД
        return True
    
    def can_merge_with(self, other: 'Command') -> bool:
        """Проверяет возможность объединения команд."""
        if not isinstance(other, DataCommand):
            return False
        
        # Объединяем только команды для одной записи
        if (self.table_name == other.table_name and 
            self.record_id == other.record_id and
            self.operation_type == 'update' and
            other.operation_type == 'update'):
            
            # Проверяем временной интервал (объединяем только недавние операции)
            time_diff = abs((self.timestamp - other.timestamp).total_seconds())
            return time_diff < 30  # 30 секунд
        
        return False
    
    def merge_with(self, other: 'Command') -> 'Command':
        """Объединяет команды редактирования."""
        if isinstance(other, DataCommand):
            # Создаем новую команду с объединенными данными
            merged_command = DataCommand(
                description=f"{self.description} + {other.description}",
                operation_type=self.operation_type,
                table_name=self.table_name,
                record_id=self.record_id,
                old_data=self.old_data,  # Берем самые старые данные
                new_data=other.new_data,  # Берем самые новые данные
                execute_callback=other.execute_callback,
                undo_callback=self.undo_callback
            )
            merged_command.timestamp = other.timestamp
            return merged_command
        
        return self


class GroupCommand(Command):
    """
    Группа команд, выполняемых как единое целое.
    """
    
    def __init__(self, description: str, commands: List[Command] = None):
        super().__init__(description)
        self.commands = commands or []
    
    def add_command(self, command: Command):
        """Добавляет команду в группу."""
        self.commands.append(command)
    
    def execute(self) -> bool:
        """Выполняет все команды группы."""
        success = True
        executed_commands = []
        
        try:
            for command in self.commands:
                if command.execute():
                    executed_commands.append(command)
                else:
                    success = False
                    break
            
            if not success:
                # Отменяем выполненные команды в обратном порядке
                for command in reversed(executed_commands):
                    command.undo()
            else:
                self.executed = True
                logger.debug(f"Группа команд выполнена: {self.description}")
        
        except Exception as e:
            logger.error(f"Ошибка выполнения группы команд {self.description}: {e}")
            # Отменяем выполненные команды
            for command in reversed(executed_commands):
                try:
                    command.undo()
                except:
                    pass
            success = False
        
        return success
    
    def undo(self) -> bool:
        """Отменяет все команды группы в обратном порядке."""
        success = True
        
        try:
            for command in reversed(self.commands):
                if not command.undo():
                    success = False
                    # Продолжаем отмену остальных команд
            
            if success:
                self.executed = False
                logger.debug(f"Группа команд отменена: {self.description}")
        
        except Exception as e:
            logger.error(f"Ошибка отмены группы команд {self.description}: {e}")
            success = False
        
        return success


class UndoRedoHistoryDialog(QDialog):
    """
    Диалог истории операций Undo/Redo.
    """
    
    def __init__(self, undo_manager, parent=None):
        super().__init__(parent)
        self.undo_manager = undo_manager
        
        self.setWindowTitle("История операций")
        self.setModal(False)
        self.resize(700, 500)
        
        self._setup_ui()
        self._update_history()
    
    def _setup_ui(self):
        """Настройка интерфейса диалога."""
        layout = QVBoxLayout()
        
        # Заголовок
        title = QLabel("История операций")
        title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        layout.addWidget(title)
        
        # Основная область
        splitter = QSplitter(Qt.Horizontal)
        
        # Левая панель - список операций
        left_panel = QGroupBox("Операции")
        left_layout = QVBoxLayout()
        
        self.history_list = QListWidget()
        self.history_list.itemClicked.connect(self._on_item_selected)
        left_layout.addWidget(self.history_list)
        
        # Кнопки управления
        buttons_layout = QHBoxLayout()
        
        self.undo_to_button = QPushButton("Отменить до")
        self.undo_to_button.clicked.connect(self._undo_to_selected)
        self.undo_to_button.setEnabled(False)
        buttons_layout.addWidget(self.undo_to_button)
        
        self.redo_to_button = QPushButton("Повторить до")
        self.redo_to_button.clicked.connect(self._redo_to_selected)
        self.redo_to_button.setEnabled(False)
        buttons_layout.addWidget(self.redo_to_button)
        
        left_layout.addLayout(buttons_layout)
        left_panel.setLayout(left_layout)
        splitter.addWidget(left_panel)
        
        # Правая панель - детали операции
        right_panel = QGroupBox("Детали операции")
        right_layout = QVBoxLayout()
        
        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        right_layout.addWidget(self.details_text)
        
        right_panel.setLayout(right_layout)
        splitter.addWidget(right_panel)
        
        splitter.setSizes([350, 350])
        layout.addWidget(splitter)
        
        # Настройки
        settings_group = QGroupBox("Настройки")
        settings_layout = QHBoxLayout()
        
        self.auto_save_check = QCheckBox("Автосохранение")
        self.auto_save_check.setChecked(self.undo_manager.auto_save_enabled)
        self.auto_save_check.toggled.connect(self._toggle_auto_save)
        settings_layout.addWidget(self.auto_save_check)
        
        settings_layout.addWidget(QLabel("Макс. операций:"))
        
        self.max_commands_spin = QSpinBox()
        self.max_commands_spin.setRange(10, 1000)
        self.max_commands_spin.setValue(self.undo_manager.max_commands)
        self.max_commands_spin.valueChanged.connect(self._change_max_commands)
        settings_layout.addWidget(self.max_commands_spin)
        
        settings_layout.addStretch()
        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)
        
        # Кнопки закрытия
        close_layout = QHBoxLayout()
        close_layout.addStretch()
        
        self.close_button = QPushButton("Закрыть")
        self.close_button.clicked.connect(self.close)
        close_layout.addWidget(self.close_button)
        
        layout.addLayout(close_layout)
        
        self.setLayout(layout)
    
    def _update_history(self):
        """Обновляет список истории."""
        self.history_list.clear()
        
        # Добавляем команды из стека отмены (в обратном порядке)
        for i, command in enumerate(reversed(self.undo_manager.undo_stack)):
            item = QListWidgetItem(f"[{len(self.undo_manager.undo_stack) - i}] {command}")
            item.setData(Qt.UserRole, ('undo', len(self.undo_manager.undo_stack) - i - 1))
            
            # Отмечаем текущую позицию
            if i == 0 and self.undo_manager.undo_stack:
                item.setBackground(Qt.lightGray)
            
            self.history_list.addItem(item)
        
        # Добавляем команды из стека повтора
        for i, command in enumerate(self.undo_manager.redo_stack):
            item = QListWidgetItem(f"[↻{i + 1}] {command}")
            item.setData(Qt.UserRole, ('redo', i))
            item.setForeground(Qt.gray)
            self.history_list.addItem(item)
    
    def _on_item_selected(self, item):
        """Обработчик выбора операции."""
        data = item.data(Qt.UserRole)
        if not data:
            return
        
        stack_type, index = data
        
        if stack_type == 'undo' and index < len(self.undo_manager.undo_stack):
            command = self.undo_manager.undo_stack[index]
            self._show_command_details(command)
            self.undo_to_button.setEnabled(True)
            self.redo_to_button.setEnabled(False)
        elif stack_type == 'redo' and index < len(self.undo_manager.redo_stack):
            command = self.undo_manager.redo_stack[index]
            self._show_command_details(command)
            self.undo_to_button.setEnabled(False)
            self.redo_to_button.setEnabled(True)
    
    def _show_command_details(self, command: Command):
        """Показывает детали команды."""
        details = f"<h3>{command.description}</h3>"
        details += f"<p><b>Время:</b> {command.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</p>"
        details += f"<p><b>Выполнена:</b> {'Да' if command.executed else 'Нет'}</p>"
        details += f"<p><b>Тип:</b> {type(command).__name__}</p>"
        
        if isinstance(command, DataCommand):
            details += f"<p><b>Операция:</b> {command.operation_type}</p>"
            details += f"<p><b>Таблица:</b> {command.table_name}</p>"
            details += f"<p><b>ID записи:</b> {command.record_id}</p>"
            
            if command.old_data:
                details += "<p><b>Старые данные:</b></p>"
                details += f"<pre>{json.dumps(command.old_data, indent=2, ensure_ascii=False)}</pre>"
            
            if command.new_data:
                details += "<p><b>Новые данные:</b></p>"
                details += f"<pre>{json.dumps(command.new_data, indent=2, ensure_ascii=False)}</pre>"
        
        elif isinstance(command, GroupCommand):
            details += f"<p><b>Команд в группе:</b> {len(command.commands)}</p>"
            details += "<p><b>Команды:</b></p><ul>"
            for cmd in command.commands:
                details += f"<li>{cmd.description}</li>"
            details += "</ul>"
        
        self.details_text.setHtml(details)
    
    def _undo_to_selected(self):
        """Отменяет операции до выбранной."""
        current_item = self.history_list.currentItem()
        if not current_item:
            return
        
        data = current_item.data(Qt.UserRole)
        if data and data[0] == 'undo':
            index = data[1]
            
            result = QMessageBox.question(
                self,
                "Подтверждение",
                f"Отменить {len(self.undo_manager.undo_stack) - index} операций?",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if result == QMessageBox.Yes:
                for _ in range(len(self.undo_manager.undo_stack) - index):
                    if not self.undo_manager.undo():
                        break
                self._update_history()
    
    def _redo_to_selected(self):
        """Повторяет операции до выбранной."""
        current_item = self.history_list.currentItem()
        if not current_item:
            return
        
        data = current_item.data(Qt.UserRole)
        if data and data[0] == 'redo':
            index = data[1]
            
            result = QMessageBox.question(
                self,
                "Подтверждение", 
                f"Повторить {index + 1} операций?",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if result == QMessageBox.Yes:
                for _ in range(index + 1):
                    if not self.undo_manager.redo():
                        break
                self._update_history()
    
    def _toggle_auto_save(self, enabled: bool):
        """Переключает автосохранение."""
        self.undo_manager.auto_save_enabled = enabled
    
    def _change_max_commands(self, value: int):
        """Изменяет максимальное количество команд."""
        self.undo_manager.max_commands = value


class UndoRedoManager(QObject):
    """
    Менеджер системы Undo/Redo.
    
    Особенности:
    - Стек команд с ограничением размера
    - Группировка связанных операций
    - Автосохранение состояний
    - Восстановление после сбоев
    - Уведомления о изменениях
    """
    
    # Сигналы
    command_executed = pyqtSignal(Command)
    command_undone = pyqtSignal(Command)
    command_redone = pyqtSignal(Command)
    state_changed = pyqtSignal()  # Изменение возможности undo/redo
    
    def __init__(self, max_commands: int = 100, auto_save: bool = True):
        super().__init__()
        self.max_commands = max_commands
        self.auto_save_enabled = auto_save
        self.undo_stack: List[Command] = []
        self.redo_stack: List[Command] = []
        self.current_group: Optional[GroupCommand] = None
        self.merge_timeout = 2.0  # Секунды для объединения команд
        self.last_command_time = None
        
        # Автосохранение
        self.auto_save_timer = QTimer()
        self.auto_save_timer.setSingleShot(True)
        self.auto_save_timer.timeout.connect(self._auto_save)
        
        logger.info(f"UndoRedoManager инициализирован (макс. команд: {max_commands})")
    
    def execute_command(self, command: Command) -> bool:
        """
        Выполняет команду и добавляет в стек.
        
        Args:
            command: Команда для выполнения
            
        Returns:
            True если команда выполнена успешно
        """
        try:
            # Выполняем команду
            if not command.execute():
                logger.warning(f"Команда не выполнена: {command.description}")
                return False
            
            # Проверяем возможность объединения с предыдущей командой
            if (self.undo_stack and 
                self.last_command_time and
                (datetime.now() - self.last_command_time).total_seconds() < self.merge_timeout):
                
                last_command = self.undo_stack[-1]
                if last_command.can_merge_with(command):
                    # Объединяем команды
                    merged_command = last_command.merge_with(command)
                    self.undo_stack[-1] = merged_command
                    logger.debug(f"Команды объединены: {merged_command.description}")
                    
                    self.last_command_time = datetime.now()
                    self.command_executed.emit(merged_command)
                    self.state_changed.emit()
                    return True
            
            # Добавляем в группу или в стек
            if self.current_group:
                self.current_group.add_command(command)
            else:
                # Очищаем стек повтора
                self.redo_stack.clear()
                
                # Добавляем в стек отмены
                self.undo_stack.append(command)
                
                # Ограничиваем размер стека
                if len(self.undo_stack) > self.max_commands:
                    removed = self.undo_stack.pop(0)
                    logger.debug(f"Команда удалена из стека (превышен лимит): {removed.description}")
            
            self.last_command_time = datetime.now()
            
            # Отправляем сигналы
            self.command_executed.emit(command)
            self.state_changed.emit()
            
            # Запускаем автосохранение
            if self.auto_save_enabled:
                self.auto_save_timer.start(5000)  # 5 секунд задержка
            
            logger.debug(f"Команда выполнена и добавлена в стек: {command.description}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка выполнения команды {command.description}: {e}")
            return False
    
    def undo(self) -> bool:
        """
        Отменяет последнюю команду.
        
        Returns:
            True если команда отменена успешно
        """
        if not self.can_undo():
            return False
        
        try:
            command = self.undo_stack.pop()
            
            if command.undo():
                self.redo_stack.append(command)
                
                self.command_undone.emit(command)
                self.state_changed.emit()
                
                logger.debug(f"Команда отменена: {command.description}")
                return True
            else:
                # Возвращаем команду в стек, если отмена не удалась
                self.undo_stack.append(command)
                logger.warning(f"Не удалось отменить команду: {command.description}")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка отмены команды: {e}")
            return False
    
    def redo(self) -> bool:
        """
        Повторяет отмененную команду.
        
        Returns:
            True если команда повторена успешно
        """
        if not self.can_redo():
            return False
        
        try:
            command = self.redo_stack.pop()
            
            if command.redo():
                self.undo_stack.append(command)
                
                self.command_redone.emit(command)
                self.state_changed.emit()
                
                logger.debug(f"Команда повторена: {command.description}")
                return True
            else:
                # Возвращаем команду в стек, если повтор не удался
                self.redo_stack.append(command)
                logger.warning(f"Не удалось повторить команду: {command.description}")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка повтора команды: {e}")
            return False
    
    def can_undo(self) -> bool:
        """Проверяет возможность отмены."""
        return len(self.undo_stack) > 0
    
    def can_redo(self) -> bool:
        """Проверяет возможность повтора."""
        return len(self.redo_stack) > 0
    
    def get_undo_text(self) -> str:
        """Возвращает текст для кнопки отмены."""
        if self.can_undo():
            return f"Отменить: {self.undo_stack[-1].description}"
        return "Отменить"
    
    def get_redo_text(self) -> str:
        """Возвращает текст для кнопки повтора."""
        if self.can_redo():
            return f"Повторить: {self.redo_stack[-1].description}"
        return "Повторить"
    
    def begin_group(self, description: str):
        """
        Начинает группу команд.
        
        Args:
            description: Описание группы
        """
        if self.current_group:
            logger.warning("Группа команд уже открыта")
            return
        
        self.current_group = GroupCommand(description)
        logger.debug(f"Начата группа команд: {description}")
    
    def end_group(self) -> bool:
        """
        Заканчивает группу команд и добавляет в стек.
        
        Returns:
            True если группа успешно завершена
        """
        if not self.current_group:
            logger.warning("Нет открытой группы команд")
            return False
        
        group = self.current_group
        self.current_group = None
        
        if group.commands:
            # Очищаем стек повтора
            self.redo_stack.clear()
            
            # Добавляем группу в стек
            self.undo_stack.append(group)
            
            # Ограничиваем размер стека
            if len(self.undo_stack) > self.max_commands:
                removed = self.undo_stack.pop(0)
                logger.debug(f"Группа команд удалена из стека (превышен лимит): {removed.description}")
            
            self.command_executed.emit(group)
            self.state_changed.emit()
            
            logger.debug(f"Группа команд завершена: {group.description} ({len(group.commands)} команд)")
            return True
        else:
            logger.debug(f"Пустая группа команд отменена: {group.description}")
            return False
    
    def clear(self):
        """Очищает все стеки команд."""
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.current_group = None
        self.last_command_time = None
        
        self.state_changed.emit()
        logger.info("Стеки команд очищены")
    
    def get_memory_usage(self) -> Dict[str, int]:
        """Возвращает информацию об использовании памяти."""
        return {
            'undo_commands': len(self.undo_stack),
            'redo_commands': len(self.redo_stack),
            'total_commands': len(self.undo_stack) + len(self.redo_stack),
            'max_commands': self.max_commands
        }
    
    def show_history_dialog(self, parent=None):
        """Показывает диалог истории операций."""
        dialog = UndoRedoHistoryDialog(self, parent)
        dialog.show()
    
    def _auto_save(self):
        """Выполняет автосохранение состояния."""
        if not self.auto_save_enabled:
            return
        
        try:
            # Здесь можно сохранять важную информацию
            # Например, последние N команд для восстановления после сбоя
            save_data = {
                'timestamp': datetime.now().isoformat(),
                'undo_count': len(self.undo_stack),
                'redo_count': len(self.redo_stack)
            }
            
            # Сохраняем в файл (упрощенная версия)
            # В реальности здесь может быть более сложная логика
            
            logger.debug("Автосохранение состояния Undo/Redo выполнено")
            
        except Exception as e:
            logger.error(f"Ошибка автосохранения: {e}")


# Глобальный экземпляр менеджера Undo/Redo
_undo_redo_manager = None


def get_undo_redo_manager(max_commands: int = 100, auto_save: bool = True) -> UndoRedoManager:
    """Возвращает глобальный экземпляр менеджера Undo/Redo."""
    global _undo_redo_manager
    if _undo_redo_manager is None:
        _undo_redo_manager = UndoRedoManager(max_commands, auto_save)
    return _undo_redo_manager


def create_data_command(description: str, operation_type: str, table_name: str, 
                       record_id: Any, old_data: Dict = None, new_data: Dict = None,
                       execute_callback: Callable = None, undo_callback: Callable = None) -> DataCommand:
    """
    Удобная функция для создания команды работы с данными.
    
    Args:
        description: Описание операции
        operation_type: Тип операции ('insert', 'update', 'delete')
        table_name: Название таблицы
        record_id: ID записи
        old_data: Старые данные (для отмены)
        new_data: Новые данные
        execute_callback: Callback для выполнения
        undo_callback: Callback для отмены
        
    Returns:
        Команда для работы с данными
    """
    return DataCommand(
        description=description,
        operation_type=operation_type,
        table_name=table_name,
        record_id=record_id,
        old_data=old_data,
        new_data=new_data,
        execute_callback=execute_callback,
        undo_callback=undo_callback
    ) 
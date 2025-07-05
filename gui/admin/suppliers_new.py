# gui/admin/suppliers_new.py — обновленный справочник поставщиков с новой системой ошибок

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QFormLayout, QLineEdit, QDialogButtonBox
)
from PyQt5.QtCore import Qt
from typing import Optional, Dict, Any

from db.database import Database
from utils.error_handlers import (
    handle_gui_errors, handle_database_errors,
    show_error, show_warning, show_success_message, confirm_action
)
from utils.exceptions import (
    RecordInUseError, ValidationError, RequiredFieldError,
    DuplicateRecordError, RecordNotFoundError
)
from utils.logger import get_logger, log_audit


class SuppliersAdminNew(QDialog):
    """
    Обновленный справочник поставщиков с современной обработкой ошибок.
    
    Использует:
    - Декораторы для обработки ошибок
    - Кастомные исключения
    - Централизованное логирование
    - User-friendly сообщения
    """
    
    def __init__(self, parent=None, user: Optional[Dict[str, Any]] = None):
        super().__init__(parent)
        self.setWindowTitle('Справочник поставщиков')
        self.user = user or {'login': 'unknown', 'role': 'user'}
        self.logger = get_logger('gui')
        
        # Инициализация БД с обработкой ошибок
        self._init_database()
        self._build_ui()
        self._load_data()
        
        self.logger.info("Открыт справочник поставщиков")
    
    @handle_gui_errors(context="init_database")
    def _init_database(self):
        """Инициализация подключения к БД."""
        self.db = Database()
        self.db.connect()
    
    def _build_ui(self):
        """Построение пользовательского интерфейса."""
        layout = QVBoxLayout(self)

        # Таблица поставщиков
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(['Поставщик', 'Применяется'])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.table)

        # Кнопки действий
        btn_layout = QHBoxLayout()
        
        self.btn_add = QPushButton('Добавить')
        self.btn_edit = QPushButton('Изменить')
        self.btn_remove = QPushButton('Удалить')
        self.btn_close = QPushButton('Закрыть')
        
        # Подключение сигналов
        self.btn_add.clicked.connect(self._add_supplier)
        self.btn_edit.clicked.connect(self._edit_supplier)
        self.btn_remove.clicked.connect(self._remove_supplier)
        self.btn_close.clicked.connect(self.accept)
        
        # Добавление кнопок
        for btn in [self.btn_add, self.btn_edit, self.btn_remove, self.btn_close]:
            btn_layout.addWidget(btn)
        
        layout.addLayout(btn_layout)
        
        # Подключение событий таблицы
        self.table.selectionModel().selectionChanged.connect(self._on_selection_changed)
        self.table.doubleClicked.connect(self._edit_supplier)
        
        # Начальное состояние кнопок
        self._update_buttons_state()
    
    @handle_gui_errors(context="load_suppliers_data")
    def _load_data(self):
        """Загрузка данных поставщиков."""
        self.table.setRowCount(0)
        
        # Выполняем запрос с подсчетом использования
        query = """
            SELECT 
                s.id, 
                s.name, 
                COUNT(m.id) as used_count
            FROM Suppliers s 
            LEFT JOIN Materials m ON m.supplier_id = s.id 
            GROUP BY s.id, s.name
            ORDER BY s.name
        """
        
        try:
            rows = self.db.conn.execute(query).fetchall()
            
            for row in rows:
                self._add_table_row(row)
            
            self.table.resizeColumnsToContents()
            self._update_buttons_state()
            
            self.logger.debug(f"Загружено {len(rows)} поставщиков")
            
        except Exception as e:
            self.logger.error(f"Ошибка загрузки данных поставщиков: {e}")
            raise
    
    def _add_table_row(self, row_data: Dict[str, Any]):
        """Добавляет строку в таблицу."""
        row_index = self.table.rowCount()
        self.table.insertRow(row_index)
        
        # Название поставщика
        name_item = QTableWidgetItem(row_data['name'])
        name_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        name_item.setData(Qt.UserRole, row_data['id'])
        
        # Количество использований
        used_item = QTableWidgetItem(str(row_data['used_count']))
        used_item.setTextAlignment(Qt.AlignCenter)
        
        self.table.setItem(row_index, 0, name_item)
        self.table.setItem(row_index, 1, used_item)
    
    def _on_selection_changed(self):
        """Обработка изменения выделения в таблице."""
        self._update_buttons_state()
    
    def _update_buttons_state(self):
        """Обновление состояния кнопок в зависимости от выделения."""
        has_selection = self.table.currentRow() >= 0
        self.btn_edit.setEnabled(has_selection)
        self.btn_remove.setEnabled(has_selection)
    
    def _show_supplier_dialog(self, title: str, initial_text: str = '') -> Optional[str]:
        """
        Показывает диалог для ввода/редактирования поставщика.
        
        Args:
            title: Заголовок диалога
            initial_text: Начальный текст
            
        Returns:
            Введенный текст или None при отмене
        """
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.setModal(True)
        dialog.resize(300, 120)
        
        layout = QFormLayout(dialog)
        
        # Поле ввода
        line_edit = QLineEdit(initial_text)
        line_edit.setMaxLength(100)  # Ограничение длины
        layout.addRow('Поставщик:', line_edit)
        
        # Кнопки
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        layout.addRow(button_box)
        
        # Подключение сигналов
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        
        # Фокус на поле ввода
        line_edit.setFocus()
        line_edit.selectAll()
        
        if dialog.exec_() == QDialog.Accepted:
            return line_edit.text().strip()
        
        return None
    
    @handle_gui_errors(context="add_supplier")
    @handle_database_errors("добавление поставщика")
    def _add_supplier(self):
        """Добавление нового поставщика."""
        supplier_name = self._show_supplier_dialog('Добавить поставщика')
        
        if not supplier_name:
            return
        
        # Валидация
        self._validate_supplier_name(supplier_name)
        
        # Проверка уникальности
        existing_query = "SELECT COUNT(*) as count FROM Suppliers WHERE LOWER(name) = LOWER(?)"
        result = self.db.conn.execute(existing_query, (supplier_name,)).fetchone()
        
        if result['count'] > 0:
            raise DuplicateRecordError(
                f"Поставщик '{supplier_name}' уже существует",
                suggestions=[
                    "Выберите другое название",
                    "Проверьте список существующих поставщиков"
                ]
            )
        
        # Добавление в БД
        insert_query = "INSERT INTO Suppliers (name) VALUES (?)"
        cursor = self.db.conn.execute(insert_query, (supplier_name,))
        self.db.conn.commit()
        
        supplier_id = cursor.lastrowid
        
        # Логирование
        log_audit(
            self.user,
            'create_supplier',
            supplier_id,
            f"Добавлен поставщик '{supplier_name}'"
        )
        
        # Обновление интерфейса
        self._load_data()
        show_success_message(
            "Успех",
            f"Поставщик '{supplier_name}' успешно добавлен",
            parent=self,
            auto_close=3
        )
        
        self.logger.info(f"Добавлен поставщик: {supplier_name} (ID: {supplier_id})")
    
    @handle_gui_errors(context="edit_supplier")
    @handle_database_errors("изменение поставщика")
    def _edit_supplier(self):
        """Редактирование выбранного поставщика."""
        row = self.table.currentRow()
        if row < 0:
            show_warning("Выберите поставщика для редактирования", parent=self)
            return
        
        # Получение данных
        name_item = self.table.item(row, 0)
        supplier_id = name_item.data(Qt.UserRole)
        old_name = name_item.text()
        used_count = int(self.table.item(row, 1).text())
        
        # Проверка возможности редактирования
        if used_count > 0:
            raise RecordInUseError(
                f"Поставщик '{old_name}' используется в {used_count} материалах",
                record_type="поставщик",
                used_in=["материалы"],
                suggestions=[
                    "Сначала измените поставщика в связанных материалах",
                    "Создайте нового поставщика вместо изменения существующего"
                ]
            )
        
        # Диалог редактирования
        new_name = self._show_supplier_dialog('Изменить поставщика', old_name)
        
        if not new_name or new_name == old_name:
            return
        
        # Валидация
        self._validate_supplier_name(new_name)
        
        # Проверка уникальности (исключая текущую запись)
        unique_query = """
            SELECT COUNT(*) as count 
            FROM Suppliers 
            WHERE LOWER(name) = LOWER(?) AND id != ?
        """
        result = self.db.conn.execute(unique_query, (new_name, supplier_id)).fetchone()
        
        if result['count'] > 0:
            raise DuplicateRecordError(
                f"Поставщик '{new_name}' уже существует",
                suggestions=[
                    "Выберите другое название",
                    "Проверьте список существующих поставщиков"
                ]
            )
        
        # Обновление в БД
        update_query = "UPDATE Suppliers SET name = ? WHERE id = ?"
        self.db.conn.execute(update_query, (new_name, supplier_id))
        self.db.conn.commit()
        
        # Логирование
        log_audit(
            self.user,
            'update_supplier',
            supplier_id,
            f"Поставщик изменен с '{old_name}' на '{new_name}'"
        )
        
        # Обновление интерфейса
        self._load_data()
        show_success_message(
            "Успех",
            f"Поставщик успешно изменен",
            parent=self,
            auto_close=3
        )
        
        self.logger.info(f"Изменен поставщик: {old_name} -> {new_name} (ID: {supplier_id})")
    
    @handle_gui_errors(context="remove_supplier")
    @handle_database_errors("удаление поставщика")
    def _remove_supplier(self):
        """Удаление выбранного поставщика."""
        row = self.table.currentRow()
        if row < 0:
            show_warning("Выберите поставщика для удаления", parent=self)
            return
        
        # Получение данных
        name_item = self.table.item(row, 0)
        supplier_id = name_item.data(Qt.UserRole)
        supplier_name = name_item.text()
        used_count = int(self.table.item(row, 1).text())
        
        # Проверка возможности удаления
        if used_count > 0:
            raise RecordInUseError(
                f"Поставщик '{supplier_name}' используется в {used_count} материалах",
                record_type="поставщик",
                used_in=["материалы"],
                suggestions=[
                    "Сначала удалите или измените поставщика в связанных материалах",
                    "Используйте функцию архивирования вместо удаления"
                ]
            )
        
        # Подтверждение удаления
        if not confirm_action(
            f"Вы уверены, что хотите удалить поставщика '{supplier_name}'?\n\n"
            "Это действие нельзя отменить.",
            parent=self,
            title="Подтверждение удаления"
        ):
            return
        
        # Удаление из БД
        delete_query = "DELETE FROM Suppliers WHERE id = ?"
        self.db.conn.execute(delete_query, (supplier_id,))
        self.db.conn.commit()
        
        # Логирование
        log_audit(
            self.user,
            'delete_supplier',
            supplier_id,
            f"Удален поставщик '{supplier_name}'"
        )
        
        # Обновление интерфейса
        self._load_data()
        show_success_message(
            "Успех",
            f"Поставщик '{supplier_name}' успешно удален",
            parent=self,
            auto_close=3
        )
        
        self.logger.info(f"Удален поставщик: {supplier_name} (ID: {supplier_id})")
    
    def _validate_supplier_name(self, name: str):
        """
        Валидация названия поставщика.
        
        Args:
            name: Название для проверки
            
        Raises:
            RequiredFieldError: Если название пустое
            ValidationError: Если название некорректное
        """
        if not name:
            raise RequiredFieldError(
                "Название поставщика не может быть пустым",
                field_name="name"
            )
        
        if len(name) < 2:
            raise ValidationError(
                "Название поставщика слишком короткое",
                field_name="name",
                field_value=name,
                suggestions=["Введите название длиной минимум 2 символа"]
            )
        
        if len(name) > 100:
            raise ValidationError(
                "Название поставщика слишком длинное",
                field_name="name",
                field_value=name,
                suggestions=["Сократите название до 100 символов"]
            )
        
        # Проверка на запрещенные символы
        forbidden_chars = ['<', '>', '"', "'", '&']
        for char in forbidden_chars:
            if char in name:
                raise ValidationError(
                    f"Название содержит недопустимый символ: {char}",
                    field_name="name",
                    field_value=name,
                    suggestions=["Удалите недопустимые символы из названия"]
                )
    
    def closeEvent(self, event):
        """Обработка закрытия окна."""
        try:
            if hasattr(self, 'db') and self.db:
                self.db.close()
            
            self.logger.info("Закрыт справочник поставщиков")
            
        except Exception as e:
            self.logger.error(f"Ошибка при закрытии справочника поставщиков: {e}")
        
        super().closeEvent(event)


# Пример использования нового класса
if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    # Пример пользователя
    user = {
        'id': 1,
        'login': 'admin',
        'role': 'Администратор',
        'name': 'Администратор'
    }
    
    # Создание и показ окна
    window = SuppliersAdminNew(user=user)
    window.show()
    
    sys.exit(app.exec_()) 
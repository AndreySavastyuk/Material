# gui/admin/suppliers.py — справочник поставщиков с операциями Добавить, Изменить, Удалить
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QMessageBox, QFormLayout, QLineEdit, QDialogButtonBox
)
from PyQt5.QtCore import Qt
from db.database import Database

class SuppliersAdmin(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Справочник поставщиков')
        self.db = Database(); self.db.connect()
        self._build()
        self._load()

    def _build(self):
        layout = QVBoxLayout(self)

        # Таблица поставщиков
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(['Поставщик', 'Применяется'])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table)

        # Кнопки действий
        btn_layout = QHBoxLayout()
        btn_add = QPushButton('Добавить')
        btn_edit = QPushButton('Изменить')
        btn_remove = QPushButton('Удалить')
        btn_close = QPushButton('Закрыть')
        btn_add.clicked.connect(self._add_supplier)
        btn_edit.clicked.connect(self._edit_supplier)
        btn_remove.clicked.connect(self._remove_supplier)
        btn_close.clicked.connect(self.accept)
        for btn in (btn_add, btn_edit, btn_remove, btn_close):
            btn_layout.addWidget(btn)
        layout.addLayout(btn_layout)

    def _load(self):
        self.table.setRowCount(0)
        rows = self.db.conn.execute(
            'SELECT s.id, s.name, COUNT(m.id) as used FROM Suppliers s '
            'LEFT JOIN Materials m ON m.supplier_id = s.id '
            'GROUP BY s.id ORDER BY s.id'
        ).fetchall()
        for r in rows:
            i = self.table.rowCount()
            self.table.insertRow(i)
            name_item = QTableWidgetItem(r['name'])
            name_item.setTextAlignment(Qt.AlignCenter)
            name_item.setData(Qt.UserRole, r['id'])
            used_item = QTableWidgetItem(str(r['used']))
            used_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(i, 0, name_item)
            self.table.setItem(i, 1, used_item)
        self.table.resizeColumnsToContents()

    def _show_dialog(self, title, text=''):
        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        form = QFormLayout(dlg)
        le = QLineEdit(text)
        form.addRow('Поставщик:', le)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        form.addRow(bb)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        if dlg.exec_() == QDialog.Accepted:
            return le.text().strip()
        return None

    def _add_supplier(self):
        res = self._show_dialog('Добавить поставщика')
        if not res:
            return
        try:
            self.db.conn.execute(
                'INSERT INTO Suppliers(name) VALUES(?)', (res,)
            )
            self.db.conn.commit()
            self._load()
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка добавления', str(e))

    def _edit_supplier(self):
        row = self.table.currentRow()
        if row < 0:
            return
        name_item = self.table.item(row, 0)
        sid = name_item.data(Qt.UserRole)
        old = name_item.text()
        res = self._show_dialog('Изменить поставщика', old)
        if not res or res == old:
            return
        try:
            used = int(self.table.item(row, 1).text())
            if used:
                QMessageBox.warning(self, 'Ошибка', 'Поставщик используется в материалах')
                return
            self.db.conn.execute(
                'UPDATE Suppliers SET name=? WHERE id=?', (res, sid)
            )
            self.db.conn.commit()
            self._load()
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка изменения', str(e))

    def _remove_supplier(self):
        row = self.table.currentRow()
        if row < 0:
            return
        name_item = self.table.item(row, 0)
        sid = name_item.data(Qt.UserRole)
        name = name_item.text()
        used = int(self.table.item(row, 1).text())
        if used:
            QMessageBox.warning(self, 'Ошибка', 'Нельзя удалить: поставщик используется')
            return
        if QMessageBox.question(
            self, 'Удалить', f'Удалить поставщика "{name}"?'
        ) == QMessageBox.Yes:
            try:
                self.db.conn.execute('DELETE FROM Suppliers WHERE id=?', (sid,))
                self.db.conn.commit()
                self._load()
            except Exception as e:
                QMessageBox.critical(self, 'Ошибка удаления', str(e))

# gui/admin/rolling_types.py — справочник видов проката с операциями Добавить, Изменить, Удалить
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QMessageBox, QFormLayout, QLineEdit, QDialogButtonBox
)
from PyQt5.QtCore import Qt
from db.database import Database

class RollingTypesAdmin(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Справочник видов проката')
        self.db = Database(); self.db.connect()
        self._build()
        self._load()

    def _build(self):
        layout = QVBoxLayout(self)
        # Таблица видов проката
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(['Вид проката', 'Применяется'])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table)

        # Кнопки действий
        btn_layout = QHBoxLayout()
        btn_add = QPushButton('Добавить')
        btn_edit = QPushButton('Изменить')
        btn_remove = QPushButton('Удалить')
        btn_close = QPushButton('Закрыть')
        btn_add.clicked.connect(self._add_type)
        btn_edit.clicked.connect(self._edit_type)
        btn_remove.clicked.connect(self._remove_type)
        btn_close.clicked.connect(self.accept)
        for btn in (btn_add, btn_edit, btn_remove, btn_close):
            btn_layout.addWidget(btn)
        layout.addLayout(btn_layout)

    def _load(self):
        self.table.setRowCount(0)
        rows = self.db.conn.execute(
            'SELECT rt.id, rt.type, COUNT(m.id) as used '
            'FROM RollingTypes rt '
            'LEFT JOIN Materials m ON m.rolling_type_id = rt.id '
            'GROUP BY rt.id ORDER BY rt.id'
        ).fetchall()
        for r in rows:
            i = self.table.rowCount()
            self.table.insertRow(i)
            type_item = QTableWidgetItem(r['type'])
            type_item.setTextAlignment(Qt.AlignCenter)
            type_item.setData(Qt.UserRole, r['id'])
            used_item = QTableWidgetItem(str(r['used']))
            used_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(i, 0, type_item)
            self.table.setItem(i, 1, used_item)
        self.table.resizeColumnsToContents()

    def _show_dialog(self, title, text=''):
        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        form = QFormLayout(dlg)
        le = QLineEdit(text)
        form.addRow('Вид проката:', le)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        form.addRow(bb)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        if dlg.exec_() == QDialog.Accepted:
            return le.text().strip()
        return None

    def _add_type(self):
        res = self._show_dialog('Добавить вид проката')
        if not res:
            return
        try:
            self.db.conn.execute('INSERT INTO RollingTypes(type) VALUES(?)', (res,))
            self.db.conn.commit()
            self._load()
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка добавления', str(e))

    def _edit_type(self):
        row = self.table.currentRow()
        if row < 0:
            return
        item = self.table.item(row, 0)
        tid = item.data(Qt.UserRole)
        old = item.text()
        res = self._show_dialog('Изменить вид проката', old)
        if not res or res == old:
            return
        try:
            used = int(self.table.item(row, 1).text())
            if used:
                QMessageBox.warning(self, 'Ошибка', 'Вид проката используется в материалах')
                return
            self.db.conn.execute('UPDATE RollingTypes SET type=? WHERE id=?', (res, tid))
            self.db.conn.commit()
            self._load()
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка изменения', str(e))

    def _remove_type(self):
        row = self.table.currentRow()
        if row < 0:
            return
        item = self.table.item(row, 0)
        tid = item.data(Qt.UserRole)
        name = item.text()
        used = int(self.table.item(row, 1).text())
        if used:
            QMessageBox.warning(self, 'Ошибка', 'Нельзя удалить: этот вид проката используется')
            return
        if QMessageBox.question(self, 'Удалить', f'Удалить вид проката "{name}"?') == QMessageBox.Yes:
            try:
                self.db.conn.execute('DELETE FROM RollingTypes WHERE id=?', (tid,))
                self.db.conn.commit()
                self._load()
            except Exception as e:
                QMessageBox.critical(self, 'Ошибка удаления', str(e))

# gui/admin/grades.py — справочник марок материала с операциями Добавить, Изменить, Удалить
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QMessageBox, QFormLayout, QLineEdit, QDialogButtonBox, QLabel
)
from PyQt5.QtCore import Qt
from db.database import Database

class GradesAdmin(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Справочник марок материала')
        self.db = Database(); self.db.connect()
        self._build()
        self._load()

    def _build(self):
        layout = QVBoxLayout(self)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(['Марка', 'Плотность', 'Стандарт'])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table)

        btn_layout = QHBoxLayout()
        btn_add = QPushButton('Добавить')
        btn_edit = QPushButton('Изменить')
        btn_remove = QPushButton('Удалить')
        btn_close = QPushButton('Закрыть')
        btn_add.clicked.connect(self._add_grade)
        btn_edit.clicked.connect(self._edit_grade)
        btn_remove.clicked.connect(self._remove_grade)
        btn_close.clicked.connect(self.accept)
        for btn in (btn_add, btn_edit, btn_remove, btn_close):
            btn_layout.addWidget(btn)
        layout.addLayout(btn_layout)

    def _load(self):
        self.table.setRowCount(0)
        rows = self.db.conn.execute(
            'SELECT id, grade, density, standard FROM Grades ORDER BY id'
        ).fetchall()
        for r in rows:
            i = self.table.rowCount()
            self.table.insertRow(i)
            items = [
                QTableWidgetItem(r['grade']),
                QTableWidgetItem(str(r['density'])),
                QTableWidgetItem(r['standard'])
            ]
            for col, item in enumerate(items):
                item.setTextAlignment(Qt.AlignCenter)
                if col == 0:
                    item.setData(Qt.UserRole, r['id'])
                self.table.setItem(i, col, item)
        self.table.resizeColumnsToContents()

    def _show_dialog(self, title, grade='', density='', standard=''):
        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        form = QFormLayout(dlg)
        ge = QLineEdit(grade); de = QLineEdit(density); se = QLineEdit(standard)
        form.addRow('Марка:', ge)
        form.addRow('Плотность:', de)
        form.addRow('Стандарт:', se)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        form.addRow(bb)
        bb.accepted.connect(dlg.accept); bb.rejected.connect(dlg.reject)
        if dlg.exec_() == QDialog.Accepted:
            return ge.text().strip(), de.text().strip(), se.text().strip()
        return None

    def _add_grade(self):
        res = self._show_dialog('Добавить марку')
        if not res:
            return
        grade, density, standard = res
        try:
            d = float(density)
        except ValueError:
            QMessageBox.warning(self, 'Ошибка', 'Плотность должна быть числом')
            return
        if not grade:
            QMessageBox.warning(self, 'Ошибка', 'Введите название марки')
            return
        try:
            self.db.conn.execute(
                'INSERT INTO Grades(grade, density, standard) VALUES(?,?,?)',
                (grade, d, standard)
            ); self.db.conn.commit()
            self._load()
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка добавления', str(e))

    def _edit_grade(self):
        r = self.table.currentRow()
        if r < 0:
            return
        item = self.table.item(r, 0)
        gid = item.data(Qt.UserRole)
        cur = [self.table.item(r, c).text() for c in range(3)]
        res = self._show_dialog('Изменить марку', *cur)
        if not res:
            return
        grade, density, standard = res
        try:
            d = float(density)
        except ValueError:
            QMessageBox.warning(self, 'Ошибка', 'Плотность должна быть числом')
            return
        try:
            # проверка использования
            cnt = self.db.conn.execute(
                'SELECT COUNT(*) FROM Materials WHERE grade_id=?', (gid,)
            ).fetchone()[0]
            if cnt:
                QMessageBox.warning(self, 'Ошибка', 'Марка используется в материалах')
                return
            self.db.conn.execute(
                'UPDATE Grades SET grade=?, density=?, standard=? WHERE id=?',
                (grade, d, standard, gid)
            ); self.db.conn.commit()
            self._load()
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка изменения', str(e))

    def _remove_grade(self):
        r = self.table.currentRow()
        if r < 0:
            return
        item = self.table.item(r, 0)
        gid = item.data(Qt.UserRole)
        text = item.text()
        # проверка использования
        cnt = self.db.conn.execute(
            'SELECT COUNT(*) FROM Materials WHERE grade_id=?', (gid,)
        ).fetchone()[0]
        if cnt:
            QMessageBox.warning(self, 'Ошибка', 'Нельзя удалить: марка используется')
            return
        if QMessageBox.question(
            self, 'Удалить', f'Удалить марку "{text}"?'
        ) == QMessageBox.Yes:
            try:
                self.db.conn.execute('DELETE FROM Grades WHERE id=?', (gid,))
                self.db.conn.commit()
                self._load()
            except Exception as e:
                QMessageBox.critical(self, 'Ошибка удаления', str(e))

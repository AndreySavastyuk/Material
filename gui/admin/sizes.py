from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QHBoxLayout, QDialogButtonBox, QInputDialog, QMessageBox
)
from db.database import Database

class SizesAdmin(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Справочник размеров проката')
        self.db = Database(); self.db.connect()
        self._build(); self._load()

    def _build(self):
        layout = QVBoxLayout()
        self.table = QTableWidget(0,3)
        self.table.setHorizontalHeaderLabels(['ID','Вид проката','Размер'])
        layout.addWidget(self.table)
        btn_layout = QHBoxLayout()
        self.btn_add = QPushButton('Добавить'); self.btn_edit = QPushButton('Изменить'); self.btn_del = QPushButton('Удалить')
        btn_layout.addWidget(self.btn_add); btn_layout.addWidget(self.btn_edit); btn_layout.addWidget(self.btn_del)
        layout.addLayout(btn_layout)
        buttons = QDialogButtonBox(QDialogButtonBox.Close); buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.setLayout(layout)
        self.btn_add.clicked.connect(self._add); self.btn_edit.clicked.connect(self._edit); self.btn_del.clicked.connect(self._delete)

    def _load(self):
        rows = self.db.conn.execute(
            'SELECT s.id, rt.type, s.size FROM Sizes s JOIN RollingTypes rt ON s.rolling_type_id=rt.id'
        ).fetchall()
        self.table.setRowCount(len(rows))
        for i,r in enumerate(rows):
            self.table.setItem(i,0,QTableWidgetItem(str(r['id'])))
            self.table.setItem(i,1,QTableWidgetItem(r['type']))
            self.table.setItem(i,2,QTableWidgetItem(r['size']))
        self.table.resizeColumnsToContents()

    def _add(self):
        # Получить список типов
        types = [r['type'] for r in self.db.conn.execute('SELECT type FROM RollingTypes')]
        choice, ok1 = QInputDialog.getItem(self, 'Выберите тип проката', 'Тип:', types, 0, False)
        if not (ok1 and choice): return
        size, ok2 = QInputDialog.getText(self, 'Новый размер', 'Размер (мм):')
        if not (ok2 and size.strip()): return
        # найти id типа
        rid = self.db.conn.execute('SELECT id FROM RollingTypes WHERE type=?', (choice,)).fetchone()['id']
        try:
            self.db.conn.execute(
                'INSERT INTO Sizes(rolling_type_id,size) VALUES(?,?)', (rid, size.strip())
            )
            self.db.conn.commit(); self._load()
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', str(e))

    def _edit(self):
        row = self.table.currentRow()
        if row < 0: return
        sid = int(self.table.item(row,0).text())
        oldsize = self.table.item(row,2).text()
        size, ok = QInputDialog.getText(self, 'Изменить размер', 'Размер (мм):', text=oldsize)
        if not (ok and size.strip()): return
        try:
            self.db.conn.execute('UPDATE Sizes SET size=? WHERE id=?', (size.strip(), sid))
            self.db.conn.commit(); self._load()
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', str(e))

    def _delete(self):
        row = self.table.currentRow()
        if row < 0: return
        sid = int(self.table.item(row,0).text())
        if QMessageBox.question(self, 'Удалить', 'Удалить размер?') == QMessageBox.Yes:
            try:
                self.db.conn.execute('DELETE FROM Sizes WHERE id=?', (sid,))
                self.db.conn.commit(); self._load()
            except Exception as e:
                QMessageBox.critical(self, 'Ошибка', str(e))
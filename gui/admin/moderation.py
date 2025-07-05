from PyQt5.QtWidgets import (
    QDialog, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QPushButton, QHBoxLayout, QMessageBox, QWidget
)
from PyQt5.QtCore import Qt
from db.database import Database

class ModerationDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Модерация удалённых материалов')
        self.db = Database()
        self.db.connect()
        self._build()
        self._load()

    def _build(self):
        layout = QVBoxLayout()

        # Таблица помеченных на удаление
        self.table = QTableWidget()
        headers = ['ID', 'Дата прихода', 'Поставщик', 'Номер заказа']
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table)

        # Кнопки действий
        btn_layout = QHBoxLayout()
        self.btn_restore = QPushButton('Восстановить')
        self.btn_remove = QPushButton('Удалить навсегда')
        self.btn_restore.clicked.connect(self._restore)
        self.btn_remove.clicked.connect(self._permanent_delete)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_restore)
        btn_layout.addWidget(self.btn_remove)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

    def _load(self):
        rows = self.db.get_marked_for_deletion()
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            vals = [r['id'], r['arrival_date'], r['supplier'], r['order_num']]
            for j, v in enumerate(vals):
                item = QTableWidgetItem(str(v))
                item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(i, j, item)
        self.table.resizeColumnsToContents()

    def _restore(self):
        row = self.table.currentRow()
        if row < 0:
            return
        mid = int(self.table.item(row, 0).text())
        self.db.unmark_material(mid)
        QMessageBox.information(self, 'Готово', f'Материал ID {mid} восстановлен')
        self._load()

    def _permanent_delete(self):
        row = self.table.currentRow()
        if row < 0:
            return
        mid = int(self.table.item(row, 0).text())
        confirm = QMessageBox.question(
            self, 'Подтверждение', f'Удалить материал ID {mid} навсегда?'
        )
        if confirm == QMessageBox.Yes:
            self.db.permanently_delete_material(mid)
            QMessageBox.information(self, 'Готово', f'Материал ID {mid} удалён')
            self._load()

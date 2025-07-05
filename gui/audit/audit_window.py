# gui/audit/audit_window.py

import os
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem
)
from PyQt5.QtCore import Qt

class AuditWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Журнал действий")
        self.resize(800, 600)
        # Путь к файлу с логами
        self.log_path = os.path.join(os.getcwd(), "audit.log")

        self._build_ui()
        self._load_logs()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels([
            "Время", "Пользователь", "Событие", "ID объекта", "Описание"
        ])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(self.table.SelectRows)
        layout.addWidget(self.table)

    def _load_logs(self):
        if not os.path.exists(self.log_path):
            return
        with open(self.log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        self.table.setRowCount(len(lines))
        for i, line in enumerate(lines):
            # Ожидаем формат: timestamp | user | event | obj_id | description
            parts = [p.strip() for p in line.split("|")]
            for j, part in enumerate(parts):
                item = QTableWidgetItem(part)
                item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(i, j, item)
        self.table.resizeColumnsToContents()

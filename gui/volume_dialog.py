# gui/volume_dialog.py

import math
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLineEdit, QMessageBox
)
from PyQt5.QtCore import Qt

class VolumeDialog(QDialog):
    def __init__(self, parent=None, initial_data=None):
        super().__init__(parent)
        self.setWindowTitle("Диалог объема")
        self.resize(600, 400)
        self.initial_data = initial_data or []

        # Поле ввода формулы и кнопка "Ввод"
        self.input_line = QLineEdit(self)
        self.input_line.setPlaceholderText("Введите формулу: 3475*10+5768*2+1000")
        self.btn_enter = QPushButton("Ввод", self)
        self.btn_enter.setEnabled(False)
        self.btn_enter.clicked.connect(self._process_formula)
        self.input_line.textChanged.connect(
            lambda text: self.btn_enter.setEnabled(bool(text.strip()))
        )
        hl_input = QHBoxLayout()
        hl_input.addWidget(self.input_line)
        hl_input.addWidget(self.btn_enter)

        # Таблица для длины и количества
        self.table = QTableWidget(10, 2, self)
        self.table.setHorizontalHeaderLabels(["Длина (мм)", "Количество"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self._load_initial()

        # Кнопки OK/Отмена
        btn_ok = QPushButton("OK", self)
        btn_ok.clicked.connect(self.accept)
        btn_cancel = QPushButton("Отмена", self)
        btn_cancel.clicked.connect(self.reject)
        hl_buttons = QHBoxLayout()
        hl_buttons.addStretch()
        hl_buttons.addWidget(btn_ok)
        hl_buttons.addWidget(btn_cancel)

        # Основная компоновка
        vl = QVBoxLayout(self)
        vl.addLayout(hl_input)
        vl.addWidget(self.table)
        vl.addLayout(hl_buttons)

    def _load_initial(self):
        """Заполнить таблицу начальными данными, округляя до целого."""
        for idx, item in enumerate(self.initial_data):
            if idx < self.table.rowCount():
                length_item = QTableWidgetItem(str(int(round(item['length']))))
                count_item  = QTableWidgetItem(str(int(round(item['count']))))
                length_item.setTextAlignment(Qt.AlignCenter)
                count_item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(idx, 0, length_item)
                self.table.setItem(idx, 1, count_item)

    def _process_formula(self):
        """Разбор формулы вида 3475*10+5768*2+1000 и заполнение строк."""
        formula = self.input_line.text().lstrip('=+-')
        terms = formula.split('+')
        parsed = []
        for term in terms:
            parts = term.split('*')
            try:
                length = int(parts[0])
                count  = int(parts[1]) if len(parts) > 1 and parts[1] else 1
            except ValueError:
                QMessageBox.warning(self, "Ошибка", f"Некорректный термин: {term}")
                return
            parsed.append((length, count))

        # Очистить таблицу
        for r in range(self.table.rowCount()):
            self.table.setItem(r, 0, QTableWidgetItem(''))
            self.table.setItem(r, 1, QTableWidgetItem(''))

        # Заполнить новыми данными
        self.initial_data = []
        for idx, (length, count) in enumerate(parsed):
            if idx < self.table.rowCount():
                self.table.setItem(idx, 0, QTableWidgetItem(str(length)))
                self.table.setItem(idx, 1, QTableWidgetItem(str(count)))
                self.initial_data.append({'length': length, 'count': count})

    def get_data(self):
        """Вернуть список словарей {'length': ..., 'count': ...} из таблицы."""
        result = []
        for row in range(self.table.rowCount()):
            li = self.table.item(row, 0)
            ci = self.table.item(row, 1)
            if li and ci and li.text().isdigit():
                try:
                    length = int(li.text())
                    count  = int(ci.text())
                    result.append({"length": length, "count": count})
                except ValueError:
                    continue
        return result

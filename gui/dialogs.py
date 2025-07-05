# gui/dialogs.py

import math
import sqlite3
from PyQt5.QtWidgets import (
    QDialog, QGridLayout, QVBoxLayout, QHBoxLayout, QDateEdit,
    QLabel, QComboBox, QLineEdit, QCheckBox, QPushButton, QMessageBox
)
from PyQt5.QtCore import Qt, QDate, QEvent, QRegExp
from PyQt5.QtGui import QDoubleValidator, QRegExpValidator

from db.database import Database
from gui.volume_dialog import VolumeDialog


class AddMaterialDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Добавить материал")
        self.resize(600, 650)

        # хранение данных объёма
        self.volume_data = []

        # подключение к базе
        self.db = Database()
        self.db.connect()
        today = QDate.currentDate()

        # --- Поля формы ---

        # Дата прихода
        lbl_date = QLabel("Дата прихода:")
        self.date_arrival = QDateEdit()
        self.date_arrival.setDisplayFormat("dd.MM.yyyy")
        self.date_arrival.setDate(today)
        self.date_arrival.setCalendarPopup(True)
        self.date_arrival.setMinimumDate(today.addDays(-10))
        self.date_arrival.setMaximumDate(today.addDays(2))

        # Поставщик
        lbl_supplier = QLabel("Поставщик:")
        self.cmb_supplier = QComboBox()
        self.cmb_supplier.addItem("", None)
        for sup in self.db.conn.execute("SELECT id, name FROM Suppliers"):
            self.cmb_supplier.addItem(sup[1], sup[0])

        # Номер заказа
        lbl_order = QLabel("Номер заказа:")
        self.le_order = QLineEdit()
        self.le_order.setPlaceholderText("____/___")
        reg = QRegExp(r"^\d{0,4}/?\d{0,3}$")
        self.le_order.setValidator(QRegExpValidator(reg, self.le_order))
        cw = self.le_order.fontMetrics().averageCharWidth()
        self.le_order.setFixedWidth(cw * 16)
        self.le_order.setAlignment(Qt.AlignHCenter)
        self.le_order.installEventFilter(self)
        self.le_order.textChanged.connect(self._format_order)

        # «Другое» для заказа
        self.chk_custom = QCheckBox("Другое")
        self.cmb_custom_order = QComboBox()
        try:
            rows = self.db.conn.execute("SELECT id, name FROM CustomOrders").fetchall()
        except sqlite3.OperationalError:
            rows = []
        if rows:
            for o in rows:
                self.cmb_custom_order.addItem(o[1], o[0])
            self.chk_custom.stateChanged.connect(self._toggle_order)
        else:
            self.chk_custom.setEnabled(False)
            self.cmb_custom_order.setEnabled(False)
        self.cmb_custom_order.setFixedWidth(cw * 20)

        # Марка материала (с плотностью)
        lbl_grade = QLabel("Марка материала:")
        self.cmb_grade = QComboBox()
        for g in self.db.conn.execute("SELECT id, grade, density FROM Grades"):
            self.cmb_grade.addItem(g[1], (g[0], g[2]))

        # Вид проката
        lbl_type = QLabel("Вид проката:")
        self.cmb_type = QComboBox()
        info = self.db.conn.execute("PRAGMA table_info(RollingTypes)").fetchall()
        col = info[1][1] if len(info) > 1 else (info[0][1] if info else "id")
        for rt in self.db.conn.execute(f"SELECT id, {col} FROM RollingTypes"):
            self.cmb_type.addItem(rt[1], rt[0])
        idx = self.cmb_type.findText("Круг")
        self.cmb_type.setCurrentIndex(idx if idx >= 0 else 0)
        self.cmb_type.currentTextChanged.connect(self._update_size_fields)

        # Сертификат
        lbl_cert = QLabel("Сертификат №:")
        self.le_cert = QLineEdit()
        lbl_cert_date = QLabel("Дата сертификата:")
        self.date_cert = QDateEdit()
        self.date_cert.setDisplayFormat("dd.MM.yyyy")
        self.date_cert.setCalendarPopup(True)
        self.date_cert.setDate(today)

        # Плавка и партия
        lbl_heat = QLabel("Плавка:")
        self.le_heat = QLineEdit()
        lbl_batch = QLabel("Партия:")
        self.le_batch = QLineEdit()
        self.le_batch.setText("Нет")
        self.le_batch.installEventFilter(self)

        # Размеры
        lbl_dim1 = QLabel("Размер 1 (мм):")
        self.le_dim1 = QLineEdit()
        self.le_dim1.setValidator(QDoubleValidator(0, 1e6, 3))
        lbl_dim2 = QLabel("Размер 2 (мм):")
        self.le_dim2 = QLineEdit()
        self.le_dim2.setValidator(QDoubleValidator(0, 1e6, 3))

        # Кнопка «Объем…»
        self.btn_volume = QPushButton("Объем...")
        self.btn_volume.clicked.connect(self._open_volume_dialog)
        self.lbl_volume_info = QLabel("")

        # Отображение веса
        self.lbl_weight = QLabel("Вес партии - 0,000 т.")
        self.lbl_weight.setAlignment(Qt.AlignCenter)
        wf = self.lbl_weight.font()
        wf.setPointSize(14)
        wf.setBold(True)
        self.lbl_weight.setFont(wf)

        # Кнопки ОК/Отмена
        btn_ok = QPushButton("Добавить")
        btn_ok.clicked.connect(self._on_accept)
        btn_cancel = QPushButton("Отмена")
        btn_cancel.clicked.connect(self.reject)
        hl_buttons = QHBoxLayout()
        hl_buttons.addStretch()
        hl_buttons.addWidget(btn_ok)
        hl_buttons.addWidget(btn_cancel)

        # Компоновка
        grid = QGridLayout()
        grid.setVerticalSpacing(10)
        grid.setHorizontalSpacing(15)
        grid.addWidget(lbl_date, 0, 0); grid.addWidget(self.date_arrival, 0, 1, 1, 3)
        grid.addWidget(lbl_supplier, 1, 0); grid.addWidget(self.cmb_supplier, 1, 1, 1, 3)
        grid.addWidget(lbl_order, 2, 0); grid.addWidget(self.le_order, 2, 1)
        grid.addWidget(self.chk_custom, 2, 2); grid.addWidget(self.cmb_custom_order, 2, 3)
        grid.addWidget(lbl_grade, 3, 0); grid.addWidget(self.cmb_grade, 3, 1)
        grid.addWidget(lbl_type, 4, 0); grid.addWidget(self.cmb_type, 4, 1)
        grid.addWidget(lbl_cert, 5, 0); grid.addWidget(self.le_cert, 5, 1)
        grid.addWidget(lbl_cert_date, 5, 2); grid.addWidget(self.date_cert, 5, 3)
        grid.addWidget(lbl_heat, 6, 0); grid.addWidget(self.le_heat, 6, 1)
        grid.addWidget(lbl_batch, 6, 2); grid.addWidget(self.le_batch, 6, 3)
        grid.addWidget(lbl_dim1, 7, 0); grid.addWidget(self.le_dim1, 7, 1)
        grid.addWidget(lbl_dim2, 7, 2); grid.addWidget(self.le_dim2, 7, 3)
        grid.addWidget(self.btn_volume, 8, 0); grid.addWidget(self.lbl_volume_info, 8, 1, 1, 3)

        vl = QVBoxLayout(self)
        vl.setContentsMargins(20, 20, 20, 20)
        vl.addLayout(grid)
        vl.addWidget(self.lbl_weight)
        vl.addLayout(hl_buttons)

        # Установить начальное состояние полей размеров
        self._update_size_fields()

    def eventFilter(self, obj, event):
        # Курсор в начале для номера заказа
        if obj is self.le_order and event.type() == QEvent.FocusIn:
            self.le_order.setCursorPosition(0)
        # Очистка/восстановление для партии
        if obj is self.le_batch:
            if event.type() == QEvent.FocusIn and self.le_batch.text() == "Нет":
                self.le_batch.clear()
            if event.type() == QEvent.FocusOut and not self.le_batch.text():
                self.le_batch.setText("Нет")
        return super().eventFilter(obj, event)

    def _format_order(self, text):
        digits = ''.join(ch for ch in text if ch.isdigit())[:7]
        formatted = digits[:4]
        if len(digits) > 4:
            formatted += '/' + digits[4:]
        self.le_order.blockSignals(True)
        self.le_order.setText(formatted)
        self.le_order.blockSignals(False)

    def _toggle_order(self, state):
        custom = state == Qt.Checked
        self.le_order.setEnabled(not custom)
        self.cmb_custom_order.setEnabled(custom)

    def _update_size_fields(self):
        t = self.cmb_type.currentText()
        for w in (self.le_dim1, self.le_dim2):
            w.clear()
            w.setPlaceholderText("")
            w.setEnabled(False)
        if t in ("Круг", "Поковка"):
            self.le_dim1.setPlaceholderText("Диаметр")
            self.le_dim1.setEnabled(True)
        elif t in ("Шестигранник", "Квадрат"):
            self.le_dim1.setPlaceholderText("Размер")
            self.le_dim1.setEnabled(True)
        elif t in ("Лист", "Плита"):
            self.le_dim1.setPlaceholderText("Толщина")
            self.le_dim2.setPlaceholderText("Ширина")
            self.le_dim1.setEnabled(True)
            self.le_dim2.setEnabled(True)
        elif t == "Труба":
            self.le_dim1.setPlaceholderText("Наружный диаметр")
            self.le_dim2.setPlaceholderText("Толщина стенки")
            self.le_dim1.setEnabled(True)
            self.le_dim2.setEnabled(True)

    def _open_volume_dialog(self):
        dlg = VolumeDialog(self, initial_data=self.volume_data)
        if dlg.exec_() == QDialog.Accepted:
            self.volume_data = dlg.get_data()
            total_mm = sum(i['length'] * i['count'] for i in self.volume_data)
            total_m  = total_mm / 1000
            self.lbl_volume_info.setText(f"{total_mm:.0f} мм ({total_m:.2f} м)")
            QMessageBox.information(self, "Объем", f"Общая длина: {total_m:.2f} м")
            self._calculate_weight()

    def _calculate_weight(self):
        grade = self.cmb_grade.currentData()
        if not grade:
            return
        _, density = grade
        t = self.cmb_type.currentText()
        a1 = float(self.le_dim1.text() or 0) / 1000
        a2 = float(self.le_dim2.text() or 0) / 1000
        area = 0
        if t in ("Круг", "Поковка"):
            area = math.pi * (a1 / 2) ** 2
        elif t == "Шестигранник":
            area = 3 * math.sqrt(3) / 2 * (a1 ** 2)
        elif t in ("Лист", "Плита"):
            area = a1 * a2
        elif t == "Труба":
            outer = a1
            wall  = a2
            inner = outer - 2 * wall
            area  = math.pi * (outer ** 2 - inner ** 2) / 4

        total_mm = sum(i['length'] * i['count'] for i in self.volume_data)
        self.volume_length_mm = int(round(total_mm))
        total_m = total_mm / 1000
        weight_kg = area * total_m * density
        self.volume_weight_kg = int(round(weight_kg))
        weight_t = weight_kg / 1000
        self.lbl_weight.setText(f"Вес партии - {weight_t:.3f} т.")

    def data(self):
        return {
            'arrival_date': self.date_arrival.date().toString("yyyy-MM-dd"),
            'supplier_id': self.cmb_supplier.currentData(),
            'order_num': self.cmb_custom_order.currentText() if self.chk_custom.isChecked()
                         else self.le_order.text(),
            'grade_id': self.cmb_grade.currentData()[0],
            'rolling_type_id': self.cmb_type.currentData(),
            'size': (f"{self.le_dim1.text()}×{self.le_dim2.text()}"
                     if self.cmb_type.currentText() in ("Лист", "Плита", "Труба")
                     else self.le_dim1.text()),
            'cert_num': self.le_cert.text(),
            'cert_date': self.date_cert.date().toString("yyyy-MM-dd"),
            'heat_num': self.le_heat.text(),
            'batch': self.le_batch.text(),
            'volume_length_mm': getattr(self, 'volume_length_mm', 0),
            'volume_weight_kg': getattr(self, 'volume_weight_kg', 0)
        }

    def _on_accept(self):
        if not self.cmb_supplier.currentData():
            QMessageBox.warning(self, "Ошибка", "Нужно выбрать поставщика.")
            return
        if (not self.le_order.hasAcceptableInput()
                and not self.chk_custom.isChecked()):
            QMessageBox.warning(self, "Ошибка",
                                "Номер заказа должен быть формата 2025/003.")
            return
        self.accept()

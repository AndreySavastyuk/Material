# gui/lab/specimen_catalog.py

import os
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QFileDialog, QHBoxLayout, QMessageBox, QLabel,
    QLineEdit, QFormLayout, QDialogButtonBox, QComboBox
)
from PyQt5.QtCore import Qt
from db.database import Database


class SpecimenCatalogDialog(QDialog):
    """Справочник образцов для испытаний."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.db = Database(); self.db.connect()
        self.setWindowTitle("Справочник образцов")
        self.resize(800, 400)
        self._build_ui()
        self._load()

    def _build_ui(self):
        v = QVBoxLayout(self)
        # Таблица
        self.tbl = QTableWidget(0, 8)
        self.tbl.setHorizontalHeaderLabels([
            "ID", "Название", "Тип испытания",
            "Длина (мм)", "Стандарт (ГОСТ)",
            "Номер образца", "Тип образца", "Чертёж PDF"
        ])
        self.tbl.hideColumn(0)
        self.tbl.setEditTriggers(self.tbl.NoEditTriggers)
        v.addWidget(self.tbl)

        # Кнопки
        h = QHBoxLayout()
        btn_add  = QPushButton("Добавить")
        btn_edit = QPushButton("Изменить")
        btn_del  = QPushButton("Удалить")
        h.addWidget(btn_add); h.addWidget(btn_edit); h.addWidget(btn_del)
        h.addStretch()
        v.addLayout(h)

        btn_add.clicked.connect(self._add)
        btn_edit.clicked.connect(self._edit)
        btn_del.clicked.connect(self._delete)

    def _load(self):
        rows = self.db.conn.execute(
            "SELECT id, name, test_type, length_mm, standard, sample_number, specimen_type, pdf_path "
            "FROM Specimens"
        ).fetchall()
        self.tbl.setRowCount(len(rows))
        for i, r in enumerate(rows):
            self.tbl.setItem(i, 0, QTableWidgetItem(str(r["id"])))
            self.tbl.setItem(i, 1, QTableWidgetItem(r["name"]))
            self.tbl.setItem(i, 2, QTableWidgetItem(r["test_type"]))
            self.tbl.setItem(i, 3, QTableWidgetItem(str(r["length_mm"])))
            self.tbl.setItem(i, 4, QTableWidgetItem(r["standard"]))
            self.tbl.setItem(i, 5, QTableWidgetItem(r["sample_number"]))
            self.tbl.setItem(i, 6, QTableWidgetItem(r["specimen_type"]))
            fname = os.path.basename(r["pdf_path"])
            self.tbl.setItem(i, 7, QTableWidgetItem(fname))
        self.tbl.resizeColumnsToContents()

    def _add(self):
        dlg = _SpecimenEditor(self, None)
        if dlg.exec_() == QDialog.Accepted:
            data = dlg.result
            self.db.conn.execute(
                """INSERT INTO Specimens
                   (name,test_type,length_mm,standard,sample_number,specimen_type,pdf_path)
                   VALUES(?,?,?,?,?,?,?)""",
                data
            )
            self.db.conn.commit()
            self._load()

    def _edit(self):
        row = self.tbl.currentRow()
        if row < 0:
            return
        sid = int(self.tbl.item(row, 0).text())
        rec = self.db.conn.execute(
            "SELECT name,test_type,length_mm,standard,sample_number,specimen_type,pdf_path "
            "FROM Specimens WHERE id=?", (sid,)
        ).fetchone()
        dlg = _SpecimenEditor(self, rec)
        if dlg.exec_() == QDialog.Accepted:
            data = dlg.result
            self.db.conn.execute(
                """UPDATE Specimens SET
                   name=?, test_type=?, length_mm=?, standard=?,
                   sample_number=?, specimen_type=?, pdf_path=?
                   WHERE id=?""",
                (*data, sid)
            )
            self.db.conn.commit()
            self._load()

    def _delete(self):
        row = self.tbl.currentRow()
        if row < 0:
            return
        sid = int(self.tbl.item(row, 0).text())
        if QMessageBox.question(self, "Удалить", "Удалить образец?") != QMessageBox.Yes:
            return
        self.db.conn.execute("DELETE FROM Specimens WHERE id=?", (sid,))
        self.db.conn.commit()
        self._load()


class _SpecimenEditor(QDialog):
    """Диалог добавления/редактирования одного образца."""
    def __init__(self, parent, record):
        super().__init__(parent)
        self.setWindowTitle("Образец")
        self.result = None

        v = QVBoxLayout(self)
        form = QFormLayout()

        self.le_name         = QLineEdit(record["name"] if record else "")
        self.cmb_test_type   = QComboBox()
        self.cmb_test_type.addItems(["Растяжение", "Ударный изгиб"])
        if record:
            idx = self.cmb_test_type.findText(record["test_type"])
            if idx >= 0: self.cmb_test_type.setCurrentIndex(idx)

        self.le_length       = QLineEdit(str(record["length_mm"]) if record else "")
        self.le_standard     = QLineEdit(record["standard"] if record else "")
        self.le_sample_num   = QLineEdit(record["sample_number"] if record else "")
        self.le_spec_type    = QLineEdit(record["specimen_type"] if record else "")

        self.le_path         = QLineEdit(record["pdf_path"] if record else "")
        btn_browse = QPushButton("…")
        btn_browse.clicked.connect(self._browse)
        h_path = QHBoxLayout(); h_path.addWidget(self.le_path); h_path.addWidget(btn_browse)

        form.addRow("Название:",       self.le_name)
        form.addRow("Тип испытания:",  self.cmb_test_type)
        form.addRow("Длина (мм):",     self.le_length)
        form.addRow("Стандарт (ГОСТ):",self.le_standard)
        form.addRow("Номер образца:",  self.le_sample_num)
        form.addRow("Тип образца:",    self.le_spec_type)
        form.addRow("PDF чертёж:",      h_path)

        v.addLayout(form)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)

    def _browse(self):
        f, _ = QFileDialog.getOpenFileName(self, "Выбрать PDF", "", "PDF Files (*.pdf)")
        if f:
            self.le_path.setText(f)

    def accept(self):
        name       = self.le_name.text().strip()
        test_type  = self.cmb_test_type.currentText()
        try:
            length = float(self.le_length.text())
        except:
            QMessageBox.warning(self, "Ошибка", "Некорректная длина")
            return
        standard   = self.le_standard.text().strip()
        sample_num = self.le_sample_num.text().strip()
        spec_type  = self.le_spec_type.text().strip()
        path       = self.le_path.text().strip()

        if not all([name, standard, sample_num, spec_type, path]):
            QMessageBox.warning(self, "Ошибка", "Заполните все поля")
            return
        if not os.path.isfile(path):
            QMessageBox.warning(self, "Ошибка", "PDF файл не найден")
            return

        self.result = (
            name, test_type, length,
            standard, sample_num, spec_type, path
        )
        super().accept()

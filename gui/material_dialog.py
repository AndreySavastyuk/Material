import os
from PyQt5.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QComboBox, QDialogButtonBox,
    QListWidget, QPushButton, QFileDialog, QMessageBox, QInputDialog
)
from db.database import Database

class MaterialDialog(QDialog):
    STATUSES = [
        'Новый', 'На проверке ОТК', 'ОТК одобрено', 'ОТК требует испытания',
        'На испытании ЦЗЛ', 'Одобрен', 'Забракован'
    ]

    def __init__(self, parent=None, material=None):
        super().__init__(parent)
        self.material = material
        self.db = Database()
        self.db.connect()
        self.setWindowTitle('Детали материала')
        self._build()
        self._load()

    def _build(self):
        self.ext_id = QLineEdit()
        self.name = QLineEdit()
        self.supplier = QLineEdit()
        self.quantity = QLineEdit()
        self.unit = QLineEdit()
        self.arrival = QLineEdit()
        self.status = QComboBox()
        self.status.addItems(self.STATUSES)

        self.doc_list = QListWidget()
        self.btn_add_doc = QPushButton('Добавить документ')
        self.btn_add_doc.clicked.connect(self._add_doc)

        form = QFormLayout()
        form.addRow('ID партии', self.ext_id)
        form.addRow('Наименование', self.name)
        form.addRow('Поставщик', self.supplier)
        form.addRow('Кол-во', self.quantity)
        form.addRow('Ед.', self.unit)
        form.addRow('Дата', self.arrival)
        form.addRow('Статус', self.status)
        form.addRow('Документы', self.doc_list)
        form.addRow(self.btn_add_doc)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        self.setLayout(form)

    def _load(self):
        m = self.material
        self.ext_id.setText(m['ext_id'] or '')
        self.name.setText(m['name'] or '')
        self.supplier.setText(m['supplier'] or '')
        self.quantity.setText(str(m['quantity']))
        self.unit.setText(m['unit'] or '')
        self.arrival.setText(m['arrival_date'] or '')
        idx = self.STATUSES.index(m['status']) if m['status'] in self.STATUSES else 0
        self.status.setCurrentIndex(idx)
        self.doc_list.clear()
        docs = self.db.get_documents(m['id'])
        for d in docs:
            fname = os.path.basename(d['file_path'])
            self.doc_list.addItem(f"{d['doc_type']}: {fname}")

    def _add_doc(self):
        m = self.material
        fpath, _ = QFileDialog.getOpenFileName(self, 'Выберите файл')
        if not fpath:
            return
        doc_type, ok = QInputDialog.getText(self, 'Тип документа', 'Введите тип:')
        if not ok or not doc_type.strip():
            return
        try:
            self.db.add_document(m['id'], doc_type.strip(), fpath, self.parent().user['login'])
            QMessageBox.information(self, 'Готово', 'Документ добавлен')
            fname = os.path.basename(fpath)
            self.doc_list.addItem(f"{doc_type.strip()}: {fname}")
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', str(e))

    def data(self):
        return {
            'ext_id': self.ext_id.text().strip(),
            'name': self.name.text().strip(),
            'supplier': self.supplier.text().strip(),
            'quantity': float(self.quantity.text()),
            'unit': self.unit.text().strip(),
            'arrival_date': self.arrival.text().strip(),
            'status': self.status.currentText()
        }

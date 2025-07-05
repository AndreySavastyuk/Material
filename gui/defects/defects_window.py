from PyQt5 import QtWidgets, QtGui
from db.database import Database
from db.models import Defect

class DefectsWindow(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Журнал дефектов")
        self.resize(800, 500)

        btn_add     = QtWidgets.QPushButton("Добавить")
        btn_delete  = QtWidgets.QPushButton("Удалить")
        btn_refresh = QtWidgets.QPushButton("Обновить")

        btn_add.clicked.connect(self.add_defect)
        btn_delete.clicked.connect(self.delete_defect)
        btn_refresh.clicked.connect(self.load_defects)

        self.table = QtWidgets.QTableView()
        self.model = QtGui.QStandardItemModel(0, 6, self)
        self.model.setHorizontalHeaderLabels([
            "ID", "Марка материала", "Тип дефекта", "Описание", "Сообщил", "Дата"
        ])
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)

        hl = QtWidgets.QHBoxLayout()
        hl.addWidget(btn_add)
        hl.addWidget(btn_delete)
        hl.addStretch()
        hl.addWidget(btn_refresh)

        vl = QtWidgets.QVBoxLayout(self)
        vl.addLayout(hl)
        vl.addWidget(self.table)

        self.db = Database()
        self.db.connect()
        self.load_defects()

    def load_defects(self):
        self.model.removeRows(0, self.model.rowCount())
        for d in Defect.list_all(self.db.conn):
            items = [
                QtGui.QStandardItem(str(d['id'])),
                QtGui.QStandardItem(d['material_grade']),
                QtGui.QStandardItem(d['defect_type']),
                QtGui.QStandardItem(d['description']),
                QtGui.QStandardItem(d['reported_by']),
                QtGui.QStandardItem(d['timestamp'])
            ]
            self.model.appendRow(items)

    def add_defect(self):
        dlg = AddDefectDialog(self.db.conn, parent=self)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            self.load_defects()

    def delete_defect(self):
        idxs = self.table.selectionModel().selectedRows()
        if not idxs:
            return
        defect_id = int(self.model.item(idxs[0].row(), 0).text())
        Defect.soft_delete(self.db.conn, defect_id)
        self.load_defects()

class AddDefectDialog(QtWidgets.QDialog):
    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.setWindowTitle("Новый дефект")
        self.resize(400, 200)

        self.cmb_material = QtWidgets.QComboBox()
        # Получаем список материалов с брендом через Grades
        for mid, grade in conn.execute(
            "SELECT m.id, g.grade FROM Materials m JOIN Grades g ON m.grade_id = g.id"
        ):
            self.cmb_material.addItem(grade, mid)

        self.cmb_type = QtWidgets.QComboBox()
        self.cmb_type.addItems(["Внешний дефект", "Внутренний дефект", "Износ", "Прочее"])

        self.txt_desc = QtWidgets.QPlainTextEdit()
        self.txt_by   = QtWidgets.QLineEdit()

        btn_ok     = QtWidgets.QPushButton("Добавить")
        btn_cancel = QtWidgets.QPushButton("Отмена")
        btn_ok.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)

        form = QtWidgets.QFormLayout()
        form.addRow("Материал:", self.cmb_material)
        form.addRow("Тип дефекта:", self.cmb_type)
        form.addRow("Описание:", self.txt_desc)
        form.addRow("Сообщил:", self.txt_by)

        hl = QtWidgets.QHBoxLayout()
        hl.addStretch()
        hl.addWidget(btn_ok)
        hl.addWidget(btn_cancel)

        vl = QtWidgets.QVBoxLayout(self)
        vl.addLayout(form)
        vl.addLayout(hl)

    def accept(self):
        data = {
            'material_id': self.cmb_material.currentData(),
            'defect_type': self.cmb_type.currentText(),
            'description': self.txt_desc.toPlainText(),
            'reported_by': self.txt_by.text()
        }
        Defect.create(self.conn, data)
        super().accept()
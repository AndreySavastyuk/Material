# gui/admin/test_scenarios.py — CRUD-интерфейс для справочника "Сценарии испытаний"
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QTableWidget, QTableWidgetItem, QPushButton, QMessageBox,
    QFormLayout, QLineEdit, QDialogButtonBox, QCheckBox, QWidget
)
from PyQt5.QtCore import Qt
import json
from db.database import Database

# Типовые испытания
TESTS_LIST = [
    'Растяжение', 'Удар', 'Твердость', 'Химический состав',
    'Стеллоскопия', 'Макроструктура', 'Неметаллические включения'
]

class TestScenariosAdmin(QDialog):
    """
    Диалоговое окно для управления сценариями испытаний:
    - выбор марки материала
    - список сценариев для выбранной марки
    - добавление, редактирование, удаление сценариев
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Справочник: Сценарии испытаний')
        self.db = Database()
        self.db.connect()
        self._build_ui()
        self._load_materials()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        # Выбор марки материала
        hbox = QHBoxLayout()
        hbox.addWidget(QLabel('Марка материала:'))
        self.cmb_material = QComboBox()
        self.cmb_material.currentIndexChanged.connect(self._load_scenarios)
        hbox.addWidget(self.cmb_material)
        main_layout.addLayout(hbox)
        # Таблица сценариев
        self.tbl = QTableWidget(0, 2)
        self.tbl.setHorizontalHeaderLabels(['Название сценария', 'Перечень испытаний'])
        self.tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl.setSelectionBehavior(QTableWidget.SelectRows)
        main_layout.addWidget(self.tbl)
        # Кнопки Add/Edit/Delete
        btn_layout = QHBoxLayout()
        btn_add = QPushButton('Добавить')
        btn_add.clicked.connect(self._add_scenario)
        btn_layout.addWidget(btn_add)
        btn_edit = QPushButton('Изменить')
        btn_edit.clicked.connect(self._edit_scenario)
        btn_layout.addWidget(btn_edit)
        btn_del = QPushButton('Удалить')
        btn_del.clicked.connect(self._delete_scenario)
        btn_layout.addWidget(btn_del)
        main_layout.addLayout(btn_layout)
        # Кнопка закрытия
        btn_close = QPushButton('Закрыть')
        btn_close.clicked.connect(self.accept)
        main_layout.addWidget(btn_close)

    def _load_materials(self):
        # Получаем список марок из справочника Grades
        cur = self.db.conn.cursor()
        cur.execute('SELECT id, grade FROM Grades ORDER BY grade')
        self.materials = cur.fetchall()
        self.cmb_material.clear()
        for m in self.materials:
            self.cmb_material.addItem(m['grade'], m['id'])
        # Загрузить сценарии для первой марки
        if self.materials:
            self._load_scenarios(0)

    def _load_scenarios(self, index):
        # Загружаем сценарии для выбранного material_id
        material_id = self.cmb_material.itemData(index)
        cur = self.db.conn.cursor()
        cur.execute(
            'SELECT id, name, tests_json FROM test_scenarios WHERE material_id=? ORDER BY name',
            (material_id,)
        )
        rows = cur.fetchall()
        self.scenarios = rows
        self.tbl.setRowCount(len(rows))
        for i, row in enumerate(rows):
            name = row['name']
            tests = json.loads(row['tests_json'])
            item_name = QTableWidgetItem(name)
            item_tests = QTableWidgetItem(', '.join(tests))
            item_name.setTextAlignment(Qt.AlignCenter)
            item_tests.setTextAlignment(Qt.AlignCenter)
            self.tbl.setItem(i, 0, item_name)
            self.tbl.setItem(i, 1, item_tests)
        self.tbl.resizeColumnsToContents()

    def _add_scenario(self):
        # Диалог создания сценария
        dlg = QDialog(self)
        dlg.setWindowTitle('Добавить сценарий')
        form = QFormLayout(dlg)
        # Название
        edt_name = QLineEdit()
        form.addRow('Название:', edt_name)
        # Список чекбоксов
        cbs = []
        for t in TESTS_LIST:
            cb = QCheckBox(t)
            form.addRow(cb)
            cbs.append(cb)
        # Кнопки OK/Cancel
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        form.addRow(bb)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        if dlg.exec_() == QDialog.Accepted:
            name = edt_name.text().strip()
            tests = [cb.text() for cb in cbs if cb.isChecked()]
            if not name or not tests:
                QMessageBox.warning(self, 'Внимание', 'Введите название и выберите хотя бы одно испытание')
                return
            material_id = self.cmb_material.currentData()
            # Сохраняем
            self.db.conn.execute(
                'INSERT INTO test_scenarios(material_id,name,tests_json) VALUES (?,?,?)',
                (material_id, name, json.dumps(tests, ensure_ascii=False))
            )
            self.db.conn.commit()
            self._load_scenarios(self.cmb_material.currentIndex())

    def _edit_scenario(self):
        row = self.tbl.currentRow()
        if row < 0:
            QMessageBox.information(self, 'Инфо', 'Выберите сценарий для редактирования')
            return
        scen = self.scenarios[row]
        dlg = QDialog(self)
        dlg.setWindowTitle('Редактировать сценарий')
        form = QFormLayout(dlg)
        edt_name = QLineEdit(scen['name'])
        form.addRow('Название:', edt_name)
        cbs = {}
        tests = json.loads(scen['tests_json'])
        for t in TESTS_LIST:
            cb = QCheckBox(t)
            cb.setChecked(t in tests)
            form.addRow(cb)
            cbs[t] = cb
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        form.addRow(bb)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        if dlg.exec_() == QDialog.Accepted:
            name = edt_name.text().strip()
            sel = [t for t, cb in cbs.items() if cb.isChecked()]
            if not name or not sel:
                QMessageBox.warning(self, 'Внимание', 'Введите название и выберите хотя бы одно испытание')
                return
            # Обновляем
            self.db.conn.execute(
                'UPDATE test_scenarios SET name=?, tests_json=? WHERE id=?',
                (name, json.dumps(sel, ensure_ascii=False), scen['id'])
            )
            self.db.conn.commit()
            self._load_scenarios(self.cmb_material.currentIndex())

    def _delete_scenario(self):
        row = self.tbl.currentRow()
        if row < 0:
            QMessageBox.information(self, 'Инфо', 'Выберите сценарий для удаления')
            return
        scen = self.scenarios[row]
        # Проверка на использование в lab_requests
        cur = self.db.conn.cursor()
        cur.execute('SELECT COUNT(*) FROM lab_requests WHERE material_id=?', (scen['material_id'],))
        if cur.fetchone()[0] > 0:
            QMessageBox.warning(self, 'Ошибка', 'Нельзя удалить сценарий: по этой марке уже создавались заявки')
            return
        if QMessageBox.question(self, 'Подтверждение',
                                f"Удалить сценарий '{scen['name']}'?",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.db.conn.execute('DELETE FROM test_scenarios WHERE id=?', (scen['id'],))
            self.db.conn.commit()
            self._load_scenarios(self.cmb_material.currentIndex())

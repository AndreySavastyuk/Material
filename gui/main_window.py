from PyQt5.QtWidgets import (
    QMainWindow, QTableWidget, QTableWidgetItem,
    QPushButton, QVBoxLayout, QWidget, QMessageBox,
    QDesktopWidget, QMenu, QStyle, QDateEdit,
    QComboBox, QLineEdit, QHBoxLayout, QDialog
)
from PyQt5.QtCore import Qt, QPoint, QTimer, QDate
from PyQt5.QtGui import QColor

from db.database import Database
from gui.dialogs import AddMaterialDialog
from gui.admin.suppliers import SuppliersAdmin
from gui.admin.grades import GradesAdmin
from gui.admin.rolling_types import RollingTypesAdmin
from gui.admin.test_scenarios import TestScenariosAdmin
from gui.admin.moderation import ModerationDialog
from gui.otk.otk_window import OtkWindow
from gui.lab.lab_window import LabWindow
from gui.audit.audit_window import AuditWindow
from gui.settings.settings_window import SettingsWindow
from gui.defects.defects_window import DefectsWindow
from logger import log_event

class MainWindow(QMainWindow):
    def __init__(self, user):
        super().__init__()
        self.user = user
        self.db = Database()
        self.db.connect()
        self.db.docs_root = r"D:\mes"

        self.setWindowTitle('Система контроля материалов')
        geom = QDesktopWidget().screenGeometry()
        self.resize(int(geom.width() * 0.8), int(geom.height() * 0.7))

        self._create_menus()
        self._build()
        self._load()

        self._last_count = len(self.db.get_materials())
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._on_poll)
        self._refresh_timer.start(5000)

    def _create_menus(self):
        menubar = self.menuBar()
        settings_menu = menubar.addMenu('Настройки')
        settings_menu.addAction('Настройки приложения', lambda: SettingsWindow(self).exec_())
        if self.user.get('role') == 'Администратор':
            admin_menu = menubar.addMenu('Справочники')
            admin_menu.addAction('Поставщики', lambda: SuppliersAdmin(self).exec_())
            admin_menu.addAction('Марки', lambda: GradesAdmin(self).exec_())
            admin_menu.addAction('Виды проката', lambda: RollingTypesAdmin(self).exec_())
            admin_menu.addAction('Модерация удаления', lambda: ModerationDialog(self).exec_())
            admin_menu.addAction('Журнал действий', lambda: AuditWindow(self).exec_())
            admin_menu.addAction('Сценарии испытаний', lambda: TestScenariosAdmin(self).exec_())
        modules_menu = menubar.addMenu('Модули')
        modules_menu.addAction('ОТК', lambda: self._open_otk())
        modules_menu.addAction('Лаборатория', lambda: self._open_lab())
        modules_menu.addAction('Журнал дефектов', lambda: self.open_defects())

    def _build(self):
        central = QWidget()
        layout = QVBoxLayout(central)

        # Фильтр поиска
        flt_layout = QHBoxLayout()
        self.le_filter = QLineEdit()
        self.le_filter.setPlaceholderText('Введите 2+ символа для поиска…')
        flt_layout.addWidget(self.le_filter)
        layout.addLayout(flt_layout)
        self.le_filter.textChanged.connect(self._on_search_text_changed)

        # Действия
        btn_add = QPushButton('Добавить материал')
        btn_add.clicked.connect(self._add)
        btn_refresh = QPushButton('Обновить')
        btn_refresh.clicked.connect(self._manual_refresh)
        btn_defects = QPushButton('Журнал дефектов')
        btn_defects.clicked.connect(self.open_defects)
        layout.addWidget(btn_add)
        layout.addWidget(btn_refresh)
        layout.addWidget(btn_defects)

        # Таблица
        self.tbl = QTableWidget()
        layout.addWidget(self.tbl)
        self.tbl.setColumnCount(14)
        self.tbl.setHorizontalHeaderLabels([
            'Дата прихода', 'Поставщик', 'Номер заказа', 'Марка',
            'Вид проката', 'Размер', 'Сертификат №', 'Дата серт.',
            'Партия', 'Плавка', 'Длина (мм)', 'Вес (кг)',
            'Заметки ОТК', 'ППСД'
        ])
        self.tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tbl.customContextMenuRequested.connect(self._show_context_menu)

        self.setCentralWidget(central)

    def _load(self, rows=None):
        rows = rows if rows is not None else self.db.get_materials()
        self.tbl.setRowCount(len(rows))
        for i, r in enumerate(rows):
            # формат дат
            arr_date = QDate.fromString(r['arrival_date'], 'yyyy-MM-dd').toString('dd.MM.yyyy')
            cert_date = QDate.fromString(r['cert_date'], 'yyyy-MM-dd').toString('dd.MM.yyyy')
            vals = [
                arr_date, r['supplier'], r['order_num'], r['grade'],
                r['rolling_type'], r['size'], r['cert_num'], cert_date,
                r['batch'], r['heat_num'], f"{r['volume_length_mm']:.0f}",
                f"{r['volume_weight_kg']:.0f}", r['otk_remarks'] or '',
                'Да' if r['needs_lab'] else ''
            ]
            for j, v in enumerate(vals):
                item = QTableWidgetItem(str(v))
                item.setTextAlignment(Qt.AlignCenter)
                self.tbl.setItem(i, j, item)
            if r['to_delete']:
                for col in range(self.tbl.columnCount()):
                    itm = self.tbl.item(i, col)
                    itm.setBackground(QColor(200,200,200,128))
                    itm.setForeground(QColor(0,0,0,153))
                self.tbl.item(i, 0).setIcon(self.style().standardIcon(QStyle.SP_TrashIcon))
        self.tbl.resizeColumnsToContents()

    def _on_search_text_changed(self, text):
        txt = text.strip().lower()
        if len(txt) < 2:
            self._load()
            return
        filtered = []
        for r in self.db.get_materials():
            hay = ' '.join([
                str(r['supplier']), str(r['cert_num']),
                str(r['heat_num']), str(r['batch']),
                str(r['grade']), str(r['rolling_type']),
                str(r['order_num']), str(r['size'])
            ]).lower()
            if txt in hay:
                filtered.append(r)
        self._load(filtered)

    def _show_context_menu(self, pos: QPoint):
        row = self.tbl.rowAt(pos.y())
        if row < 0:
            return
        mat = self.db.get_materials()[row]
        menu = QMenu(self)
        text = 'Снять метку' if mat['to_delete'] else 'Пометить на удаление'
        act = menu.addAction(text)
        if menu.exec_(self.tbl.viewport().mapToGlobal(pos)) == act:
            mid = mat['id']
            if mat['to_delete']:
                self.db.unmark_material(mid)
                log_event(self.user, 'unmark', mid, 'Снята метка')
            else:
                self.db.mark_material_for_deletion(mid)
                log_event(self.user, 'mark', mid, 'Помечена удаление')
            self._load()

    def _add(self):
        dlg = AddMaterialDialog(self)
        dlg.setMinimumSize(800, 600)
        if dlg.exec_() == QDialog.Accepted:
            data = dlg.data()
            mid = self.db.add_material(**data)
            log_event(self.user, 'add_material', mid, str(data))
            QMessageBox.information(self, 'Готово', 'Материал добавлен')
            self._load()

    def _manual_refresh(self):
        self._load()

    def _on_poll(self):
        curr = len(self.db.get_materials())
        if curr != self._last_count:
            # подсветить кнопку Обновить можно здесь
            pass
        self._last_count = curr

    def _open_otk(self):
        OtkWindow(self).exec_()

    def _open_lab(self):
        LabWindow(self).show()

    def open_defects(self):
        DefectsWindow(self).exec_()

    def closeEvent(self, event):
        self.db.close()
        super().closeEvent(event)

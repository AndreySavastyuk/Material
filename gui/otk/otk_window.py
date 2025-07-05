# gui/otk/otk_window.py

import os
import datetime
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QFileDialog, QMenu, QMessageBox,
    QCheckBox, QDialogButtonBox, QFormLayout
)
from PyQt5.QtCore import Qt, QPoint, QDateTime
from db.database import Database
from gui.utils.certificate_saver import save_certificate


class OtkWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.user = parent.user
        self.db = Database()
        self.db.connect()

        # путь к сертификатам из конфига или по умолчанию
        try:
            from config import load_config
            cfg = load_config()
            self.docs_root = cfg.get('DOCUMENTS', {}).get('root_path', r"D:\mes")
        except:
            self.docs_root = r"D:\mes"

        self.setWindowTitle('Модуль ОТК')
        self.resize(800, 600)

        self._build()
        self._load()

    def _build(self):
        layout = QVBoxLayout(self)

        self.table = QTableWidget(0, 14)
        headers = [
            'ID', 'Дата прихода', 'Поставщик', 'Номер заказа', 'Марка',
            'Вид проката', 'Размер', 'Сертификат №', 'Дата серт.',
            'Партия', 'Плавка', 'Замечания ОТК', 'PDF сертификат', 'ППСД'
        ]
        self.table.setHorizontalHeaderLabels(headers)
        self.table.hideColumn(0)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_menu)
        self.table.cellDoubleClicked.connect(self._on_row_double_clicked)
        layout.addWidget(self.table)

        btn_close = QPushButton('Закрыть')
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)

    def _load(self):
        rows = [dict(r) for r in self.db.get_materials()]
        self.table.setRowCount(len(rows))

        for i, r in enumerate(rows):
            mat_id   = r['id']
            path     = r.get('cert_scan_path') or ''
            saved_ts = r.get('cert_saved_at')   or ''

            if not path:
                status = 'Сертификат не загружен'
            else:
                # форматируем дату из cert_saved_at
                try:
                    dt = QDateTime.fromString(saved_ts, 'yyyy-MM-dd HH:mm:ss')
                    date_str = dt.toString('dd.MM.yyyy') if dt.isValid() else ''
                except:
                    date_str = ''
                status = f'Сертификат загружен {date_str}'

            vals = [
                mat_id,
                r['arrival_date'], r['supplier'], r['order_num'],
                r['grade'], r['rolling_type'], r['size'], r['cert_num'],
                r['cert_date'], r['batch'], r['heat_num'],
                r['otk_remarks'] or '',
                status,
                'Да' if r['needs_lab'] else 'Нет'
            ]
            for j, v in enumerate(vals):
                item = QTableWidgetItem(str(v))
                item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(i, j, item)

        self.table.resizeColumnsToContents()

    def _on_row_double_clicked(self, row: int, col: int):
        """Двойной клик: открыть файл, если есть; иначе – загрузить сертификат."""
        if col != 12:
            return

        mat_id = int(self.table.item(row, 0).text())
        path   = self.db.conn.execute(
            "SELECT cert_scan_path FROM Materials WHERE id=?", (mat_id,)
        ).fetchone()[0] or ''

        if path:
            try:
                os.startfile(path)
            except Exception as e:
                QMessageBox.critical(self, 'Ошибка открытия', str(e))
        else:
            # загрузить первый раз
            self._load_certificate(mat_id)

    def _show_menu(self, pos: QPoint):
        row = self.table.rowAt(pos.y())
        if row < 0:
            return
        mat_id = int(self.table.item(row, 0).text())
        menu = QMenu(self)
        menu.addAction(
            'Загрузить/Заменить сертификат',
            lambda: self._guard(self._load_certificate, mat_id)
        )
        menu.addAction(
            'Добавить замечания',
            lambda: self._guard(self._add_remarks, mat_id, row)
        )
        menu.addAction(
            'Отметить ППСД',
            lambda: self._guard(self._toggle_lab, mat_id, row)
        )
        menu.exec_(self.table.viewport().mapToGlobal(pos))

    def _guard(self, func, mat_id: int, row: int = None):
        """Проверяем блокировку, вызываем func с нужными аргументами и перезагружаем."""
        locked, locker = self.db.is_locked(mat_id)
        if locked and locker != self.user['login']:
            QMessageBox.warning(self, 'Заблокировано', f'Запись редактирует {locker}.')
            return
        if not self.db.acquire_lock(mat_id, self.user['login']):
            QMessageBox.warning(self, 'Ошибка', 'Не удалось получить блокировку.')
            return

        try:
            # если func принимает только mat_id
            if row is None:
                func(mat_id)
            else:
                func(row, mat_id)
        finally:
            self.db.release_lock(mat_id, self.user['login'])
            self._load()

    def _load_certificate(self, mat_id: int):
        """Выбрать PDF и сохранить/заменить сертификат."""
        fpath, _ = QFileDialog.getOpenFileName(
            self, 'Выбрать PDF сертификат', self.docs_root,
            'PDF Files (*.pdf)'
        )
        if not fpath:
            return
        try:
            msg = save_certificate(self.db, mat_id, fpath, self.docs_root)
            QMessageBox.information(self, 'Результат', msg)
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', str(e))

    def _add_remarks(self, row: int, mat_id: int):
        dlg = QDialog(self)
        dlg.setWindowTitle('Замечания ОТК')
        form = QFormLayout(dlg)
        cbs = [QCheckBox(txt) for txt in (
            'Не читаем', 'Перекуп', 'Размер не соответствует', 'Ошибка в сертификате'
        )]
        for cb in cbs:
            form.addRow(cb)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        form.addRow(bb)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        if dlg.exec_() == QDialog.Accepted:
            remarks = ', '.join(cb.text() for cb in cbs if cb.isChecked())
            try:
                self.db.conn.execute(
                    'UPDATE Materials SET otk_remarks=? WHERE id=?',
                    (remarks, mat_id)
                )
                self.db.conn.commit()
            except Exception as e:
                QMessageBox.critical(self, 'Ошибка', str(e))

    def _toggle_lab(self, row: int, mat_id: int):
        current = self.table.item(row, 13).text() == 'Да'
        new_flag = 0 if current else 1
        try:
            self.db.conn.execute(
                'UPDATE Materials SET needs_lab=? WHERE id=?',
                (new_flag, mat_id)
            )
            # Если установили флаг, создаём новую заявку в lab_requests
            if new_flag == 1:
                cur = self.db.conn.cursor()
                cur.execute("SELECT COALESCE(MAX(id),0)+1 FROM lab_requests")
                next_id = cur.fetchone()[0]
                request_number = f"{next_id:05d}"
                creation_date = datetime.date.today().isoformat()
                cur.execute(
                '''
                INSERT INTO lab_requests(
                creation_date, request_number, material_id,
                tests_json, results_json, status, archived
                )
                VALUES (?, ?, ?, '[]', '[]', 'Не отработана', 0)
                ''',
                (creation_date, request_number, mat_id))
            self.db.conn.commit()
        except Exception as e:
                    QMessageBox.critical(self, 'Ошибка', str(e))

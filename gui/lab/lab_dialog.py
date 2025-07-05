# gui/lab/lab_dialog.py — диалог лаборатории ЦЗЛ для формирования заявки на пробы
import os
import datetime
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QCheckBox,
    QSpinBox, QFormLayout, QDialogButtonBox, QMessageBox
)
from fpdf import FPDF
from logger import log_event
from db.database import Database

class LabDialog(QDialog):
    """
    Диалог инженера ЦЗЛ:
    - Отображает информацию о материале
    - Список чекбоксов для выбранных испытаний
    - Ввод количества образцов
    - Генерация PDF заявки на пробы
    """
    TESTS = [
        'Механические испытания',
        'Химический состав',
        'Микроструктурный анализ',
        'Ударная вязкость'
    ]

    def __init__(self, parent=None, material_id=None):
        super().__init__(parent)
        self.material_id = material_id
        self.db = Database(); self.db.connect()
        # Загрузка данных по материалу
        cur = self.db.conn.cursor()
        cur.execute(
            'SELECT ext_id, grade, size FROM Materials m '
            'JOIN Grades g ON m.grade_id=g.id '
            'WHERE m.id=?', (material_id,)
        )
        row = cur.fetchone()
        self.party = row['ext_id']
        self.grade = row['grade']
        self.size = row['size']
        self.pdf_path = ''

        self.setWindowTitle('ППСД — Заявка на пробы')
        self._build()

    def _build(self):
        layout = QVBoxLayout()
        # Информация о материале
        layout.addWidget(QLabel(f'Партия: {self.party}'))
        layout.addWidget(QLabel(f'Марка: {self.grade}'))
        layout.addWidget(QLabel(f'Размер: {self.size}'))

        # Чекбоксы тестов
        self.checks = []
        for t in self.TESTS:
            cb = QCheckBox(t)
            layout.addWidget(cb)
            self.checks.append(cb)

        # Количество образцов
        form = QFormLayout()
        self.spin = QSpinBox()
        self.spin.setMinimum(1)
        self.spin.setMaximum(100)
        form.addRow('Количество образцов:', self.spin)
        layout.addLayout(form)

        # ОК/Отмена
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setLayout(layout)

    def _on_save(self):
        # Генерируем PDF
        try:
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font('Arial', 'B', 14)
            pdf.cell(0, 10, 'Заявка на пробы', ln=True, align='C')
            pdf.ln(5)
            pdf.set_font('Arial', size=12)
            pdf.cell(0, 8, f'Партия: {self.party}', ln=True)
            pdf.cell(0, 8, f'Марка: {self.grade}', ln=True)
            pdf.cell(0, 8, f'Размер: {self.size}', ln=True)
            pdf.ln(5)
            pdf.cell(0, 8, 'Испытания:', ln=True)
            for cb in self.checks:
                if cb.isChecked():
                    pdf.cell(0, 8, f'- {cb.text()}', ln=True)
            pdf.ln(5)
            pdf.cell(0, 8, f'Количество образцов: {self.spin.value()}', ln=True)
            # Сохраняем файл
            folder = os.path.join(self.db.docs_root, str(self.material_id))
            os.makedirs(folder, exist_ok=True)
            fname = f"request_{self.material_id}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
            path = os.path.join(folder, fname)
            pdf.output(path)
            self.pdf_path = path
            QMessageBox.information(self, 'Готово', f'Заявка сохранена:\n{path}')
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', f'Не удалось сформировать PDF: {e}')

    def data(self):
        return self.pdf_path
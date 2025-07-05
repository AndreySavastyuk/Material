import os
from PyQt5.QtWidgets import (
    QDialog, QFormLayout, QCheckBox, QTextEdit,
    QPushButton, QHBoxLayout, QDialogButtonBox, QFileDialog, QLabel
)

class OtkDialog(QDialog):
    """
    Диалог ОТК для проверки материала
    """
    def __init__(self, parent=None, material=None):
        super().__init__(parent)
        self.setWindowTitle('Проверка ОТК')
        self.cert_path = ''
        self._build()

    def _build(self):
        form = QFormLayout()
        btn_cert = QPushButton('Загрузить сертификат')
        btn_cert.clicked.connect(self._load_cert)
        self.lbl_cert = QLabel('Файл не выбран')
        h = QHBoxLayout(); h.addWidget(btn_cert); h.addWidget(self.lbl_cert)
        form.addRow('Сертификат:', h)

        self.chk_unreadable = QCheckBox('Сертификат плохого качества')
        self.chk_reseller   = QCheckBox('Перекуп')
        self.chk_size       = QCheckBox('Размер не соответствует ГОСТ')
        self.chk_error      = QCheckBox('Ошибка в сертификате')
        self.chk_lab        = QCheckBox('Нужна проверка сертификатных данных (ППСД)')
        form.addRow(self.chk_unreadable)
        form.addRow(self.chk_reseller)
        form.addRow(self.chk_size)
        form.addRow(self.chk_error)
        form.addRow(self.chk_lab)

        self.txt_comments = QTextEdit()
        form.addRow('Комментарии:', self.txt_comments)

        buttons = QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

        self.setLayout(form)

    def _load_cert(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Выберите сертификат', filter='PDF (*.pdf);;All files (*)')
        if path:
            self.cert_path = path
            self.lbl_cert.setText(os.path.basename(path))

    def data(self):
        remarks = ','.join(f for f,chk in [
            ('нечитаем', self.chk_unreadable.isChecked()),
            ('перекуп', self.chk_reseller.isChecked()),
            ('размер', self.chk_size.isChecked()),
            ('ошибка', self.chk_error.isChecked()),
        ] if chk)
        return {
            'cert_path': self.cert_path,
            'remarks': remarks,
            'needs_lab': self.chk_lab.isChecked()
        }

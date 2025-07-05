# gui/settings/settings_window.py

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLabel, QLineEdit,
    QPushButton, QHBoxLayout, QDialogButtonBox, QMessageBox, QFileDialog
)
from PyQt5.QtCore import Qt
from config import load_config, save_config

class SettingsWindow(QDialog):
    """
    Окно настроек приложения. Позволяет задать путь к БД, корень документов,
    а также настройки Telegram.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.setWindowTitle('Настройки приложения')
        self.resize(500, 300)

        # Загружаем текущие значения из конфига
        self.cfg = load_config()
        self._build_ui()
        self._load_values()

    def _build_ui(self):
        vlay = QVBoxLayout(self)

        form = QFormLayout()

        # Путь к БД
        self.db_path = QLineEdit()
        btn_db = QPushButton('Обзор...')
        btn_db.clicked.connect(self._browse_db)
        h_db = QHBoxLayout(); h_db.addWidget(self.db_path); h_db.addWidget(btn_db)
        form.addRow(QLabel('Путь к БД:'), h_db)

        # Корень документов (сертификаты и пр.)
        self.docs_root = QLineEdit()
        btn_docs = QPushButton('Обзор...')
        btn_docs.clicked.connect(self._browse_docs)
        h_docs = QHBoxLayout(); h_docs.addWidget(self.docs_root); h_docs.addWidget(btn_docs)
        form.addRow(QLabel('Корень документов:'), h_docs)

        # Telegram
        self.bot_token = QLineEdit()
        form.addRow(QLabel('Telegram bot_token:'), self.bot_token)
        self.chat_id   = QLineEdit()
        form.addRow(QLabel('Telegram chat_id:'),   self.chat_id)

        vlay.addLayout(form)

        # Кнопки Сохранить/Отмена
        bb = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel, Qt.Horizontal, self)
        bb.accepted.connect(self._save)
        bb.rejected.connect(self.reject)
        vlay.addWidget(bb)

    def _load_values(self):
        db_sec  = self.cfg.get('DATABASE', {})
        doc_sec = self.cfg.get('DOCUMENTS', {})
        tg_sec  = self.cfg.get('TELEGRAM', {})

        self.db_path.setText(    db_sec.get('path', '') )
        self.docs_root.setText(  doc_sec.get('root_path', '') )
        self.bot_token.setText(  tg_sec.get('bot_token', '') )
        self.chat_id.setText(    tg_sec.get('chat_id', '') )

    def _browse_db(self):
        path, _ = QFileDialog.getOpenFileName(
            self, 'Выберите файл базы данных', self.db_path.text(), 'SQLite DB (*.db *.sqlite)' )
        if path:
            self.db_path.setText(path)

    def _browse_docs(self):
        path = QFileDialog.getExistingDirectory(
            self, 'Выберите корень документов', self.docs_root.text() or '' )
        if path:
            self.docs_root.setText(path)

    def _save(self):
        # Обновляем конфиг
        self.cfg.setdefault('DATABASE', {})['path']        = self.db_path.text().strip()
        self.cfg.setdefault('DOCUMENTS', {})['root_path']  = self.docs_root.text().strip()
        self.cfg.setdefault('TELEGRAM', {})['bot_token']   = self.bot_token.text().strip()
        self.cfg.setdefault('TELEGRAM', {})['chat_id']     = self.chat_id.text().strip()

        # Сохраняем в файл
        try:
            save_config(self.cfg)
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', f'Не удалось сохранить настройки:\n{e}')
            return

        # Обновляем в памяти
        # путь к БД сменить можно только после перезапуска приложения
        if self.parent_window and hasattr(self.parent_window, 'db'):
            self.parent_window.db.docs_root = self.docs_root.text().strip()

        QMessageBox.information(self, 'Успех', 'Настройки сохранены')
        self.accept()
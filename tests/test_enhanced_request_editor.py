"""
Тесты для улучшенного редактора заявок.

Покрывает функциональность:
- Автосохранение черновиков
- История изменений и версионирование
- Прикрепление файлов
- Система одобрения
- Экспорт в различные форматы
"""

import pytest
import tempfile
import json
import os
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from services.request_draft_service import RequestDraftService
from services.file_attachment_service import FileAttachmentService
from services.approval_service import ApprovalService
from services.request_export_service import RequestExportService


class TestRequestDraftService:
    """Тесты сервиса черновиков заявок."""
    
    @pytest.fixture
    def draft_service(self, test_db_connection):
        """Фикстура сервиса черновиков."""
        return RequestDraftService(test_db_connection)
    
    @pytest.fixture
    def sample_draft_data(self):
        """Образец данных черновика."""
        return {
            "scenario_id": 1,
            "tests": ["Растяжение", "Твёрдость"],
            "results": [
                {"name": "Растяжение", "result": {"σ₀.₂": 250, "σᵥ": 400, "δ": 25}},
                {"name": "Твёрдость", "result": {"HB": 180}}
            ],
            "timestamp": datetime.now().isoformat()
        }
    
    def test_get_autosave_settings_default(self, draft_service):
        """Тест получения настроек автосохранения по умолчанию."""
        settings = draft_service.get_autosave_settings("test_user")
        
        assert settings['autosave_enabled'] is True
        assert settings['autosave_interval'] == 300
        assert settings['max_drafts'] == 10
    
    def test_save_autosave_settings(self, draft_service):
        """Тест сохранения настроек автосохранения."""
        settings = {
            'autosave_enabled': False,
            'autosave_interval': 600,
            'max_drafts': 5
        }
        
        result = draft_service.save_autosave_settings("test_user", settings)
        assert result is True
        
        # Проверяем сохранение
        saved_settings = draft_service.get_autosave_settings("test_user")
        assert saved_settings['autosave_enabled'] is False
        assert saved_settings['autosave_interval'] == 600
        assert saved_settings['max_drafts'] == 5
    
    def test_save_draft(self, draft_service, sample_draft_data):
        """Тест сохранения черновика."""
        draft_id = draft_service.save_draft(
            1, "Тестовый черновик", sample_draft_data, "test_user"
        )
        
        assert draft_id > 0
        
        # Проверяем сохранение
        saved_draft = draft_service.get_draft(draft_id)
        assert saved_draft is not None
        assert saved_draft['draft_name'] == "Тестовый черновик"
        assert saved_draft['draft_data'] == sample_draft_data
    
    def test_save_auto_draft(self, draft_service, sample_draft_data):
        """Тест автосохранения черновика."""
        draft_id = draft_service.save_draft(
            1, "Автосохранение_12:34:56", sample_draft_data, "test_user", is_auto_save=True
        )
        
        assert draft_id > 0
        
        # Проверяем что это автосохранение
        saved_draft = draft_service.get_draft(draft_id)
        assert saved_draft['is_auto_save'] is True
    
    def test_get_drafts(self, draft_service, sample_draft_data):
        """Тест получения списка черновиков."""
        # Создаем несколько черновиков
        draft_service.save_draft(1, "Черновик 1", sample_draft_data, "test_user")
        draft_service.save_draft(1, "Черновик 2", sample_draft_data, "test_user", is_auto_save=True)
        draft_service.save_draft(1, "Черновик 3", sample_draft_data, "other_user")
        
        # Получаем черновики пользователя
        drafts = draft_service.get_drafts(1, "test_user")
        assert len(drafts) == 2
        
        # Получаем все черновики
        all_drafts = draft_service.get_drafts(1)
        assert len(all_drafts) == 3
    
    def test_delete_draft(self, draft_service, sample_draft_data):
        """Тест удаления черновика."""
        draft_id = draft_service.save_draft(
            1, "Удаляемый черновик", sample_draft_data, "test_user"
        )
        
        # Удаляем
        result = draft_service.delete_draft(draft_id, "test_user")
        assert result is True
        
        # Проверяем что удален
        deleted_draft = draft_service.get_draft(draft_id)
        assert deleted_draft is None
    
    def test_delete_draft_wrong_user(self, draft_service, sample_draft_data):
        """Тест удаления чужого черновика."""
        draft_id = draft_service.save_draft(
            1, "Чужой черновик", sample_draft_data, "test_user"
        )
        
        # Пытаемся удалить чужим пользователем
        with pytest.raises(Exception):
            draft_service.delete_draft(draft_id, "other_user")
    
    def test_create_version(self, draft_service, sample_draft_data):
        """Тест создания версии."""
        old_data = {"scenario_id": 1, "tests": ["Растяжение"], "results": []}
        
        version_num = draft_service.create_version(
            1, "Добавлены результаты", sample_draft_data, old_data, "test_user"
        )
        
        assert version_num == 1
        
        # Создаем еще одну версию
        version_num2 = draft_service.create_version(
            1, "Исправления", sample_draft_data, old_data, "test_user"
        )
        
        assert version_num2 == 2
    
    def test_get_versions(self, draft_service, sample_draft_data):
        """Тест получения списка версий."""
        old_data = {"scenario_id": 1, "tests": ["Растяжение"], "results": []}
        
        # Создаем несколько версий
        draft_service.create_version(1, "Версия 1", sample_draft_data, old_data, "test_user")
        draft_service.create_version(1, "Версия 2", sample_draft_data, old_data, "test_user")
        
        versions = draft_service.get_versions(1)
        assert len(versions) == 2
        
        # Проверяем порядок (по убыванию номера версии)
        assert versions[0]['version_number'] == 2
        assert versions[1]['version_number'] == 1
    
    def test_get_version_data(self, draft_service, sample_draft_data):
        """Тест получения данных версии."""
        old_data = {"scenario_id": 1, "tests": ["Растяжение"], "results": []}
        
        version_num = draft_service.create_version(
            1, "Тестовая версия", sample_draft_data, old_data, "test_user"
        )
        
        # Получаем версии и берем ID первой
        versions = draft_service.get_versions(1)
        version_id = versions[0]['id']
        
        # Получаем данные версии
        version_data = draft_service.get_version_data(version_id)
        assert version_data is not None
        assert version_data['version_number'] == version_num
        assert version_data['data_snapshot'] == sample_draft_data


class TestFileAttachmentService:
    """Тесты сервиса прикрепления файлов."""
    
    @pytest.fixture
    def attachment_service(self, test_db_connection):
        """Фикстура сервиса файлов."""
        with tempfile.TemporaryDirectory() as temp_dir:
            service = FileAttachmentService(test_db_connection, temp_dir)
            yield service
    
    @pytest.fixture
    def sample_file(self):
        """Образец файла для тестирования."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Тестовое содержимое файла")
            file_path = f.name
        
        yield file_path
        
        # Cleanup
        try:
            os.unlink(file_path)
        except FileNotFoundError:
            pass
    
    def test_upload_file(self, attachment_service, sample_file):
        """Тест загрузки файла."""
        attachment_id = attachment_service.upload_file(
            1, "Растяжение", sample_file, "Тестовый файл", "test_user"
        )
        
        assert attachment_id > 0
        
        # Проверяем информацию о файле
        attachment = attachment_service.get_attachment(attachment_id)
        assert attachment is not None
        assert attachment['test_name'] == "Растяжение"
        assert attachment['description'] == "Тестовый файл"
        assert attachment['uploaded_by'] == "test_user"
        assert attachment['file_exists'] is True
    
    def test_upload_large_file(self, attachment_service):
        """Тест загрузки слишком большого файла."""
        # Создаем большой файл
        with tempfile.NamedTemporaryFile(delete=False) as f:
            # Записываем больше максимального размера
            large_data = b'x' * (attachment_service.MAX_FILE_SIZE + 1)
            f.write(large_data)
            large_file_path = f.name
        
        try:
            with pytest.raises(Exception) as exc_info:
                attachment_service.upload_file(
                    1, "Растяжение", large_file_path, "Большой файл", "test_user"
                )
            
            assert "размер файла превышает" in str(exc_info.value).lower()
        finally:
            os.unlink(large_file_path)
    
    def test_upload_forbidden_extension(self, attachment_service):
        """Тест загрузки файла с запрещенным расширением."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.exe', delete=False) as f:
            f.write("Executable content")
            exe_file_path = f.name
        
        try:
            with pytest.raises(Exception) as exc_info:
                attachment_service.upload_file(
                    1, "Растяжение", exe_file_path, "Исполняемый файл", "test_user"
                )
            
            assert "тип файла" in str(exc_info.value).lower()
        finally:
            os.unlink(exe_file_path)
    
    def test_get_attachments(self, attachment_service, sample_file):
        """Тест получения списка файлов."""
        # Загружаем несколько файлов
        attachment_service.upload_file(1, "Растяжение", sample_file, "Файл 1", "test_user")
        attachment_service.upload_file(1, "Растяжение", sample_file, "Файл 2", "test_user")
        attachment_service.upload_file(1, "Твёрдость", sample_file, "Файл 3", "test_user")
        
        # Получаем файлы для конкретного теста
        tension_files = attachment_service.get_attachments(1, "Растяжение")
        assert len(tension_files) == 2
        
        # Получаем все файлы заявки
        all_files = attachment_service.get_attachments(1)
        assert len(all_files) == 3
    
    def test_delete_attachment(self, attachment_service, sample_file):
        """Тест удаления файла."""
        attachment_id = attachment_service.upload_file(
            1, "Растяжение", sample_file, "Удаляемый файл", "test_user"
        )
        
        # Мягкое удаление
        result = attachment_service.delete_attachment(attachment_id, "test_user")
        assert result is True
        
        # Проверяем что файл помечен как удаленный
        attachments = attachment_service.get_attachments(1, "Растяжение")
        assert len(attachments) == 0  # Не должен показываться в списке
    
    def test_get_file_content(self, attachment_service, sample_file):
        """Тест получения содержимого файла."""
        attachment_id = attachment_service.upload_file(
            1, "Растяжение", sample_file, "Читаемый файл", "test_user"
        )
        
        content = attachment_service.get_file_content(attachment_id)
        assert content is not None
        assert "Тестовое содержимое файла".encode("utf-8") in content
    
    def test_update_attachment_description(self, attachment_service, sample_file):
        """Тест обновления описания файла."""
        attachment_id = attachment_service.upload_file(
            1, "Растяжение", sample_file, "Старое описание", "test_user"
        )
        
        result = attachment_service.update_attachment_description(
            attachment_id, "Новое описание", "test_user"
        )
        assert result is True
        
        # Проверяем обновление
        attachment = attachment_service.get_attachment(attachment_id)
        assert attachment['description'] == "Новое описание"
    
    def test_get_storage_statistics(self, attachment_service, sample_file):
        """Тест статистики хранилища."""
        # Загружаем несколько файлов
        attachment_service.upload_file(1, "Растяжение", sample_file, "Файл 1", "user1")
        attachment_service.upload_file(1, "Твёрдость", sample_file, "Файл 2", "user2")
        
        stats = attachment_service.get_storage_statistics()
        
        assert stats['total_files'] == 2
        assert stats['total_size'] > 0
        assert stats['requests_with_files'] == 1
        assert stats['uploaders'] == 2
        assert len(stats['file_types']) > 0
        assert len(stats['top_uploaders']) == 2


class TestApprovalService:
    """Тесты сервиса одобрений."""
    
    @pytest.fixture
    def approval_service(self, test_db_connection):
        """Фикстура сервиса одобрений."""
        return ApprovalService(test_db_connection)
    
    def test_get_approval_config(self, approval_service):
        """Тест получения конфигурации одобрения."""
        config = approval_service.get_approval_config("Растяжение")
        assert isinstance(config, list)
        
        # Проверяем что есть базовые правила
        assert len(config) > 0
        
        # Проверяем структуру правил
        for rule in config:
            assert 'approval_level' in rule
            assert 'approver_role' in rule
            assert 'is_required' in rule
    
    def test_create_approval_request(self, approval_service):
        """Тест создания запроса на одобрение."""
        result = approval_service.create_approval_request(
            1, "Растяжение", "test_user", "09Г2С"
        )
        assert result is True
    
    def test_get_pending_approvals(self, approval_service):
        """Тест получения ожидающих одобрений."""
        # Создаем запрос на одобрение
        approval_service.create_approval_request(1, "Растяжение", "test_user")
        
        # Получаем ожидающие одобрения
        pending = approval_service.get_pending_approvals("test_user", ["lab_engineer"])
        assert isinstance(pending, list)
    
    def test_approval_workflow(self, approval_service):
        """Тест полного цикла одобрения."""
        # Создаем запрос
        approval_service.create_approval_request(1, "Растяжение", "test_user")
        
        # Получаем ожидающие одобрения
        pending = approval_service.get_pending_approvals("approver", ["lab_engineer"])
        
        if pending:
            approval_id = pending[0]['id']
            
            # Одобряем
            result = approval_service.approve_request(approval_id, "approver", "Все хорошо")
            assert result is True
            
            # Проверяем статус
            status = approval_service.get_approval_status(1, "Растяжение")
            assert status['approved'] > 0
    
    def test_reject_request(self, approval_service):
        """Тест отклонения заявки."""
        # Создаем запрос
        approval_service.create_approval_request(1, "Растяжение", "test_user")
        
        # Получаем ожидающие одобрения
        pending = approval_service.get_pending_approvals("approver", ["lab_engineer"])
        
        if pending:
            approval_id = pending[0]['id']
            
            # Отклоняем
            result = approval_service.reject_request(
                approval_id, "approver", "Неверные результаты", 
                ["Повторить испытание", "Проверить образцы"]
            )
            assert result is True
            
            # Проверяем статус
            status = approval_service.get_approval_status(1, "Растяжение")
            assert status['rejected'] > 0
    
    def test_get_approval_history(self, approval_service):
        """Тест получения истории одобрений."""
        # Создаем запрос
        approval_service.create_approval_request(1, "Растяжение", "test_user")
        
        # Получаем историю
        history = approval_service.get_approval_history(1, "Растяжение")
        assert isinstance(history, list)
        
        # Проверяем структуру записей истории
        for record in history:
            assert 'approval_level' in record
            assert 'approval_status' in record
            assert 'created_at' in record
    
    def test_reset_approval_after_changes(self, approval_service):
        """Тест сброса одобрений после изменений."""
        # Создаем и одобряем запрос
        approval_service.create_approval_request(1, "Растяжение", "test_user")
        
        # Сбрасываем одобрения
        result = approval_service.reset_approval_after_changes(1, "Растяжение")
        assert result is True


class TestRequestExportService:
    """Тесты сервиса экспорта заявок."""
    
    @pytest.fixture
    def export_service(self, test_db_connection):
        """Фикстура сервиса экспорта."""
        with tempfile.TemporaryDirectory() as temp_dir:
            service = RequestExportService(test_db_connection, temp_dir)
            yield service
    
    @pytest.fixture
    def sample_request_data(self, test_db_connection):
        """Создание образца заявки для экспорта."""
        # Создаем тестовую заявку в БД
        cursor = test_db_connection.cursor()
        
        # Добавляем материал
        cursor.execute("""
            INSERT INTO Materials (heat_num, size, cert_num, grade_id)
            VALUES ('12345', '20x3', 'CERT001', 1)
        """)
        material_id = cursor.lastrowid
        
        # Добавляем заявку
        cursor.execute("""
            INSERT INTO lab_requests (request_number, material_id, scenario_id, tests_json, results_json, status)
            VALUES ('REQ-TEST-001', ?, 1, ?, ?, 'new')
        """, (
            material_id,
            json.dumps(["Растяжение", "Твёрдость"], ensure_ascii=False),
            json.dumps([
                {"name": "Растяжение", "result": {"σ₀.₂": 250, "σᵥ": 400, "δ": 25}},
                {"name": "Твёрдость", "result": {"HB": 180}}
            ], ensure_ascii=False)
        ))
        request_id = cursor.lastrowid
        
        test_db_connection.commit()
        return request_id
    
    def test_export_to_pdf(self, export_service, sample_request_data):
        """Тест экспорта в PDF."""
        file_path = export_service.export_to_pdf(sample_request_data)
        
        assert os.path.exists(file_path)
        assert file_path.endswith('.pdf')
        assert os.path.getsize(file_path) > 0
    
    def test_export_to_pdf_with_template(self, export_service, sample_request_data):
        """Тест экспорта в PDF с шаблоном."""
        file_path = export_service.export_to_pdf(sample_request_data, "summary")
        
        assert os.path.exists(file_path)
        assert file_path.endswith('.pdf')
    
    @patch('docx.Document')
    def test_export_to_docx(self, mock_document, export_service, sample_request_data):
        """Тест экспорта в DOCX."""
        # Мокаем Document для избежания зависимости от файловой системы
        mock_doc = Mock()
        mock_document.return_value = mock_doc
        
        file_path = export_service.export_to_docx(sample_request_data)
        
        # Проверяем что Document был создан
        mock_document.assert_called_once()
        mock_doc.save.assert_called_once()
    
    @patch('openpyxl.Workbook')
    def test_export_to_xlsx(self, mock_workbook, export_service, sample_request_data):
        """Тест экспорта в XLSX."""
        # Мокаем Workbook
        mock_wb = Mock()
        mock_workbook.return_value = mock_wb
        mock_ws = Mock()
        mock_wb.active = mock_ws
        
        file_path = export_service.export_to_xlsx([sample_request_data])
        
        # Проверяем что Workbook был создан
        mock_workbook.assert_called_once()
        mock_wb.save.assert_called_once()
    
    def test_export_batch_pdf(self, export_service, sample_request_data):
        """Тест пакетного экспорта в PDF."""
        files = export_service.export_batch([sample_request_data], "pdf", "detailed")
        
        assert len(files) == 1
        assert all(os.path.exists(f) for f in files)
        assert all(f.endswith('.pdf') for f in files)
    
    def test_get_export_templates(self, export_service):
        """Тест получения списка шаблонов."""
        templates = export_service.get_export_templates()
        
        assert 'pdf' in templates
        assert 'docx' in templates
        assert 'xlsx' in templates
        
        assert 'detailed' in templates['pdf']
        assert 'summary' in templates['pdf']
    
    def test_cleanup_old_exports(self, export_service):
        """Тест очистки старых экспортов."""
        # Создаем тестовый файл
        test_file = export_service.export_dir / "old_export.pdf"
        test_file.write_text("test content")
        
        # Изменяем время модификации на старое
        old_time = datetime.now().timestamp() - (40 * 24 * 60 * 60)  # 40 дней назад
        os.utime(test_file, (old_time, old_time))
        
        # Очищаем файлы старше 30 дней
        deleted_count = export_service.cleanup_old_exports(30)
        
        assert deleted_count >= 1
        assert not test_file.exists()


class TestIntegrationEnhancedEditor:
    """Интеграционные тесты улучшенного редактора."""
    
    def test_full_workflow(self, test_db_connection):
        """Тест полного рабочего процесса."""
        # Создаем все сервисы
        draft_service = RequestDraftService(test_db_connection)
        attachment_service = FileAttachmentService(test_db_connection)
        approval_service = ApprovalService(test_db_connection)
        export_service = RequestExportService(test_db_connection)
        
        request_id = 1
        user_login = "test_user"
        
        # 1. Сохраняем черновик
        draft_data = {
            "scenario_id": 1,
            "tests": ["Растяжение"],
            "results": [{"name": "Растяжение", "result": {"σ₀.₂": 250}}]
        }
        
        draft_id = draft_service.save_draft(
            request_id, "Тестовый черновик", draft_data, user_login
        )
        assert draft_id > 0
        
        # 2. Создаем версию
        old_data = {"scenario_id": 1, "tests": ["Растяжение"], "results": []}
        version_num = draft_service.create_version(
            request_id, "Добавили результаты", draft_data, old_data, user_login
        )
        assert version_num > 0
        
        # 3. Создаем запрос на одобрение
        approval_result = approval_service.create_approval_request(
            request_id, "Растяжение", user_login
        )
        assert approval_result is True
        
        # 4. Проверяем что все работает вместе
        drafts = draft_service.get_drafts(request_id, user_login)
        assert len(drafts) >= 1
        
        versions = draft_service.get_versions(request_id)
        assert len(versions) >= 1
        
        approval_status = approval_service.get_approval_status(request_id, "Растяжение")
        assert approval_status['total'] > 0
    
    def test_autosave_and_version_interaction(self, test_db_connection):
        """Тест взаимодействия автосохранения и версионирования."""
        draft_service = RequestDraftService(test_db_connection)
        
        request_id = 1
        user_login = "test_user"
        
        # Создаем несколько автосохранений
        for i in range(5):
            draft_data = {
                "scenario_id": 1,
                "tests": ["Растяжение"],
                "results": [{"name": "Растяжение", "result": {"σ₀.₂": 250 + i}}]
            }
            
            draft_service.save_draft(
                request_id, f"Автосохранение_{i}", draft_data, user_login, is_auto_save=True
            )
        
        # Проверяем что автосохранения создались
        drafts = draft_service.get_drafts(request_id, user_login)
        auto_drafts = [d for d in drafts if d['is_auto_save']]
        assert len(auto_drafts) == 5
        
        # Создаем версию на основе последнего автосохранения
        last_draft = draft_service.get_draft(auto_drafts[0]['id'])  # Первый - самый новый
        
        old_data = {"scenario_id": 1, "tests": ["Растяжение"], "results": []}
        version_num = draft_service.create_version(
            request_id, "Версия из автосохранения", 
            last_draft['draft_data'], old_data, user_login
        )
        
        assert version_num > 0
        
        # Проверяем данные версии
        versions = draft_service.get_versions(request_id)
        version_data = draft_service.get_version_data(versions[0]['id'])
        
        assert version_data['data_snapshot'] == last_draft['draft_data']


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 
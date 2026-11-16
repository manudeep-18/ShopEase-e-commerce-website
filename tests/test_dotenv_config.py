import os

from dotenv import load_dotenv

import app as backend


def test_process_environment_takes_priority_over_dotenv(tmp_path, monkeypatch):
    setting = 'SHOPEASE_DOTENV_TEST_VALUE'
    (tmp_path / '.env').write_text(f'{setting}=from-dotenv\n', encoding='utf-8')
    monkeypatch.setenv('PYTHON_DOTENV_DISABLED', '')
    monkeypatch.setenv(setting, 'from-process')

    load_dotenv(dotenv_path=tmp_path / '.env')

    assert os.environ[setting] == 'from-process'


def test_test_configuration_disables_dotenv_loading(tmp_path, monkeypatch):
    setting = 'SHOPEASE_DOTENV_DISABLED_TEST_VALUE'
    (tmp_path / '.env').write_text(f'{setting}=must-not-load\n', encoding='utf-8')
    monkeypatch.delenv(setting, raising=False)
    assert os.environ['PYTHON_DOTENV_DISABLED'] == '1'

    load_dotenv(dotenv_path=tmp_path / '.env')

    assert setting not in os.environ


def test_smtp_from_accepts_display_name_format(monkeypatch):
    monkeypatch.setenv('SMTP_HOST', 'smtp.example.com')
    monkeypatch.setenv('SMTP_PORT', '587')
    monkeypatch.setenv('SMTP_USERNAME', 'shop@example.com')
    monkeypatch.setenv('SMTP_PASSWORD', 'test-password')
    monkeypatch.setenv('SMTP_FROM', 'ShopEase <shop@example.com>')
    sent_messages = []

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            assert (host, port, timeout) == ('smtp.example.com', 587, 10)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def starttls(self):
            pass

        def login(self, username, password):
            assert (username, password) == ('shop@example.com', 'test-password')

        def send_message(self, message):
            sent_messages.append(message)

    monkeypatch.setattr(backend.smtplib, 'SMTP', FakeSMTP)

    backend.send_email('customer@example.com', 'Test', '<p>Code</p>', 'Code')

    assert sent_messages[0]['From'] == 'ShopEase <shop@example.com>'

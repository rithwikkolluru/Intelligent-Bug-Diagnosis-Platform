from __future__ import annotations

from app.services.redaction import redact_secrets


def test_redact_password_assignment():
    clean, count = redact_secrets('password=supersecret')
    assert '[REDACTED]' in clean
    assert count >= 1


def test_redact_json_secret():
    clean, count = redact_secrets('{"token": "abc123"}')
    assert '[REDACTED]' in clean
    assert count >= 1


def test_redact_bearer_header():
    clean, _ = redact_secrets('Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9')
    assert '[REDACTED]' in clean


def test_redact_connection_string():
    clean, _ = redact_secrets('postgresql://user:pass@db.local/app')
    assert '[REDACTED]' in clean and 'user:[REDACTED]@db.local' in clean


def test_redact_private_key_block():
    clean, count = redact_secrets('-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----')
    assert '[REDACTED]' in clean
    assert count >= 1


def test_normal_text_and_stack_frames_not_redacted():
    sample = 'The bug is caused by a file read issue.\n at com.example.Service.read(Service.java:30)'
    clean, count = redact_secrets(sample)
    assert 'file read issue' in clean
    assert 'Service.java:30' in clean
    assert count == 0

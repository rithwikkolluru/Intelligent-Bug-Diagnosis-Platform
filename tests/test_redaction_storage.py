from __future__ import annotations


def test_redaction_happens_before_storage(client):
    payload = {
        'title': 'Secret issue',
        'description': 'password=supersecret and token=xyz123',
        'error_logs': 'Authorization: Bearer abcdef123456',
    }
    response = client.post('/api/bugs', json=payload)
    data = response.json()
    assert response.status_code == 201
    assert '[REDACTED]' in data['description']
    assert '[REDACTED]' in data['error_logs']
    assert 'supersecret' not in data['description']
    assert 'abcdef123456' not in data['error_logs']

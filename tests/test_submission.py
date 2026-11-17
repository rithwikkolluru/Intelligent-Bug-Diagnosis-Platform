from __future__ import annotations

import pytest


@pytest.mark.parametrize(
    ('payload', 'expected_status'),
    [
        ({'title': 'Null pointer bug', 'description': 'This bug appears when login user is null.'}, 201),
        ({'title': 'Missing description', 'description': 'Short'}, 422),
    ],
)
def test_submission_payloads(client, payload, expected_status):
    response = client.post('/api/bugs', json=payload)
    assert response.status_code == expected_status


def test_missing_title(client):
    response = client.post('/api/bugs', json={'title': '', 'description': 'This is a valid description with enough length.'})
    assert response.status_code == 422


def test_whitespace_only_input_rejected(client):
    response = client.post('/api/bugs', json={'title': '   ', 'description': '   '})
    assert response.status_code == 422


def test_valid_paste_submission_stored(client):
    payload = {
        'title': 'Java stack trace failure',
        'description': 'User login fails due to null id in service layer.',
        'stack_trace': 'java.lang.NullPointerException\n\tat com.example.Service.login(Service.java:42)\nCaused by: java.lang.IllegalStateException',
        'error_logs': 'error logs here',
        'programming_language': 'Java',
    }
    response = client.post('/api/bugs', json=payload)
    data = response.json()
    assert response.status_code == 201
    assert data['title'] == payload['title']
    assert data['source_type'] == 'paste'
    assert data['programming_language'] == 'Java'


def test_get_bug_by_id(client):
    payload = {'title': 'Alpha bug', 'description': 'This description is definitely longer than ten chars.'}
    created = client.post('/api/bugs', json=payload)
    bug_id = created.json()['bug_id']
    response = client.get(f'/api/bugs/{bug_id}')
    assert response.status_code == 200
    assert response.json()['bug_id'] == bug_id


def test_get_unknown_bug_404(client):
    response = client.get('/api/bugs/99999')
    assert response.status_code == 404
    assert response.json()['code'] == 'NOT_FOUND'


def test_list_pagination_order(client):
    for i in range(3):
        client.post('/api/bugs', json={'title': f'Bug {i}', 'description': 'This description is definitely long enough.'})
    response = client.get('/api/bugs?limit=2&offset=0')
    data = response.json()
    assert response.status_code == 200
    assert data['limit'] == 2
    assert len(data['items']) == 2
    assert data['total'] >= 3

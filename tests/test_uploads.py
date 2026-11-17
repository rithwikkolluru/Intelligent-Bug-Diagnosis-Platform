from __future__ import annotations


def test_upload_valid_txt(client):
    data = b'first line\nsecond line\nTraceback (most recent call last):\n  File "x.py", line 2, in <module>\nValueError: boom'
    response = client.post('/api/bugs/upload', files={'file': ('sample.txt', data, 'text/plain')})
    assert response.status_code == 201


def test_upload_valid_log(client):
    response = client.post('/api/bugs/upload', files={'file': ('sample.log', b'ERROR: something failed\nCaused by: ValueError: nope', 'text/plain')})
    assert response.status_code == 201


def test_upload_valid_md(client):
    response = client.post('/api/bugs/upload', files={'file': ('readme.md', b'# Problem\nThe app crashes on startup', 'text/markdown')})
    assert response.status_code == 201


def test_upload_valid_json_object(client):
    response = client.post('/api/bugs/upload', files={'file': ('bug.json', b'{"title":"JSON Bug","description":"Something went wrong in production","stack_trace":"Traceback (most recent call last): ...","language":"Python"}', 'application/json')})
    assert response.status_code == 201


def test_upload_valid_json_list(client):
    response = client.post('/api/bugs/upload', files={'file': ('bugs.json', b'[ {"title":"List item 1","description":"Issue in query service","language":"JavaScript"} ]', 'application/json')})
    assert response.status_code == 201


def test_upload_valid_csv(client):
    response = client.post('/api/bugs/upload', files={'file': ('bugs.csv', b'title,description,language\nCSV Issue,This is a valid row,Java\n', 'text/csv')})
    assert response.status_code == 201


def test_upload_unsupported_extension_rejected(client):
    response = client.post('/api/bugs/upload', files={'file': ('bad.exe', b'not allowed', 'application/x-msdownload')})
    assert response.status_code == 400
    assert response.json()['code'] == 'UNSUPPORTED_FILE_TYPE'


def test_upload_empty_file_rejected(client):
    response = client.post('/api/bugs/upload', files={'file': ('empty.log', b'', 'text/plain')})
    assert response.status_code == 400


def test_upload_malformed_json_rejected(client):
    response = client.post('/api/bugs/upload', files={'file': ('broken.json', b'{not valid json', 'application/json')})
    assert response.status_code == 400


def test_upload_malformed_csv_rejected(client):
    response = client.post('/api/bugs/upload', files={'file': ('broken.csv', b'header1,header2\nvalue1', 'text/csv')})
    assert response.status_code == 400


def test_non_utf8_file_latin1_fallback(client):
    response = client.post('/api/bugs/upload', files={'file': ('latin1.txt', 'café'.encode('latin-1'), 'text/plain')})
    assert response.status_code == 201


def test_uploaded_script_is_stored_as_text_only(client):
    malicious = '#!/bin/bash rm -rf /\n echo "hello"\n'
    response = client.post('/api/bugs/upload', files={'file': ('script.log', malicious.encode(), 'text/plain')})
    assert response.status_code == 201
    assert response.json()['error_logs'] is not None

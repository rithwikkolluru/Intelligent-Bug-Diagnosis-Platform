from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import generic_exception_handler


def test_explicit_invalid_field_error(client):
    response = client.post('/api/bugs', json={'title': 'x', 'description': 'short'})
    assert response.status_code == 422


def test_unhandled_exception_does_not_expose_internal_details():
    test_app = FastAPI()
    test_app.add_exception_handler(Exception, generic_exception_handler)

    @test_app.get("/test-internal-error")
    def raise_internal_error():
        raise RuntimeError("sensitive internal detail")

    response = TestClient(test_app, raise_server_exceptions=False).get("/test-internal-error")

    assert response.status_code == 500
    assert response.json() == {
        "detail": "An unexpected error occurred.",
        "code": "INTERNAL_ERROR",
    }


def test_logs_and_trace_upload_are_kept(client):
    payload = {
        'title': 'Trace issue',
        'description': 'Detailed reproduction',
        'stack_trace': 'java.lang.RuntimeException\n\tat x.main(x.java:1)',
        'error_logs': 'ERROR: bad',
    }
    response = client.post('/api/bugs', json=payload)
    assert response.status_code == 201
    assert response.json()['stack_trace'] is not None
    assert response.json()['error_logs'] == 'ERROR: bad'


def test_empty_body_rejected(client):
    response = client.post('/api/bugs', json={})
    assert response.status_code == 422

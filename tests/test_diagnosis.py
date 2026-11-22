from __future__ import annotations

from unittest.mock import MagicMock, patch


def test_get_sample_bugs(client):
    response = client.get("/api/samples")
    assert response.status_code == 200
    samples = response.json()
    assert len(samples) >= 3
    assert any("java" in s["id"] for s in samples)
    assert any("python" in s["id"] for s in samples)


def test_diagnose_existing_bug(client):
    # 1. Create a bug
    create_resp = client.post(
        "/api/bugs",
        json={
            "title": "NullPointerException in user login",
            "description": "User login crashes during authentication handler execution.",
            "stack_trace": (
                "java.lang.NullPointerException\n"
                "    at com.example.service.AuthenticationService.authenticate(AuthenticationService.java:54)"
            ),
            "programming_language": "Java",
        },
    )
    assert create_resp.status_code == 201
    bug_id = create_resp.json()["bug_id"]

    # 2. Diagnose bug
    diag_resp = client.post(f"/api/bugs/{bug_id}/diagnose")
    assert diag_resp.status_code == 200
    data = diag_resp.json()
    assert data["bug_id"] == bug_id
    assert data["status"] == "completed"
    assert "root_cause" in data and len(data["root_cause"]) > 10
    assert "fix_recommendation" in data and len(data["fix_recommendation"]) > 10
    assert data["code_patch"] is not None
    assert isinstance(data["verification_steps"], list)
    assert isinstance(data["similar_defects"], list)
    assert data["confidence_score"] > 0

    # 3. Retrieve diagnosis via GET
    get_resp = client.get(f"/api/bugs/{bug_id}/diagnosis")
    assert get_resp.status_code == 200
    assert get_resp.json()["diagnosis_id"] == data["diagnosis_id"]


def test_submit_and_diagnose_convenience_endpoint(client):
    payload = {
        "title": "KeyError 'token' in API gateway",
        "description": "API Gateway worker crashes on missing token key in request headers.",
        "stack_trace": (
            "Traceback (most recent call last):\n"
            "  File \"gateway.py\", line 42, in handle\n"
            "    token = headers['token']\n"
            "KeyError: 'token'"
        ),
        "programming_language": "Python",
    }
    response = client.post("/api/diagnose", json=payload)
    assert response.status_code == 201
    res = response.json()
    assert "bug" in res and res["bug"]["status"] == "diagnosed"
    assert "diagnosis" in res and res["diagnosis"]["confidence_score"] > 0


def test_diagnose_nonexistent_bug_returns_404(client):
    response = client.post("/api/bugs/99999/diagnose")
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


def test_upload_file_exceeding_size_limit_rejected(client):
    # Create content larger than 5 MB
    large_content = b"A" * (5 * 1024 * 1024 + 100)
    response = client.post(
        "/api/bugs/upload",
        files={"file": ("large_file.txt", large_content, "text/plain")},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "FILE_TOO_LARGE"


def test_upload_filename_sanitization(client):
    # Test directory traversal in filename
    data = b"first line\nsecond line with error details"
    response = client.post(
        "/api/bugs/upload",
        files={"file": ("../../etc/sample.txt", data, "text/plain")},
    )
    assert response.status_code == 201
    assert response.json()["original_filename"] == "sample.txt"


@patch("app.services.gemini.httpx.AsyncClient.post")
def test_gemini_api_integration_mock(mock_post, client):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": (
                                '{"root_cause": "Live Gemini identified missing null check.", '
                                '"fix_recommendation": "1. Use Optional.ofNullable()", '
                                '"code_patch": "Optional.ofNullable(user).ifPresent(...)", '
                                '"verification_steps": ["Run unit test"], '
                                '"duplicate_assessment": "Possible duplicate of APACHE-5120", '
                                '"confidence_score": 0.95}'
                            )
                        }
                    ]
                }
            }
        ]
    }
    mock_post.return_value = mock_response

    # Submit bug and diagnose with custom Gemini API Key header
    resp = client.post(
        "/api/diagnose",
        json={
            "title": "Null check bug in UserService",
            "description": "User service throws error when user is absent.",
            "stack_trace": "java.lang.NullPointerException\n    at UserService.get()",
            "programming_language": "Java",
        },
        headers={"X-Gemini-API-Key": "test-gemini-key"},
    )
    assert resp.status_code == 201
    diag = resp.json()["diagnosis"]
    assert "Google Gemini" in diag["model_used"]
    assert "Live Gemini identified" in diag["root_cause"]

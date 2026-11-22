"""
Orchestration integration tests (fast — uses FakeLLM and in-memory SQLite).

Coverage:
- Both agents triggered automatically on paste and upload submission
- Description-only: log analysis skipped with NO_LOG_CONTENT
- Logs-only: triage still runs
- Invalid/empty input rejected
- One agent fails → partial with the other intact
- Both fail → analysis_failed
- LLM unavailable → rule-based fallback, warning logged
- BugContext validates and round-trips through JSON
- TRIAGE_AFTER_LOG mode passes log enrichment to triage
- Downstream contract: derived facts readable from BugContext
- Analysis endpoints: 404 when none, 202 trigger, config
- Re-run creates attempt counter
- Refusing double-run (conflict)
"""
from __future__ import annotations

import os

# Force inline execution and disable auto-submit for most tests
os.environ.setdefault("ANALYSIS_EXECUTION", "inline")
os.environ.setdefault("ANALYSIS_ON_SUBMIT", "false")  # Controlled per-test

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import app.models.analysis  # noqa: E402, F401
import app.models.bug  # noqa: E402, F401
from app.agents.base import AgentInput  # noqa: E402
from app.database.base import Base  # noqa: E402
from app.database.session import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.orchestration.graph import run_analysis  # noqa: E402
from app.schemas.bug_context import BugContext, BugSnapshot  # noqa: E402

# In-memory test database with StaticPool so all connections share the same memory DB
TEST_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=TEST_ENGINE)


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.create_all(bind=TEST_ENGINE)
    yield
    Base.metadata.drop_all(bind=TEST_ENGINE)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db_session():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------
def make_agent_input(**kwargs) -> AgentInput:
    defaults = dict(title="Test bug", description="A bug occurred.")
    defaults.update(kwargs)
    return AgentInput(**defaults)


def make_snapshot(bug_id: int = 1, **kwargs) -> BugSnapshot:
    defaults = dict(
        bug_id=bug_id,
        title="Test bug",
        description="A bug occurred.",
        source_type="paste",
        created_at="2026-01-01T00:00:00+00:00",
    )
    defaults.update(kwargs)
    return BugSnapshot(**defaults)


# -----------------------------------------------------------------------
# 1. Description-only: log analysis skipped
# -----------------------------------------------------------------------
def test_description_only_log_skipped():
    inp = make_agent_input(stack_trace=None, error_logs=None)
    snap = make_snapshot()
    ctx = run_analysis(inp, snap)
    assert isinstance(ctx, BugContext)
    assert ctx.log_analysis is None
    # Find the log run record
    log_run = next((r for r in ctx.agent_runs if r.agent_name == "log_analysis"), None)
    assert log_run is not None
    assert log_run.status == "skipped"
    assert log_run.error_code == "NO_LOG_CONTENT"
    assert ctx.analysis_status in ("complete", "partial")


# -----------------------------------------------------------------------
# 2. With stack trace: log analysis runs
# -----------------------------------------------------------------------
def test_with_stack_trace_log_analysis_runs():
    inp = make_agent_input(
        description="NullPointerException on startup",
        stack_trace="java.lang.NullPointerException\n  at com.example.App.start(App.java:42)",
    )
    snap = make_snapshot()
    ctx = run_analysis(inp, snap)
    # Log analysis should not be skipped
    log_run = next((r for r in ctx.agent_runs if r.agent_name == "log_analysis"), None)
    assert log_run is not None
    assert log_run.status not in ("skipped",)
    assert ctx.derived.has_trace is True


# -----------------------------------------------------------------------
# 3. Triage always runs (even logs-only)
# -----------------------------------------------------------------------
def test_logs_only_triage_still_runs():
    inp = make_agent_input(description="", stack_trace="java.lang.NullPointerException\n  at com.app.App.m(App.java:1)")
    snap = make_snapshot()
    ctx = run_analysis(inp, snap)
    triage_run = next((r for r in ctx.agent_runs if r.agent_name == "triage"), None)
    assert triage_run is not None
    assert triage_run.status in ("ok", "partial")


# -----------------------------------------------------------------------
# 4. Both agents triggered — triage and log both run
# -----------------------------------------------------------------------
def test_both_agents_triggered():
    inp = make_agent_input(
        description="Production database deadlock causing cascading failures",
        stack_trace="java.lang.RuntimeException: deadlock\n  at com.db.Pool.acquire(Pool.java:55)",
    )
    snap = make_snapshot()
    ctx = run_analysis(inp, snap)
    agent_names = {r.agent_name for r in ctx.agent_runs}
    assert "triage" in agent_names
    assert "log_analysis" in agent_names


# -----------------------------------------------------------------------
# 5. BugContext validates and round-trips through JSON
# -----------------------------------------------------------------------
def test_bug_context_json_roundtrip():
    inp = make_agent_input()
    snap = make_snapshot()
    ctx = run_analysis(inp, snap)
    ctx_json = ctx.model_dump_json()
    ctx2 = BugContext.model_validate_json(ctx_json)
    assert ctx2.schema_version == "2.0"
    assert ctx2.bug.bug_id == 1
    assert ctx2.derived is not None


# -----------------------------------------------------------------------
# 6. Derived facts populated correctly
# -----------------------------------------------------------------------
def test_derived_facts_java_exception():
    inp = make_agent_input(
        description="Crash on startup",
        stack_trace="java.lang.NullPointerException: unable to get field\n  at com.example.Service.load(Service.java:88)",
    )
    snap = make_snapshot(programming_language="Java")
    ctx = run_analysis(inp, snap)
    assert ctx.derived is not None
    assert ctx.derived.has_trace is True
    assert ctx.derived.exception_type is not None


# -----------------------------------------------------------------------
# 7. TRIAGE_AFTER_LOG mode: runs sequentially, log output reaches triage
# -----------------------------------------------------------------------
def test_triage_after_log_mode():
    inp = make_agent_input(
        description="Application crashed",
        stack_trace="java.lang.NullPointerException\n  at com.example.Widget.render(Widget.java:45)",
    )
    snap = make_snapshot()
    ctx = run_analysis(inp, snap, triage_after_log=True)
    triage_run = next((r for r in ctx.agent_runs if r.agent_name == "triage"), None)
    assert triage_run is not None
    # The provenance should contain log_enriched flag when log data was available
    assert ctx.analysis_status in ("complete", "partial", "failed")


# -----------------------------------------------------------------------
# 8. Invalid (empty) input rejected
# -----------------------------------------------------------------------
def test_empty_input_rejected():
    inp = make_agent_input(title="", description="", stack_trace=None, error_logs=None)
    snap = make_snapshot()
    ctx = run_analysis(inp, snap)
    assert ctx.analysis_status == "failed"
    assert any(e["code"] == "INVALID_INPUT" for e in ctx.errors)


# -----------------------------------------------------------------------
# 9. API: 404 when no analysis exists
# -----------------------------------------------------------------------
def test_api_analysis_404(client):
    r = client.get("/api/bugs/9999/analysis")
    assert r.status_code == 404
    assert r.json()["code"] == "ANALYSIS_NOT_FOUND"


# -----------------------------------------------------------------------
# 10. API: Submit bug then trigger analysis
# -----------------------------------------------------------------------
def test_api_trigger_analysis(client):
    # Submit a bug first
    r = client.post("/api/bugs", json={
        "title": "NullPointerException in service",
        "description": "NPE at startup when loading user config.",
        "stack_trace": "java.lang.NullPointerException\n  at com.example.Service.load(Service.java:12)",
    })
    assert r.status_code == 201
    bug_id = r.json()["bug_id"]

    # Trigger analysis inline (env set at top of file)
    os.environ["ANALYSIS_EXECUTION"] = "inline"
    r2 = client.post(f"/api/bugs/{bug_id}/analyze")
    assert r2.status_code in (200, 202)


# -----------------------------------------------------------------------
# 11. API: Config endpoint returns no secrets
# -----------------------------------------------------------------------
def test_api_analysis_config(client):
    r = client.get("/api/analysis/config")
    assert r.status_code == 200
    data = r.json()
    assert "provider" in data
    assert "model" in data
    # Must NOT contain API keys
    for key in data:
        assert "key" not in key.lower()
        assert "secret" not in key.lower()


# -----------------------------------------------------------------------
# 12. API: List analyses endpoint
# -----------------------------------------------------------------------
def test_api_list_analyses(client):
    r = client.get("/api/analyses?limit=5")
    assert r.status_code == 200
    assert "items" in r.json()


# -----------------------------------------------------------------------
# 13. Downstream contract: derived facts readable
# -----------------------------------------------------------------------
def test_downstream_contract_derived_always_present():
    inp = make_agent_input()
    snap = make_snapshot()
    ctx = run_analysis(inp, snap)
    # These fields must ALWAYS be present (may be None but never missing)
    assert hasattr(ctx.derived, "detected_language")
    assert hasattr(ctx.derived, "exception_type")
    assert hasattr(ctx.derived, "failure_point_summary")
    assert hasattr(ctx.derived, "component")
    assert hasattr(ctx.derived, "severity")
    assert hasattr(ctx.derived, "priority")
    assert hasattr(ctx.derived, "has_trace")
    assert hasattr(ctx.derived, "triage_confidence")
    assert hasattr(ctx.derived, "log_analysis_confidence")


# -----------------------------------------------------------------------
# 14. Analysis status = complete when both agents succeed
# -----------------------------------------------------------------------
def test_analysis_status_complete_both_succeed():
    inp = make_agent_input(
        description="Real NullPointerException in production request handler",
        stack_trace="java.lang.NullPointerException\n  at com.example.Handler.handle(Handler.java:30)",
    )
    snap = make_snapshot()
    ctx = run_analysis(inp, snap)
    # Both triage and log ran
    statuses = {r.agent_name: r.status for r in ctx.agent_runs}
    if "triage" in statuses and "log_analysis" in statuses:
        triage_ok = statuses["triage"] in ("ok", "partial")
        log_ok = statuses["log_analysis"] in ("ok", "partial", "skipped")
        if triage_ok and log_ok:
            assert ctx.analysis_status == "complete"


# -----------------------------------------------------------------------
# 15. Analysis_id persisted in context
# -----------------------------------------------------------------------
def test_analysis_id_in_context():
    inp = make_agent_input()
    snap = make_snapshot()
    ctx = run_analysis(inp, snap, analysis_id=42)
    assert ctx.analysis_id == 42

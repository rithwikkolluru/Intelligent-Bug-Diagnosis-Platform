"""Tests for Milestone 2.4 validation harness."""
from __future__ import annotations

from app.agents.validation.runner import (
    evaluate_format_diversity,
    evaluate_log_analysis,
    evaluate_triage,
    run_validation_suite,
)


def test_triage_evaluation_runs():
    samples, failures = evaluate_triage()
    assert len(samples) > 0
    # Every sample has required assessment dimensions
    for s in samples:
        assert s.predicted_severity in ("Critical", "High", "Medium", "Low")
        assert s.predicted_priority in ("P1", "P2", "P3", "P4")
        assert s.predicted_component is not None
        assert 0.0 <= s.confidence <= 1.0


def test_log_analysis_evaluation_accuracy():
    samples, failures = evaluate_log_analysis()
    assert len(samples) >= 10
    # Log analysis parsers must achieve >= 90% format detection and failure point accuracy
    fmt_accuracy = sum(1 for s in samples if s.format_match) / len(samples)
    fp_accuracy = sum(1 for s in samples if s.file_match and s.line_match) / len(samples)
    assert fmt_accuracy >= 0.90
    assert fp_accuracy >= 0.90


def test_format_diversity_coverage():
    covered = evaluate_format_diversity()
    expected = {
        "description_only",
        "description_with_stack_trace",
        "logs_without_description",
        "messy_unstructured_logs",
    }
    assert expected.issubset(set(covered))


def test_full_validation_suite_report():
    report = run_validation_suite()
    assert report.triage_total >= 9
    assert report.log_total >= 10
    assert report.log_format_accuracy >= 0.90
    assert report.log_failure_point_accuracy >= 0.90
    assert len(report.input_formats_tested) >= 4

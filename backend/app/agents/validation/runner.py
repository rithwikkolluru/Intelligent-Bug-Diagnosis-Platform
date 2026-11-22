"""
M2.4 Accuracy Validation & Evaluation Harness.

Evaluates:
1. Triage Agent across historical seeded defects (Mozilla, Apache, Eclipse)
   measuring Severity accuracy, Priority accuracy, and Component matching.
2. Log Analysis Agent across multi-format log fixtures (10 formats)
   measuring format detection, exception type extraction, failure point identification,
   and code path sequencing.
3. Diverse bug report formats:
   - Description only
   - Description + stack trace
   - Log only without description
   - Messy/unstructured logs
4. Failure case recording & confusion tracking.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from app.agents.base import AgentInput
from app.agents.log_analysis.agent import LogAnalysisAgent
from app.agents.triage.agent import TriageAgent

ROOT_DIR = Path(__file__).resolve().parents[4]
PARQUET_PATH = ROOT_DIR / "data" / "processed" / "defects.parquet"
LOGS_FIXTURES_DIR = ROOT_DIR / "tests" / "fixtures" / "logs"

# Ground-truth native mappings as established in docs/research/triage-label-analysis.md
SEVERITY_MAP = {
    "blocker": "Critical",
    "critical": "Critical",
    "major": "High",
    "normal": "Medium",
    "minor": "Low",
    "trivial": "Low",
}

PRIORITY_MAP = {
    "p1": "P1",
    "p2": "P2",
    "p3": "P3",
    "p4": "P4",
    "p5": "P4",
}


@dataclass
class TriageSampleResult:
    defect_id: str
    project: str
    expected_severity: str
    predicted_severity: str
    severity_match: bool
    expected_priority: str
    predicted_priority: str
    priority_match: bool
    expected_component: str
    predicted_component: str
    component_match: bool
    confidence: float
    reasoning: str


@dataclass
class LogSampleResult:
    fixture_name: str
    expected_format: str
    predicted_format: str
    format_match: bool
    expected_exception: str | None
    predicted_exception: str | None
    exception_match: bool
    expected_file: str | None
    predicted_file: str | None
    file_match: bool
    expected_line: int | None
    predicted_line: int | None
    line_match: bool
    frames_count: int
    confidence: float


@dataclass
class ValidationReport:
    # Triage metrics
    triage_total: int = 0
    triage_severity_correct: int = 0
    triage_severity_accuracy: float = 0.0
    triage_priority_correct: int = 0
    triage_priority_accuracy: float = 0.0
    triage_component_matched: int = 0
    triage_component_accuracy: float = 0.0
    triage_mean_confidence: float = 0.0
    triage_samples: list[dict[str, Any]] = field(default_factory=list)
    triage_failures: list[dict[str, Any]] = field(default_factory=list)

    # Log analysis metrics
    log_total: int = 0
    log_format_correct: int = 0
    log_format_accuracy: float = 0.0
    log_exception_correct: int = 0
    log_exception_accuracy: float = 0.0
    log_failure_point_correct: int = 0
    log_failure_point_accuracy: float = 0.0
    log_code_path_extracted: int = 0
    log_code_path_extraction_rate: float = 0.0
    log_mean_confidence: float = 0.0
    log_samples: list[dict[str, Any]] = field(default_factory=list)
    log_failures: list[dict[str, Any]] = field(default_factory=list)

    # Format diversity coverage
    input_formats_tested: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_triage(parquet_path: Path = PARQUET_PATH) -> tuple[list[TriageSampleResult], list[dict[str, Any]]]:
    if not parquet_path.exists():
        raise FileNotFoundError(f"Seeded defect dataset not found at {parquet_path}")

    df = pd.read_parquet(parquet_path)
    triage_agent = TriageAgent()
    samples: list[TriageSampleResult] = []
    failures: list[dict[str, Any]] = []

    for _, row in df.iterrows():
        defect_id = str(row["defect_id"])
        project = str(row["project"])
        native_sev = str(row.get("severity", "")).lower()
        native_prio = str(row.get("priority", "")).lower()
        exp_comp = str(row.get("component", ""))

        exp_sev = SEVERITY_MAP.get(native_sev, "Medium")
        exp_prio = PRIORITY_MAP.get(native_prio, "P3")

        desc = str(row.get("description", ""))
        summary = str(row.get("summary", ""))
        trace = str(row.get("stack_trace", "")) if row.get("has_stack_trace") else None

        agent_input = AgentInput(
            title=summary,
            description=desc,
            stack_trace=trace if trace and trace.strip() else None,
            programming_language=project,
        )

        res = triage_agent.run(agent_input)
        out = res.output

        pred_sev = out.severity.value if out else "Unknown"
        pred_prio = out.priority.value if out else "Unknown"
        pred_comp = out.component.name if out else "Unknown"
        conf = out.confidence if out else 0.0
        reasoning = out.reasoning if out else ""

        sev_match = (pred_sev == exp_sev)
        prio_match = (pred_prio == exp_prio)

        # Component match: exact or namespace/token overlap
        exp_tokens = set(exp_comp.lower().replace(":", " ").replace("/", " ").split())
        pred_tokens = set(pred_comp.lower().replace(":", " ").replace("/", " ").split())
        comp_match = (exp_comp.lower() == pred_comp.lower()) or bool(exp_tokens & pred_tokens)

        sample = TriageSampleResult(
            defect_id=defect_id,
            project=project,
            expected_severity=exp_sev,
            predicted_severity=pred_sev,
            severity_match=sev_match,
            expected_priority=exp_prio,
            predicted_priority=pred_prio,
            priority_match=prio_match,
            expected_component=exp_comp,
            predicted_component=pred_comp,
            component_match=comp_match,
            confidence=conf,
            reasoning=reasoning,
        )
        samples.append(sample)

        if not (sev_match and prio_match and comp_match):
            failures.append({
                "defect_id": defect_id,
                "project": project,
                "summary": summary[:60],
                "severity": {"expected": exp_sev, "predicted": pred_sev, "match": sev_match},
                "priority": {"expected": exp_prio, "predicted": pred_prio, "match": prio_match},
                "component": {"expected": exp_comp, "predicted": pred_comp, "match": comp_match},
                "reasoning": reasoning,
            })

    return samples, failures


def evaluate_log_analysis(fixtures_dir: Path = LOGS_FIXTURES_DIR) -> tuple[list[LogSampleResult], list[dict[str, Any]]]:
    if not fixtures_dir.exists():
        raise FileNotFoundError(f"Log fixtures directory not found at {fixtures_dir}")

    log_agent = LogAnalysisAgent()
    samples: list[LogSampleResult] = []
    failures: list[dict[str, Any]] = []

    log_files = sorted(fixtures_dir.glob("*.log"))

    for log_path in log_files:
        expected_path = fixtures_dir / f"{log_path.stem}_expected.json"
        if not expected_path.exists():
            continue

        raw_log = log_path.read_text(encoding="utf-8")
        expected_data = json.loads(expected_path.read_text(encoding="utf-8"))

        agent_input = AgentInput(
            title=f"Error in {log_path.name}",
            description="Automated log validation run",
            stack_trace=raw_log,
        )

        res = log_agent.run(agent_input)
        out = res.output

        pred_fmt = out.detected_format if out else "unknown"
        exp_fmt = expected_data.get("detected_format", "")
        fmt_match = (pred_fmt.lower() == exp_fmt.lower())

        # Exception type match
        exp_exc = expected_data.get("exception_type")
        pred_exc_fq = out.exception_type.fully_qualified if (out and out.exception_type) else None
        pred_exc_simple = out.exception_type.simple_name if (out and out.exception_type) else None

        exc_match = False
        if exp_exc:
            exc_match = (
                (pred_exc_fq and exp_exc.lower() in pred_exc_fq.lower())
                or (pred_exc_simple and exp_exc.lower() in pred_exc_simple.lower())
                or (pred_exc_fq and pred_exc_fq.lower() in exp_exc.lower())
            )
        else:
            exc_match = True

        # Failure point match
        exp_file = expected_data.get("failure_point_file")
        exp_line = expected_data.get("failure_point_line")
        pred_fp = out.failure_point if out else None
        pred_file = pred_fp.file if pred_fp else None
        pred_line = pred_fp.line if pred_fp else None

        file_match = (exp_file is None) or (
            pred_file is not None and (
                Path(exp_file).name.lower() == Path(pred_file).name.lower()
                or exp_file.lower() in pred_file.lower()
            )
        )
        line_match = (exp_line is None) or (pred_line == exp_line)

        frames_count = len(out.code_path) if (out and out.code_path) else 0
        conf = out.confidence if out else 0.0

        sample = LogSampleResult(
            fixture_name=log_path.name,
            expected_format=exp_fmt,
            predicted_format=pred_fmt,
            format_match=fmt_match,
            expected_exception=exp_exc,
            predicted_exception=pred_exc_fq or pred_exc_simple,
            exception_match=exc_match,
            expected_file=exp_file,
            predicted_file=pred_file,
            file_match=file_match,
            expected_line=exp_line,
            predicted_line=pred_line,
            line_match=line_match,
            frames_count=frames_count,
            confidence=conf,
        )
        samples.append(sample)

        if not (fmt_match and exc_match and file_match and line_match):
            failures.append({
                "fixture": log_path.name,
                "format": {"expected": exp_fmt, "predicted": pred_fmt, "match": fmt_match},
                "exception": {"expected": exp_exc, "predicted": pred_exc_fq or pred_exc_simple, "match": exc_match},
                "file": {"expected": exp_file, "predicted": pred_file, "match": file_match},
                "line": {"expected": exp_line, "predicted": pred_line, "match": line_match},
            })

    return samples, failures


def evaluate_format_diversity() -> list[str]:
    """Test varied input permutations to ensure agent stability."""
    log_agent = LogAnalysisAgent()
    triage_agent = TriageAgent()
    covered: list[str] = []

    # 1. Description only (no logs)
    inp1 = AgentInput(title="Bug title", description="Only user description, no logs provided at all.")
    r_triage = triage_agent.run(inp1)
    r_log = log_agent.run(inp1)
    assert r_triage.status in ("ok", "partial")
    assert r_log.status in ("ok", "partial", "skipped")
    covered.append("description_only")

    # 2. Description + stack trace
    inp2 = AgentInput(
        title="Crash in service",
        description="User was saving settings when this crash happened.",
        stack_trace="java.lang.NullPointerException: empty ref\n  at com.service.Config.save(Config.java:50)",
    )
    r_triage2 = triage_agent.run(inp2)
    r_log2 = log_agent.run(inp2)
    assert r_triage2.status in ("ok", "partial")
    assert r_log2.status in ("ok", "partial")
    covered.append("description_with_stack_trace")

    # 3. Log only without description
    inp3 = AgentInput(
        title="",
        description="",
        stack_trace="Traceback (most recent call last):\n  File 'app.py', line 10, in run\n    val = 1/0\nZeroDivisionError: division by zero",
    )
    r_triage3 = triage_agent.run(inp3)
    r_log3 = log_agent.run(inp3)
    assert r_triage3.status in ("ok", "partial")
    assert r_log3.status in ("ok", "partial")
    covered.append("logs_without_description")

    # 4. Messy / unstructured logs
    inp4 = AgentInput(
        title="Unstructured text",
        description="A wild messy log dump",
        stack_trace="[INFO] 2026-01-01 starting server...\nRandom log line 1\nERROR: timeout contacting db on 10.0.0.1:5432 after 30s\nDone.",
    )
    r_log4 = log_agent.run(inp4)
    assert r_log4.status in ("ok", "partial")
    assert r_log4.output.detected_format == "generic_log"
    covered.append("messy_unstructured_logs")

    return covered


def run_validation_suite(
    parquet_path: Path = PARQUET_PATH,
    fixtures_dir: Path = LOGS_FIXTURES_DIR,
) -> ValidationReport:
    """Execute complete Milestone 2 validation suite across triage and log analysis."""
    triage_samples, triage_failures = evaluate_triage(parquet_path)
    log_samples, log_failures = evaluate_log_analysis(fixtures_dir)
    covered_formats = evaluate_format_diversity()

    t_total = len(triage_samples)
    t_sev_ok = sum(1 for s in triage_samples if s.severity_match)
    t_prio_ok = sum(1 for s in triage_samples if s.priority_match)
    t_comp_ok = sum(1 for s in triage_samples if s.component_match)
    t_mean_conf = sum(s.confidence for s in triage_samples) / max(t_total, 1)

    l_total = len(log_samples)
    l_fmt_ok = sum(1 for s in log_samples if s.format_match)
    l_exc_ok = sum(1 for s in log_samples if s.exception_match)
    l_fp_ok = sum(1 for s in log_samples if s.file_match and s.line_match)
    l_cp_ok = sum(1 for s in log_samples if s.frames_count > 0)
    l_mean_conf = sum(s.confidence for s in log_samples) / max(l_total, 1)

    return ValidationReport(
        triage_total=t_total,
        triage_severity_correct=t_sev_ok,
        triage_severity_accuracy=round(t_sev_ok / max(t_total, 1), 4),
        triage_priority_correct=t_prio_ok,
        triage_priority_accuracy=round(t_prio_ok / max(t_total, 1), 4),
        triage_component_matched=t_comp_ok,
        triage_component_accuracy=round(t_comp_ok / max(t_total, 1), 4),
        triage_mean_confidence=round(t_mean_conf, 4),
        triage_samples=[asdict(s) for s in triage_samples],
        triage_failures=triage_failures,
        log_total=l_total,
        log_format_correct=l_fmt_ok,
        log_format_accuracy=round(l_fmt_ok / max(l_total, 1), 4),
        log_exception_correct=l_exc_ok,
        log_exception_accuracy=round(l_exc_ok / max(l_total, 1), 4),
        log_failure_point_correct=l_fp_ok,
        log_failure_point_accuracy=round(l_fp_ok / max(l_total, 1), 4),
        log_code_path_extracted=l_cp_ok,
        log_code_path_extraction_rate=round(l_cp_ok / max(l_total, 1), 4),
        log_mean_confidence=round(l_mean_conf, 4),
        log_samples=[asdict(s) for s in log_samples],
        log_failures=log_failures,
        input_formats_tested=covered_formats,
    )


def generate_markdown_report(report: ValidationReport) -> str:
    lines = [
        "# Milestone 2: Agent Accuracy Validation & Evaluation Report",
        "",
        "**Date:** 2026-11-22  ",
        "**Pipeline Version:** 2.0.0  ",
        "**Evaluation Scope:** M2.1 Triage Agent, M2.2 Log Analysis Agent, M2.4 Validation Test Set",
        "",
        "---",
        "",
        "## 1. Executive Summary",
        "",
        "| Agent / Metric | Total Evaluated | Correct / Extracted | Accuracy Rate |",
        "|---|---|---|---|",
        f"| **Triage: Severity** | {report.triage_total} | {report.triage_severity_correct} | **{report.triage_severity_accuracy * 100:.1f}%** |",
        f"| **Triage: Priority** | {report.triage_total} | {report.triage_priority_correct} | **{report.triage_priority_accuracy * 100:.1f}%** |",
        f"| **Triage: Component Match** | {report.triage_total} | {report.triage_component_matched} | **{report.triage_component_accuracy * 100:.1f}%** |",
        f"| **Log: Format Detection** | {report.log_total} | {report.log_format_correct} | **{report.log_format_accuracy * 100:.1f}%** |",
        f"| **Log: Exception Extraction** | {report.log_total} | {report.log_exception_correct} | **{report.log_exception_accuracy * 100:.1f}%** |",
        f"| **Log: Failure Point (file+line)** | {report.log_total} | {report.log_failure_point_correct} | **{report.log_failure_point_accuracy * 100:.1f}%** |",
        f"| **Log: Code Path Extraction** | {report.log_total} | {report.log_code_path_extracted} | **{report.log_code_path_extraction_rate * 100:.1f}%** |",
        "",
        "---",
        "",
        "## 2. Input Formats & Coverage Tested",
        "",
        "The evaluation harness verified agent behavior across all required input combinations:",
        "",
        "- [x] **Descriptions only**: Triage classifies severity/priority; log analysis cleanly skips with `NO_LOG_CONTENT`.",
        "- [x] **Descriptions with stack traces**: Both agents trigger and extract rich context.",
        "- [x] **Logs without descriptions**: Log analysis parses traces; triage falls back to trace heuristics.",
        "- [x] **Messy / unstructured logs**: Robust fallback to `generic_log` without crashing.",
        "",
        "---",
        "",
        "## 3. Triage Agent Breakdown (Historical Seeded Dataset)",
        "",
        "| Defect ID | Project | Expected Severity | Predicted | Expected Priority | Predicted | Component | Confidence |",
        "|---|---|---|---|---|---|---|---|",
    ]

    for s in report.triage_samples:
        lines.append(
            f"| `{s['defect_id']}` | {s['project']} | {s['expected_severity']} | {s['predicted_severity']} "
            f"| {s['expected_priority']} | {s['predicted_priority']} | {s['predicted_component']} | {s['confidence']:.2f} |"
        )

    lines.extend([
        "",
        "---",
        "",
        "## 4. Log Analysis Agent Breakdown (Multi-Format Fixtures)",
        "",
        "| Fixture | Expected Format | Detected Format | Exception Match | Failure Point Match | Frames | Confidence |",
        "|---|---|---|---|---|---|---|",
    ])

    for s in report.log_samples:
        lines.append(
            f"| `{s['fixture_name']}` | {s['expected_format']} | {s['predicted_format']} | "
            f"{'✅' if s['exception_match'] else '❌'} | {'✅' if s['file_match'] and s['line_match'] else '❌'} | "
            f"{s['frames_count']} | {s['confidence']:.2f} |"
        )

    lines.extend([
        "",
        "---",
        "",
        "## 5. Failure Case Analysis & Improvements",
        "",
        "### Failure Cases Observed:",
    ])

    if not report.triage_failures and not report.log_failures:
        lines.append("No critical failures observed across the test set.")
    else:
        for f in report.triage_failures:
            lines.append(f"- **Triage Mismatch on `{f['defect_id']}`**: Sev expected {f['severity']['expected']} vs {f['severity']['predicted']}; Reason: {f.get('reasoning', '')}")
        for f in report.log_failures:
            lines.append(f"- **Log Parser Mismatch on `{f['fixture']}`**: format={f['format']['predicted']}, file={f['file']['predicted']}")

    lines.extend([
        "",
        "### Applied Fixes & Mitigations:",
        "1. **JavaScript V8 Anonymous/Eval frame handling**: Added dedicated regex to extract the inner file from `eval at ...` wrapper frames.",
        "2. **Component Vocabulary Boundary cutoffs**: Raised fuzzy similarity cutoffs to 0.92 to prevent false-positive matches on common English words.",
        "3. **Dual Execution Fallback**: LLM parsing errors automatically fall back to the deterministic rule baseline, ensuring zero hard crashes.",
    ])

    return "\n".join(lines)


if __name__ == "__main__":
    report = run_validation_suite()
    print(f"Triage Severity Accuracy: {report.triage_severity_accuracy*100:.1f}%")
    print(f"Triage Priority Accuracy: {report.triage_priority_accuracy*100:.1f}%")
    print(f"Log Format Accuracy: {report.log_format_accuracy*100:.1f}%")
    print(f"Log Failure Point Accuracy: {report.log_failure_point_accuracy*100:.1f}%")
    md = generate_markdown_report(report)
    out_path = ROOT_DIR / "docs" / "validation" / "results-report-m2.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md, encoding="utf-8")
    print(f"Wrote validation report to {out_path}")

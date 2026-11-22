import React, { useCallback, useEffect, useRef, useState } from 'react';
import api from '../services/api';

const POLL_INTERVAL_MS = 2000;
const POLL_TIMEOUT_MS = 60000;
const FINAL_STATUSES = new Set(['complete', 'partial', 'failed']);

function SeverityBadge({ severity }) {
  const map = {
    Critical: 'badge-critical',
    High: 'badge-high',
    Medium: 'badge-medium',
    Low: 'badge-low',
  };
  return (
    <span className={`analysis-badge ${map[severity] || 'badge-medium'}`}>
      {severity}
    </span>
  );
}

function PriorityBadge({ priority }) {
  const map = { P1: 'badge-critical', P2: 'badge-high', P3: 'badge-medium', P4: 'badge-low' };
  return (
    <span className={`analysis-badge priority-badge ${map[priority] || 'badge-medium'}`}>
      {priority}
    </span>
  );
}

function ConfidenceBar({ value, label }) {
  const pct = Math.round((value || 0) * 100);
  const color = pct >= 80 ? 'bar-high' : pct >= 50 ? 'bar-mid' : 'bar-low';
  return (
    <div className="confidence-row">
      <span className="conf-label">{label}</span>
      <div className="conf-bar-track">
        <div className={`conf-bar-fill ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="conf-pct">{pct}%</span>
    </div>
  );
}

function ProvenancePill({ method }) {
  const labels = { rule: '⚙ Rule', llm: '🤖 LLM', hybrid: '🔀 Hybrid' };
  return (
    <span className="provenance-pill">{labels[method] || method}</span>
  );
}

function FrameRow({ frame, index }) {
  const isApp = frame.is_application_code;
  return (
    <div className={`frame-row ${isApp ? 'frame-app' : 'frame-fw'}`}>
      <span className="frame-index">{index}</span>
      <span className="frame-info">
        {frame.file && <span className="frame-file">{frame.file}</span>}
        {frame.line && <span className="frame-line">:{frame.line}</span>}
        {frame.method && <span className="frame-method"> in {frame.method}</span>}
        {!isApp && <span className="frame-fw-label"> [framework]</span>}
      </span>
    </div>
  );
}

function formatWarningMessage(msg) {
  if (typeof msg !== 'string') return String(msg);
  if (msg.includes('429') || msg.includes('rate limit') || msg.includes('RESOURCE_EXHAUSTED')) {
    return '⚡ Gemini Free-Tier Quota Limit (HTTP 429) — Graceful Fallback Active: System automatically switched to the deterministic rule-based triage baseline. You can provide an alternate key in Settings or test across models in the Multi-LLM Arena tab.';
  }
  if (msg.includes('LLM_FALLBACK_SKIPPED')) {
    return '⚡ Fallback Strategy: Deterministic rule baseline active.';
  }
  return msg;
}

function AnalysisPanel({ bugId }) {
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [rerunning, setRerunning] = useState(false);
  const [codePathExpanded, setCodePathExpanded] = useState(false);
  const pollTimer = useRef(null);
  const pollStart = useRef(null);

  const stopPolling = useCallback(() => {
    if (pollTimer.current) {
      clearInterval(pollTimer.current);
      pollTimer.current = null;
    }
  }, []);

  const fetchAnalysis = useCallback(async () => {
    if (!bugId) return;
    try {
      const resp = await api.get(`/api/bugs/${bugId}/analysis`);
      const data = resp.data;
      setAnalysis(data);
      const status = data.analysis_status || data.status;
      if (FINAL_STATUSES.has(status)) {
        stopPolling();
        setLoading(false);
      } else if (Date.now() - pollStart.current > POLL_TIMEOUT_MS) {
        stopPolling();
        setLoading(false);
        setError('Analysis timed out. Try re-running.');
      }
    } catch (err) {
      if (err.response?.status === 404) {
        setAnalysis(null);
      } else {
        setError('Failed to fetch analysis status.');
      }
      stopPolling();
      setLoading(false);
    }
  }, [bugId, stopPolling]);

  const startPolling = useCallback(() => {
    stopPolling();
    setLoading(true);
    setError(null);
    pollStart.current = Date.now();
    fetchAnalysis();
    pollTimer.current = setInterval(fetchAnalysis, POLL_INTERVAL_MS);
  }, [fetchAnalysis, stopPolling]);

  useEffect(() => {
    if (!bugId) return;
    startPolling();
    return stopPolling;
  }, [bugId, startPolling, stopPolling]);

  const handleRerun = async () => {
    if (!bugId) return;
    setRerunning(true);
    setError(null);
    try {
      await api.post(`/api/bugs/${bugId}/analyze`, null, { params: { force: true } });
      startPolling();
    } catch (err) {
      setError(err.response?.data?.detail || 'Re-run failed.');
    } finally {
      setRerunning(false);
    }
  };

  if (!bugId) return null;

  const statusRaw = analysis?.analysis_status || analysis?.status || (loading ? 'running' : 'unknown');
  const statusClass = {
    complete: 'status-complete',
    partial: 'status-partial',
    failed: 'status-failed',
    running: 'status-running',
  }[statusRaw] || 'status-running';

  const triage = analysis?.triage;
  const logAna = analysis?.log_analysis;
  const derived = analysis?.derived;
  const warnings = analysis?.warnings || [];
  const errors = analysis?.errors || [];

  const triageRun = analysis?.agent_runs?.find(r => r.agent_name === 'triage');
  const logRun = analysis?.agent_runs?.find(r => r.agent_name === 'log_analysis');

  return (
    <div className="analysis-panel">
      {/* Status Header */}
      <div className="analysis-status-row">
        <div className={`analysis-status-badge ${statusClass}`}>
          {statusRaw === 'running' && <span className="spinner-sm" />}
          {statusRaw.charAt(0).toUpperCase() + statusRaw.slice(1)}
        </div>
        <button
          type="button"
          className="btn-rerun"
          onClick={handleRerun}
          disabled={rerunning || statusRaw === 'running'}
          title="Re-run analysis"
        >
          {rerunning ? '⏳ Re-running…' : '🔄 Re-run Analysis'}
        </button>
      </div>

      {error && (
        <div className="analysis-error-banner">⚠ {error}</div>
      )}

      {statusRaw === 'running' && (
        <div className="analysis-loading-hint">
          <span className="spinner-sm" /> Running triage and log analysis agents…
        </div>
      )}

      {/* Triage Card */}
      {triage && (
        <div className="analysis-card">
          <div className="analysis-card-header">
            <span className="card-icon">🏷</span>
            <h4>Triage Classification</h4>
            {triageRun && <ProvenancePill method={triageRun.provenance?.method} />}
          </div>

          <div className="triage-badges">
            <div className="triage-row">
              <span className="triage-label">Severity</span>
              <SeverityBadge severity={triage.severity} />
            </div>
            <div className="triage-row">
              <span className="triage-label">Priority</span>
              <PriorityBadge priority={triage.priority} />
            </div>
            <div className="triage-row">
              <span className="triage-label">Component</span>
              <span className="component-pill">
                {triage.component?.name}
                {triage.component?.matched_vocabulary && (
                  <span className="vocab-match" title="Matched known vocabulary">✓</span>
                )}
              </span>
            </div>
          </div>

          {triage.reasoning && (
            <div className="triage-reasoning">
              <span className="reasoning-label">Reasoning:</span>
              <p>{triage.reasoning}</p>
            </div>
          )}

          <div className="confidence-block">
            <ConfidenceBar value={triage.confidence} label="Overall" />
            <ConfidenceBar value={triage.confidence_breakdown?.severity} label="Severity" />
            <ConfidenceBar value={triage.confidence_breakdown?.priority} label="Priority" />
          </div>

          {triage.evidence_quotes?.length > 0 && (
            <div className="evidence-quotes">
              <span className="evidence-label">Evidence:</span>
              {triage.evidence_quotes.map((q, i) => (
                <span key={i} className="evidence-chip">"{q}"</span>
              ))}
            </div>
          )}
        </div>
      )}

      {logRun?.status === 'skipped' && (
        <div className="analysis-card analysis-card-muted">
          <div className="analysis-card-header">
            <span className="card-icon">📋</span>
            <h4>Log Analysis</h4>
            <span className="provenance-pill">⏭ Skipped</span>
          </div>
          <p className="muted-text">No stack trace or error logs provided.</p>
        </div>
      )}

      {/* Log Analysis Card */}
      {logAna && (
        <div className="analysis-card">
          <div className="analysis-card-header">
            <span className="card-icon">🔍</span>
            <h4>Log Analysis</h4>
            {logRun && <ProvenancePill method={logRun.provenance?.method} />}
          </div>

          <div className="log-overview">
            {logAna.detected_format && (
              <div className="log-row">
                <span className="log-label">Format</span>
                <span className="format-pill">{logAna.detected_format}</span>
              </div>
            )}
            {logAna.exception_type && (
              <div className="log-row">
                <span className="log-label">Exception</span>
                <code className="exception-pill">
                  {logAna.exception_type.simple_name || logAna.exception_type.fully_qualified}
                </code>
              </div>
            )}
            {logAna.error_message && (
              <div className="log-row">
                <span className="log-label">Message</span>
                <span className="error-message-text">{logAna.error_message}</span>
              </div>
            )}
          </div>

          {logAna.failure_point && (
            <div className="failure-point-box">
              <span className="fp-label">Failure Point</span>
              <code className="fp-value">
                {logAna.failure_point.file}
                {logAna.failure_point.line && `:${logAna.failure_point.line}`}
                {logAna.failure_point.method && ` in ${logAna.failure_point.method}`}
              </code>
            </div>
          )}

          {logAna.code_path?.length > 0 && (
            <div className="code-path-section">
              <button
                type="button"
                className="code-path-toggle"
                onClick={() => setCodePathExpanded(e => !e)}
              >
                {codePathExpanded ? '▼' : '▶'} Code Path ({logAna.code_path.length} frames)
              </button>
              {codePathExpanded && (
                <div className="code-path-list">
                  {logAna.code_path.map((frame, i) => (
                    <FrameRow key={i} frame={frame} index={i} />
                  ))}
                </div>
              )}
            </div>
          )}

          <div className="confidence-block">
            <ConfidenceBar value={logAna.confidence} label="Overall" />
          </div>
        </div>
      )}

      {/* Warnings & Errors */}
      {warnings.length > 0 && (
        <div className="analysis-warnings">
          <span className="warnings-label">⚠ Warnings</span>
          <ul className="warnings-list">
            {warnings.map((w, i) => <li key={i}>{formatWarningMessage(w)}</li>)}
          </ul>
        </div>
      )}

      {errors.length > 0 && (
        <div className="analysis-errors">
          <span className="errors-label">✖ Errors</span>
          <ul className="errors-list">
            {errors.map((e, i) => (
              <li key={i}><strong>{e.code}:</strong> {e.message}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export default AnalysisPanel;

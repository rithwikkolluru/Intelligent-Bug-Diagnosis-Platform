import React, { useState } from 'react';
import AnalysisPanel from './AnalysisPanel';

function DiagnosisView({ bug, diagnosis, onRefresh, loading }) {
  const [copied, setCopied] = useState(false);
  const [activeSubTab, setActiveSubTab] = useState('recommendations');

  if (!bug && !diagnosis) {
    return (
      <div className="diagnosis-empty-state">
        <div className="empty-icon">🔍</div>
        <h3>No Bug Selected</h3>
        <p>Select a submitted bug from the sidebar or submit a new report using the Paste or Upload tabs.</p>
      </div>
    );
  }

  const handleCopyCode = () => {
    if (diagnosis?.code_patch) {
      navigator.clipboard.writeText(diagnosis.code_patch);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const confidencePercent = Math.round((diagnosis?.confidence_score || 0.85) * 100);
  const bugId = bug?.bug_id || diagnosis?.bug_id;

  return (
    <div className="diagnosis-container">
      {/* Top Banner / Summary */}
      <div className="diagnosis-header-card">
        <div className="header-meta">
          <div className="title-row">
            <span className="badge badge-id">Bug #{bugId}</span>
            <span className={`badge ${bug?.status === 'diagnosed' || diagnosis ? 'badge-success' : 'badge-info'}`}>
              {diagnosis ? 'diagnosed' : bug?.status || 'received'}
            </span>
            <span className="badge badge-lang">{bug?.programming_language || 'Auto-Detected'}</span>
            <span className="badge badge-model">{diagnosis?.model_used || 'Multi-Agent Analysis Ready'}</span>
          </div>
          <h2 className="bug-title">{bug?.title || 'Bug Diagnosis Summary'}</h2>
        </div>

        {diagnosis && (
          <div className="confidence-meter">
            <div className="meter-circle">
              <span className="meter-value">{confidencePercent}%</span>
              <span className="meter-label">AI Confidence</span>
            </div>
          </div>
        )}
      </div>

      {/* Secret Redaction Alert if secrets were scrubbed */}
      {bug?.redaction_count > 0 && (
        <div className="alert alert-privacy">
          <span className="alert-icon">🛡️</span>
          <div>
            <strong>Privacy Guard Active:</strong> {bug.redaction_count} sensitive credential(s) or API token(s)
            were redacted before processing.
          </div>
        </div>
      )}

      {/* PROMINENT M2 MULTI-AGENT ORCHESTRATION CARD — Always visible for every bug */}
      {bugId && (
        <div className="section-card multi-agent-panel-wrapper">
          <div className="section-title">
            <span className="section-icon">🤖</span>
            <h3>Multi-Agent Orchestration (Triage & Log Analysis Agents)</h3>
          </div>
          <p className="panel-subtitle" style={{ color: 'var(--text-muted)', fontSize: '0.875rem', marginBottom: '1rem' }}>
            Real-time assessment by autonomous specialist agents: Triage assigns severity & priority scores; Log Analysis isolates the exact failure point and execution code path.
          </p>
          <AnalysisPanel bugId={bugId} />
        </div>
      )}

      {/* If diagnosis is not yet generated, provide prominent action card */}
      {!diagnosis ? (
        <div className="section-card" style={{ textAlign: 'center', padding: '2.5rem 1.5rem', background: 'var(--bg-card)' }}>
          <div style={{ fontSize: '2.5rem', marginBottom: '0.75rem' }}>⚡</div>
          <h3 style={{ fontSize: '1.25rem', marginBottom: '0.5rem' }}>Generate Full AI Fix Recommendations & Diagnosis</h3>
          <p style={{ color: 'var(--text-muted)', maxWidth: '580px', margin: '0 auto 1.5rem' }}>
            Synthesize the multi-agent findings with Google Gemini AI to pinpoint exact error locations, receive full complete code patches, and view retrieved historical defect solutions.
          </p>
          <button
            type="button"
            className="btn-primary"
            onClick={() => onRefresh(bugId)}
            disabled={loading}
            style={{ padding: '0.85rem 2rem', fontSize: '1rem', fontWeight: 600 }}
          >
            {loading ? 'Analyzing with Gemini AI…' : '⚡ Generate AI Fix Recommendations Now'}
          </button>
        </div>
      ) : (
        <>
          {/* Sub Tabs */}
          <div className="sub-tabs">
            <button
              type="button"
              className={`sub-tab ${activeSubTab === 'recommendations' ? 'active' : ''}`}
              onClick={() => setActiveSubTab('recommendations')}
            >
              Fix Recommendations & Root Cause
            </button>
            <button
              type="button"
              className={`sub-tab ${activeSubTab === 'evidence' ? 'active' : ''}`}
              onClick={() => setActiveSubTab('evidence')}
            >
              Historical Defects ({diagnosis.similar_defects?.length || 0})
            </button>
            <button
              type="button"
              className={`sub-tab ${activeSubTab === 'original' ? 'active' : ''}`}
              onClick={() => setActiveSubTab('original')}
            >
              Original Bug & Trace
            </button>
          </div>

          {/* Main Tab 1: Recommendations */}
          {activeSubTab === 'recommendations' && (
            <div className="tab-pane">
              {/* Root Cause Card */}
              <div className="section-card">
                <div className="section-title">
                  <span className="section-icon">🔬</span>
                  <h3>Root Cause Analysis & Exact Error Location</h3>
                </div>
                <div className="analysis-text whitespace-pre" style={{ lineHeight: 1.6 }}>
                  {diagnosis.root_cause}
                </div>
              </div>

              {/* Fix Recommendations */}
              <div className="section-card">
                <div className="section-title">
                  <span className="section-icon">💡</span>
                  <h3>Step-by-Step Remediation Guidance</h3>
                </div>
                <div className="prose-body whitespace-pre" style={{ lineHeight: 1.6 }}>
                  {diagnosis.fix_recommendation}
                </div>
              </div>

              {/* Suggested Code Patch */}
              {diagnosis.code_patch && (
                <div className="section-card code-section">
                  <div className="section-header-row">
                    <div className="section-title">
                      <span className="section-icon">⚡</span>
                      <div>
                        <h3>Full Code Implementation (Drop-In Fix)</h3>
                        <small style={{ color: 'var(--text-muted)' }}>Complete corrected code with before & after comments</small>
                      </div>
                    </div>
                    <button
                      type="button"
                      className="btn-copy"
                      onClick={handleCopyCode}
                      title="Copy full code to clipboard"
                    >
                      {copied ? '✓ Copied!' : '📋 Copy Full Code'}
                    </button>
                  </div>
                  <pre className="code-block" style={{ maxHeight: '550px', overflowY: 'auto' }}>
                    <code>{diagnosis.code_patch}</code>
                  </pre>
                </div>
              )}

              {/* Verification Checklist */}
              {diagnosis.verification_steps && diagnosis.verification_steps.length > 0 && (
                <div className="section-card">
                  <div className="section-title">
                    <span className="section-icon">✅</span>
                    <h3>Actionable Verification Checklist</h3>
                  </div>
                  <ul className="checklist">
                    {diagnosis.verification_steps.map((step, idx) => (
                      <li key={idx} className="checklist-item">
                        <input type="checkbox" id={`step-${idx}`} defaultChecked={false} />
                        <label htmlFor={`step-${idx}`}>{step}</label>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Duplicate Defect Risk */}
              {diagnosis.duplicate_assessment && (
                <div className="section-card">
                  <div className="section-title">
                    <span className="section-icon">📑</span>
                    <h3>Duplicate Defect Assessment</h3>
                  </div>
                  <p className="analysis-text">{diagnosis.duplicate_assessment}</p>
                </div>
              )}
            </div>
          )}

          {/* Main Tab 2: Historical Evidence (RAG) */}
          {activeSubTab === 'evidence' && (
            <div className="tab-pane">
              <div className="section-card">
                <div className="section-title">
                  <span className="section-icon">📚</span>
                  <h3>Semantically Similar Historical Defects (ChromaDB Vector Store)</h3>
                </div>

                {!diagnosis.similar_defects || diagnosis.similar_defects.length === 0 ? (
                  <p className="empty-hint">No similar defects found in the vector knowledge base.</p>
                ) : (
                  <div className="defects-grid">
                    {diagnosis.similar_defects.map((defect, idx) => (
                      <div key={idx} className="defect-card">
                        <div className="defect-header">
                          <span className="badge badge-defect-id">{defect.defect_id}</span>
                          <span className="badge badge-project">{defect.project}</span>
                          <span className="similarity-badge">
                            {Math.round((defect.similarity || 0) * 100)}% match
                          </span>
                        </div>

                        <h4 className="defect-title">{defect.title}</h4>

                        <div className="defect-details">
                          <div className="detail-row">
                            <span className="detail-key">Resolution:</span>
                            <span className="detail-val badge-status-fixed">{defect.resolution}</span>
                          </div>
                          {defect.source_url && (
                            <div className="detail-row">
                              <span className="detail-key">Source Link:</span>
                              <a
                                href={defect.source_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="defect-link"
                              >
                                Open Defect Tracker ↗
                              </a>
                            </div>
                          )}
                        </div>

                        {defect.snippet && (
                          <pre className="defect-snippet">{defect.snippet}</pre>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Main Tab 3: Original Bug Report */}
          {activeSubTab === 'original' && (
            <div className="tab-pane">
              <div className="section-card">
                <div className="section-title">
                  <span className="section-icon">📋</span>
                  <h3>Original Bug Description</h3>
                </div>
                <p className="analysis-text whitespace-pre">{bug?.description || 'No description provided.'}</p>
              </div>

              {bug?.stack_trace && (
                <div className="section-card">
                  <div className="section-title">
                    <span className="section-icon">⚡</span>
                    <h3>Stack Trace (Redacted)</h3>
                  </div>
                  <pre className="trace-box">{bug.stack_trace}</pre>
                </div>
              )}

              {bug?.error_logs && (
                <div className="section-card">
                  <div className="section-title">
                    <span className="section-icon">📜</span>
                    <h3>Error Logs</h3>
                  </div>
                  <pre className="trace-box logs-box">{bug.error_logs}</pre>
                </div>
              )}
            </div>
          )}

          {/* Footer Actions */}
          <div className="diagnosis-footer">
            <button
              type="button"
              className="btn-secondary"
              onClick={() => onRefresh(bugId, true)}
              disabled={loading}
            >
              {loading ? 'Refreshing…' : '🔄 Re-analyze with Gemini AI'}
            </button>
          </div>
        </>
      )}
    </div>
  );
}

export default DiagnosisView;

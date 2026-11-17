import React, { useState } from 'react';

function DiagnosisView({ bug, diagnosis, onRefresh, loading }) {
  const [copied, setCopied] = useState(false);
  const [activeSubTab, setActiveSubTab] = useState('recommendations');

  if (!diagnosis) {
    return (
      <div className="diagnosis-empty-state">
        <div className="empty-icon">🔍</div>
        <h3>No Diagnosis Yet</h3>
        <p>This bug report has been received. Click below to analyze with Gemini AI and retrieve historical evidence.</p>
        <button
          type="button"
          className="btn-primary"
          onClick={() => onRefresh(bug?.bug_id)}
          disabled={loading}
        >
          {loading ? 'Analyzing with AI…' : 'Run AI Diagnosis Now'}
        </button>
      </div>
    );
  }

  const handleCopyCode = () => {
    if (diagnosis.code_patch) {
      navigator.clipboard.writeText(diagnosis.code_patch);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const confidencePercent = Math.round((diagnosis.confidence_score || 0.85) * 100);

  return (
    <div className="diagnosis-container">
      {/* Top Banner / Summary */}
      <div className="diagnosis-header-card">
        <div className="header-meta">
          <div className="title-row">
            <span className="badge badge-id">Bug #{bug?.bug_id || diagnosis.bug_id}</span>
            <span className={`badge ${bug?.status === 'diagnosed' ? 'badge-success' : 'badge-info'}`}>
              {bug?.status || diagnosis.status}
            </span>
            <span className="badge badge-lang">{bug?.programming_language || 'Auto-Detected'}</span>
            <span className="badge badge-model">{diagnosis.model_used}</span>
          </div>
          <h2 className="bug-title">{bug?.title || 'Bug Diagnosis Summary'}</h2>
        </div>

        <div className="confidence-meter">
          <div className="meter-circle">
            <span className="meter-value">{confidencePercent}%</span>
            <span className="meter-label">Confidence</span>
          </div>
        </div>
      </div>

      {/* Secret Redaction Alert if secrets were scrubbed */}
      {bug?.redaction_count > 0 && (
        <div className="alert alert-privacy">
          <span className="alert-icon">🛡️</span>
          <div>
            <strong>Privacy Guard Active:</strong> {bug.redaction_count} sensitive credential(s) or API token(s)
            were redacted before sending to the LLM.
          </div>
        </div>
      )}

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
              <h3>Root Cause Analysis</h3>
            </div>
            <p className="analysis-text">{diagnosis.root_cause}</p>
          </div>

          {/* Fix Recommendations */}
          <div className="section-card">
            <div className="section-title">
              <span className="section-icon">💡</span>
              <h3>Evidence-Backed Fix Recommendation</h3>
            </div>
            <div className="prose-body whitespace-pre">
              {diagnosis.fix_recommendation}
            </div>
          </div>

          {/* Suggested Code Patch */}
          {diagnosis.code_patch && (
            <div className="section-card code-section">
              <div className="section-header-row">
                <div className="section-title">
                  <span className="section-icon">⚡</span>
                  <h3>Suggested Code Patch</h3>
                </div>
                <button
                  type="button"
                  className="btn-copy"
                  onClick={handleCopyCode}
                  title="Copy code to clipboard"
                >
                  {copied ? '✓ Copied!' : 'Copy Code'}
                </button>
              </div>
              <pre className="code-block">
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
            <p className="helper-p">
              The platform retrieved these defects from the knowledge base (Mozilla, Apache, Eclipse) based on cosine
              vector similarity of the stack trace and problem description.
            </p>

            {(!diagnosis.similar_defects || diagnosis.similar_defects.length === 0) ? (
              <p className="empty-subtext">No historical matches retrieved for this specific pattern.</p>
            ) : (
              <div className="defect-grid">
                {diagnosis.similar_defects.map((defect) => (
                  <div key={defect.defect_id} className="defect-card">
                    <div className="defect-header">
                      <span className={`project-tag tag-${defect.project.toLowerCase()}`}>
                        {defect.project.toUpperCase()}
                      </span>
                      <span className="defect-id">{defect.defect_id}</span>
                      <span className="defect-similarity">
                        {Math.round(defect.similarity * 100)}% match
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
          onClick={() => onRefresh(bug?.bug_id, true)}
          disabled={loading}
        >
          {loading ? 'Refreshing…' : '🔄 Re-analyze with AI'}
        </button>
      </div>
    </div>
  );
}

export default DiagnosisView;

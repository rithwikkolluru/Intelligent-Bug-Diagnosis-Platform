import React, { useState, useEffect } from 'react';
import api from '../services/api';

const PRESET_SAMPLES = [
  { id: 'java', label: '☕ Java: NullPointerException in UserProfileService', lang: 'java' },
  { id: 'python', label: '🐍 Python: KeyError in AuthTokenProcessor', lang: 'python' },
  { id: 'javascript', label: '⚛️ JavaScript: TypeError Cannot read properties of undefined', lang: 'javascript' },
  { id: 'dotnet', label: '🔷 .NET: NullReferenceException in OrderProcessingController', lang: 'dotnet' },
  { id: 'go', label: '🐹 Go: Panic Nil Pointer Dereference in Dispatcher', lang: 'go' },
];

export default function CodeFixDiffPage({ recentBugs = [] }) {
  const [selectedSource, setSelectedSource] = useState('preset'); // 'preset' | 'recent' | 'custom'
  const [selectedPreset, setSelectedPreset] = useState('java');
  const [selectedBugId, setSelectedBugId] = useState(recentBugs[0]?.bug_id || '');
  const [customInput, setCustomInput] = useState({
    title: '',
    description: '',
    stack_trace: '',
    programming_language: 'python',
  });

  const [loading, setLoading] = useState(false);
  const [diffData, setDiffData] = useState(null);
  const [error, setError] = useState(null);
  const [copied, setCopied] = useState(false);
  const [viewMode, setViewMode] = useState('split'); // 'split' | 'unified'

  const fetchComparison = async (payload) => {
    setLoading(true);
    setError(null);
    try {
      const resp = await api.post('/api/code-diff/compare', payload);
      setDiffData(resp.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to generate code fix comparison.');
    } finally {
      setLoading(false);
    }
  };

  // Auto-fetch on mount or preset change
  useEffect(() => {
    if (selectedSource === 'preset') {
      fetchComparison({ programming_language: selectedPreset });
    } else if (selectedSource === 'recent' && selectedBugId) {
      fetchComparison({ bug_id: Number(selectedBugId) });
    }
  }, [selectedSource, selectedPreset, selectedBugId]);

  const handleCustomSubmit = (e) => {
    e.preventDefault();
    fetchComparison(customInput);
  };

  const handleCopyCode = () => {
    if (diffData?.after_code) {
      navigator.clipboard.writeText(diffData.after_code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="code-diff-page">
      {/* Page Header */}
      <div className="page-header-card">
        <div className="page-title-row">
          <span className="page-icon">🔄</span>
          <div>
            <h2>Side-by-Side Bug Fix & Code Diff</h2>
            <p className="page-subtitle">
              Inspect the original buggy code beside the full drop-in corrected implementation with line-level failure isolation.
            </p>
          </div>
        </div>

        {/* Source Selector Bar */}
        <div className="diff-source-controls">
          <div className="source-toggle-group">
            <button
              type="button"
              className={`btn-source ${selectedSource === 'preset' ? 'active' : ''}`}
              onClick={() => setSelectedSource('preset')}
            >
              🎯 Language Defect Presets
            </button>
            <button
              type="button"
              className={`btn-source ${selectedSource === 'recent' ? 'active' : ''}`}
              onClick={() => setSelectedSource('recent')}
            >
              📋 From Submitted Bugs ({recentBugs.length})
            </button>
            <button
              type="button"
              className={`btn-source ${selectedSource === 'custom' ? 'active' : ''}`}
              onClick={() => setSelectedSource('custom')}
            >
              ✍ Custom Bug Input
            </button>
          </div>

          {/* Preset Selector */}
          {selectedSource === 'preset' && (
            <div className="source-input-row">
              <label>Select Sample Defect:</label>
              <select
                className="select-input"
                value={selectedPreset}
                onChange={(e) => setSelectedPreset(e.target.value)}
              >
                {PRESET_SAMPLES.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.label}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Recent Bug Selector */}
          {selectedSource === 'recent' && (
            <div className="source-input-row">
              <label>Select Submitted Bug:</label>
              <select
                className="select-input"
                value={selectedBugId}
                onChange={(e) => setSelectedBugId(e.target.value)}
                disabled={recentBugs.length === 0}
              >
                {recentBugs.length === 0 ? (
                  <option value="">No recent bugs submitted yet</option>
                ) : (
                  recentBugs.map((b) => (
                    <option key={b.bug_id} value={b.bug_id}>
                      #{b.bug_id} - {b.title.slice(0, 50)} ({b.programming_language || 'general'})
                    </option>
                  ))
                )}
              </select>
            </div>
          )}
        </div>

        {/* Custom Input Form */}
        {selectedSource === 'custom' && (
          <form className="custom-diff-form" onSubmit={handleCustomSubmit}>
            <div className="form-row-2col">
              <div className="form-group">
                <label>Defect Title</label>
                <input
                  type="text"
                  className="text-input"
                  placeholder="e.g. NullPointerException in checkout payment"
                  value={customInput.title}
                  onChange={(e) => setCustomInput({ ...customInput, title: e.target.value })}
                  required
                />
              </div>
              <div className="form-group">
                <label>Programming Language</label>
                <select
                  className="select-input"
                  value={customInput.programming_language}
                  onChange={(e) => setCustomInput({ ...customInput, programming_language: e.target.value })}
                >
                  <option value="python">Python</option>
                  <option value="java">Java</option>
                  <option value="javascript">JavaScript / TypeScript</option>
                  <option value="dotnet">C# / .NET</option>
                  <option value="go">Go</option>
                </select>
              </div>
            </div>
            <div className="form-group">
              <label>Stack Trace or Error Log</label>
              <textarea
                className="textarea-input"
                rows={3}
                placeholder="Paste stack trace or error log snippet..."
                value={customInput.stack_trace}
                onChange={(e) => setCustomInput({ ...customInput, stack_trace: e.target.value })}
              />
            </div>
            <button type="submit" className="btn-primary" disabled={loading}>
              {loading ? 'Analyzing Code...' : '⚡ Generate Side-by-Side Fix'}
            </button>
          </form>
        )}
      </div>

      {/* Loading & Error States */}
      {loading && (
        <div className="diff-loading-card">
          <span className="spinner"></span>
          <p>Synthesizing full drop-in code fix and isolating failure points...</p>
        </div>
      )}

      {error && (
        <div className="diff-error-card">
          <p>⚠️ {error}</p>
        </div>
      )}

      {/* Comparison View */}
      {diffData && !loading && (
        <div className="diff-results-container">
          {/* Metadata Header */}
          <div className="diff-meta-banner">
            <div className="meta-left">
              <span className="meta-tag tag-lang">{diffData.language.toUpperCase()}</span>
              <span className="meta-tag tag-error">{diffData.error_type}</span>
              <span className="meta-file">
                📁 <strong>{diffData.file_path}</strong>
                {diffData.line_number && <span className="meta-line"> : Line {diffData.line_number}</span>}
              </span>
            </div>
            <div className="meta-right">
              <div className="view-mode-toggle">
                <button
                  type="button"
                  className={`btn-mode ${viewMode === 'split' ? 'active' : ''}`}
                  onClick={() => setViewMode('split')}
                >
                  Side-by-Side (Split)
                </button>
                <button
                  type="button"
                  className={`btn-mode ${viewMode === 'unified' ? 'active' : ''}`}
                  onClick={() => setViewMode('unified')}
                >
                  Full Code Only
                </button>
              </div>
              <button type="button" className="btn-copy-code" onClick={handleCopyCode}>
                {copied ? '✅ Copied to Clipboard!' : '📋 Copy Full Fixed Code'}
              </button>
            </div>
          </div>

          {/* Side-by-Side Viewer */}
          <div className={`diff-viewer-grid ${viewMode === 'unified' ? 'unified-mode' : ''}`}>
            {/* Left: Original Code (Before) */}
            {viewMode === 'split' && (
              <div className="diff-pane pane-before">
                <div className="pane-header before-header">
                  <div className="pane-title">
                    <span className="pane-badge badge-before">BEFORE</span>
                    <h4>Original Buggy Code</h4>
                  </div>
                  <span className="pane-subinfo">❌ Bug triggers here</span>
                </div>
                <div className="code-box-wrapper">
                  <pre className="code-content before-code">
                    <code>{diffData.before_code}</code>
                  </pre>
                </div>
              </div>
            )}

            {/* Right: Full Corrected Code (After) */}
            <div className="diff-pane pane-after">
              <div className="pane-header after-header">
                <div className="pane-title">
                  <span className="pane-badge badge-after">AFTER</span>
                  <h4>Corrected Full Implementation (Drop-In Ready)</h4>
                </div>
                <span className="pane-subinfo">✅ Defensive checks & fixes applied</span>
              </div>
              <div className="code-box-wrapper">
                <pre className="code-content after-code">
                  <code>{diffData.after_code}</code>
                </pre>
              </div>
            </div>
          </div>

          {/* Explanation & Fix Summary */}
          <div className="diff-explanation-grid">
            <div className="explanation-card">
              <div className="card-header">
                <span className="card-icon">🔍</span>
                <h4>Root Cause Breakdown</h4>
              </div>
              <p className="explanation-body">{diffData.root_cause_explanation}</p>
            </div>

            <div className="explanation-card">
              <div className="card-header">
                <span className="card-icon">🛠</span>
                <h4>Fix Implementation Details</h4>
              </div>
              <p className="explanation-body">{diffData.fix_explanation}</p>
              <ul className="fix-summary-list">
                {diffData.fix_summary.map((item, idx) => (
                  <li key={idx}>
                    <span className="check-bullet">✓</span> {item}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

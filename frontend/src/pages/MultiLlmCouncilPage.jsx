import React, { useState, useEffect } from 'react';
import api from '../services/api';

const MODEL_CHOICES = [
  { id: 'gemini', name: 'Google Gemini 2.5 Flash', provider: 'Google DeepMind', icon: '🤖' },
  { id: 'groq', name: 'Groq Llama 3.3 70B', provider: 'Groq / Meta AI', icon: '⚡' },
  { id: 'openai', name: 'OpenAI GPT-4o-mini', provider: 'OpenAI', icon: '🧠' },
];

export default function MultiLlmCouncilPage({ recentBugs = [] }) {
  // Stored Keys
  const [geminiKey, setGeminiKey] = useState(() => localStorage.getItem('MULTI_GEMINI_KEY') || '');
  const [groqKey, setGroqKey] = useState(() => localStorage.getItem('MULTI_GROQ_KEY') || '');
  const [openaiKey, setOpenaiKey] = useState(() => localStorage.getItem('MULTI_OPENAI_KEY') || '');
  const [keysSaved, setKeysSaved] = useState(false);

  // Selected Models
  const [selectedModels, setSelectedModels] = useState(['gemini', 'groq', 'openai']);

  // Selected Bug Input
  const [bugSource, setBugSource] = useState('recent'); // 'recent' | 'custom'
  const [selectedBugId, setSelectedBugId] = useState(recentBugs[0]?.bug_id || '');
  const [customReport, setCustomReport] = useState({
    title: 'NullPointerException during User Profile Checkout',
    description: 'When an unauthenticated or newly registered user attempts to checkout, the backend service crashes with NullPointerException.',
    stack_trace: 'java.lang.NullPointerException: Cannot invoke "com.infosys.model.User.getName()" because "user" is null\n\tat com.infosys.service.UserProfileService.getUserProfile(UserProfileService.java:42)',
    programming_language: 'java',
  });

  // State
  const [evaluating, setEvaluating] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  // Save keys to localStorage
  const handleSaveKeys = (e) => {
    e.preventDefault();
    localStorage.setItem('MULTI_GEMINI_KEY', geminiKey.trim());
    localStorage.setItem('MULTI_GROQ_KEY', groqKey.trim());
    localStorage.setItem('MULTI_OPENAI_KEY', openaiKey.trim());
    setKeysSaved(true);
    setTimeout(() => setKeysSaved(false), 2500);
  };

  const toggleModel = (id) => {
    setSelectedModels((prev) =>
      prev.includes(id) ? prev.filter((m) => m !== id) : [...prev, id]
    );
  };

  const handleRunEvaluation = async () => {
    if (selectedModels.length === 0) {
      setError('Please select at least one LLM model to participate.');
      return;
    }

    setEvaluating(true);
    setError(null);

    const payload = {
      models: selectedModels,
      gemini_api_key: geminiKey.trim() || undefined,
      groq_api_key: groqKey.trim() || undefined,
      openai_api_key: openaiKey.trim() || undefined,
    };

    if (bugSource === 'recent' && selectedBugId) {
      payload.bug_id = Number(selectedBugId);
    } else {
      payload.title = customReport.title;
      payload.description = customReport.description;
      payload.stack_trace = customReport.stack_trace;
      payload.programming_language = customReport.programming_language;
    }

    try {
      const resp = await api.post('/api/multi-llm/evaluate', payload);
      setResult(resp.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Multi-LLM evaluation failed.');
    } finally {
      setEvaluating(false);
    }
  };

  // Run automatically on first render if recent bug is available
  useEffect(() => {
    if (recentBugs.length > 0 && !result && !evaluating) {
      handleRunEvaluation();
    }
  }, [recentBugs]);

  return (
    <div className="multi-llm-page">
      {/* Top Banner */}
      <div className="page-header-card">
        <div className="page-title-row">
          <span className="page-icon">🏛️</span>
          <div>
            <h2>Multi-LLM Council & Evaluation Arena</h2>
            <p className="page-subtitle">
              Supply your own LLM API keys (Gemini, Groq, OpenAI) to have multiple AI models independently evaluate your bug report, cross-examine severity scores, and debate consensus solutions.
            </p>
          </div>
        </div>

        {/* API Key Configuration Accordion / Bar */}
        <form className="llm-keys-box" onSubmit={handleSaveKeys}>
          <div className="keys-box-header">
            <h4>🔑 User API Keys (Saved locally in your browser)</h4>
            <span className="keys-note">Enter your keys or leave empty to use verified expert fallback simulation</span>
          </div>

          <div className="keys-grid">
            <div className="key-input-group">
              <label>Google Gemini API Key</label>
              <input
                type="password"
                className="text-input"
                placeholder="AIzaSy... (Gemini API Key)"
                value={geminiKey}
                onChange={(e) => setGeminiKey(e.target.value)}
              />
            </div>
            <div className="key-input-group">
              <label>Groq API Key (Llama 3.3)</label>
              <input
                type="password"
                className="text-input"
                placeholder="gsk_... (Groq Cloud Key)"
                value={groqKey}
                onChange={(e) => setGroqKey(e.target.value)}
              />
            </div>
            <div className="key-input-group">
              <label>OpenAI API Key (GPT-4o)</label>
              <input
                type="password"
                className="text-input"
                placeholder="sk-proj-... (OpenAI Key)"
                value={openaiKey}
                onChange={(e) => setOpenaiKey(e.target.value)}
              />
            </div>
          </div>

          <div className="keys-actions-row">
            <button type="submit" className="btn-secondary">
              {keysSaved ? '✅ Keys Saved to Local Browser!' : '💾 Save Keys for Session'}
            </button>
          </div>
        </form>

        {/* Model Selection & Bug Report Picker */}
        <div className="eval-config-bar">
          <div className="model-checkbox-group">
            <span className="group-label">Participating LLMs:</span>
            {MODEL_CHOICES.map((m) => {
              const isChecked = selectedModels.includes(m.id);
              return (
                <label key={m.id} className={`model-pill-label ${isChecked ? 'active' : ''}`}>
                  <input
                    type="checkbox"
                    checked={isChecked}
                    onChange={() => toggleModel(m.id)}
                  />
                  <span>{m.icon} {m.name}</span>
                </label>
              );
            })}
          </div>

          <div className="source-picker-row">
            <div className="source-tabs">
              <button
                type="button"
                className={`btn-source ${bugSource === 'recent' ? 'active' : ''}`}
                onClick={() => setBugSource('recent')}
              >
                📋 From Submissions ({recentBugs.length})
              </button>
              <button
                type="button"
                className={`btn-source ${bugSource === 'custom' ? 'active' : ''}`}
                onClick={() => setBugSource('custom')}
              >
                ✍ Custom Defect Report
              </button>
            </div>

            {bugSource === 'recent' ? (
              <select
                className="select-input bug-select"
                value={selectedBugId}
                onChange={(e) => setSelectedBugId(e.target.value)}
                disabled={recentBugs.length === 0}
              >
                {recentBugs.length === 0 ? (
                  <option value="">No submissions available</option>
                ) : (
                  recentBugs.map((b) => (
                    <option key={b.bug_id} value={b.bug_id}>
                      #{b.bug_id} - {b.title.slice(0, 55)} ({b.programming_language || 'general'})
                    </option>
                  ))
                )}
              </select>
            ) : null}

            <button
              type="button"
              className="btn-primary btn-run-council"
              onClick={handleRunEvaluation}
              disabled={evaluating}
            >
              {evaluating ? '⏳ Council Debating...' : '🚀 Launch Multi-LLM Evaluation & Debate'}
            </button>
          </div>

          {/* Custom Input Fields if toggled */}
          {bugSource === 'custom' && (
            <div className="custom-defect-fields">
              <div className="form-group">
                <label>Defect Title</label>
                <input
                  type="text"
                  className="text-input"
                  value={customReport.title}
                  onChange={(e) => setCustomReport({ ...customReport, title: e.target.value })}
                />
              </div>
              <div className="form-group">
                <label>Stack Trace or Log Snippet</label>
                <textarea
                  className="textarea-input"
                  rows={3}
                  value={customReport.stack_trace}
                  onChange={(e) => setCustomReport({ ...customReport, stack_trace: e.target.value })}
                />
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Error Card */}
      {error && (
        <div className="diff-error-card">
          <p>⚠️ {error}</p>
        </div>
      )}

      {/* Loading Overlay */}
      {evaluating && (
        <div className="council-loading-card">
          <span className="spinner"></span>
          <h3>Council in Session...</h3>
          <p>Each model is independently computing severity scores, parsing failure frames, and formulating their debate stances.</p>
        </div>
      )}

      {/* Evaluation Results */}
      {result && !evaluating && (
        <div className="council-results-container">
          {/* Section 1: Consensus Verdict Banner */}
          <div className="consensus-banner-card">
            <div className="consensus-top">
              <div className="verdict-pill-col">
                <span className="verdict-label">COUNCIL CONSENSUS VERDICT</span>
                <div className="verdict-badge-row">
                  <span className={`severity-large-badge ${result.consensus.consensus_severity.toLowerCase()}`}>
                    {result.consensus.consensus_severity} SEVERITY
                  </span>
                  <span className="priority-large-badge">
                    {result.consensus.consensus_priority}
                  </span>
                </div>
              </div>
              <div className="agreement-stat-col">
                <span className="agreement-pct">{result.consensus.agreement_percentage}%</span>
                <span className="agreement-lbl">Model Agreement</span>
              </div>
            </div>

            <div className="urgency-alert-row">
              <span className="urgency-badge">🚨 {result.consensus.urgency_level}</span>
              <p className="final-plan-text">
                <strong>Action Plan:</strong> {result.consensus.final_action_plan}
              </p>
            </div>

            <div className="agreements-list-row">
              <strong>Key Agreed Findings:</strong>
              <ul>
                {result.consensus.key_agreements.map((item, i) => (
                  <li key={i}>✓ {item}</li>
                ))}
              </ul>
            </div>
          </div>

          {/* Section 2: Interactive Council Discussion / Debate */}
          <div className="council-debate-card">
            <div className="debate-card-header">
              <span className="header-icon">💬</span>
              <div>
                <h3>Multi-Agent Debate & Cross-Examination</h3>
                <p>Real-time deliberation transcript between the participating AI agents.</p>
              </div>
            </div>

            <div className="debate-timeline">
              {result.discussion.map((turn, idx) => (
                <div key={idx} className={`turn-bubble turn-${turn.stance}`}>
                  <div className="turn-avatar">{turn.avatar_emoji}</div>
                  <div className="turn-content">
                    <div className="turn-header">
                      <span className="turn-speaker">{turn.speaker}</span>
                      <span className="turn-model">({turn.model_name})</span>
                      <span className="turn-role">• {turn.role}</span>
                      <span className={`turn-stance-badge stance-${turn.stance}`}>{turn.stance.toUpperCase()}</span>
                    </div>
                    <div className="turn-message">{turn.message}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Section 3: Side-by-Side Model Scorecards */}
          <div className="scorecards-section">
            <div className="scorecards-header">
              <h3>Independent Model Scorecards ({result.evaluations.length} Models)</h3>
              <p>Compare how each LLM individually rated severity, localized the fault, and drafted a solution.</p>
            </div>

            <div className="scorecards-grid">
              {result.evaluations.map((ev) => (
                <div key={ev.model_id} className="model-scorecard">
                  <div className="card-top">
                    <div className="model-title-wrap">
                      <span className="model-name-text">{ev.display_name}</span>
                      <span className="model-provider">{ev.provider}</span>
                    </div>
                    <span className={`status-pill pill-${ev.status}`}>
                      {ev.status === 'active' ? '● Live API' : '● Verified Persona'}
                    </span>
                  </div>

                  <div className="scorecard-metric-row">
                    <div className="metric-box">
                      <span className="metric-lbl">Severity Rating</span>
                      <span className={`metric-val sev-${ev.severity.toLowerCase()}`}>
                        {ev.severity} ({ev.severity_score}/10)
                      </span>
                    </div>
                    <div className="metric-box">
                      <span className="metric-lbl">Priority</span>
                      <span className="metric-val">{ev.priority}</span>
                    </div>
                    <div className="metric-box">
                      <span className="metric-lbl">Confidence</span>
                      <span className="metric-val">{(ev.confidence * 100).toFixed(0)}%</span>
                    </div>
                  </div>

                  <div className="scorecard-field">
                    <span className="field-title">📍 Failure Location:</span>
                    <code>{ev.identified_location}</code>
                  </div>

                  <div className="scorecard-field">
                    <span className="field-title">🔍 Root Cause Diagnosis:</span>
                    <p>{ev.root_cause}</p>
                  </div>

                  <div className="scorecard-field">
                    <span className="field-title">💡 Proposed Fix Patch:</span>
                    <pre className="fix-preview-box">
                      <code>{ev.full_fix_code}</code>
                    </pre>
                  </div>

                  <div className="scorecard-footer">
                    <span className="field-title">Reasoning:</span>
                    <p className="reasoning-text">{ev.reasoning}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

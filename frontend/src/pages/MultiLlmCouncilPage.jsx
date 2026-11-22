import React, { useState, useEffect } from 'react';
import api from '../services/api';

const AVAILABLE_PROVIDERS = [
  { id: 'gemini', name: 'Google Gemini', defaultModel: 'Gemini 2.5 Flash', icon: '🤖', badge: 'Cloud' },
  { id: 'groq', name: 'Groq Cloud', defaultModel: 'Llama 3.3 70B', icon: '⚡', badge: 'Ultra-Fast' },
  { id: 'openai', name: 'OpenAI', defaultModel: 'GPT-4o-mini', icon: '🧠', badge: 'Cloud' },
  { id: 'anthropic', name: 'Anthropic Claude', defaultModel: 'Claude 3.5 Sonnet', icon: '🛡️', badge: 'Cloud' },
  { id: 'mistral', name: 'Mistral AI', defaultModel: 'Codestral', icon: '🌪️', badge: 'Code AI' },
  { id: 'ollama', name: 'Local Ollama', defaultModel: 'Llama 3.2 (Local)', icon: '🦙', badge: '100% Free & Local' },
  { id: 'custom', name: 'Custom Endpoint', defaultModel: 'Custom Model', icon: '⚙️', badge: 'Any OpenAI API' },
];

export default function MultiLlmCouncilPage({ recentBugs = [] }) {
  // Stored Keys & Configuration
  const [geminiKey, setGeminiKey] = useState(() => localStorage.getItem('KEY_GEMINI') || '');
  const [groqKey, setGroqKey] = useState(() => localStorage.getItem('KEY_GROQ') || '');
  const [openaiKey, setOpenaiKey] = useState(() => localStorage.getItem('KEY_OPENAI') || '');
  const [anthropicKey, setAnthropicKey] = useState(() => localStorage.getItem('KEY_ANTHROPIC') || '');
  const [mistralKey, setMistralKey] = useState(() => localStorage.getItem('KEY_MISTRAL') || '');
  const [ollamaUrl, setOllamaUrl] = useState(() => localStorage.getItem('URL_OLLAMA') || 'http://localhost:11434');
  const [customUrl, setCustomUrl] = useState(() => localStorage.getItem('URL_CUSTOM') || '');
  const [customKey, setCustomKey] = useState(() => localStorage.getItem('KEY_CUSTOM') || '');
  const [customModel, setCustomModel] = useState(() => localStorage.getItem('MODEL_CUSTOM') || '');

  const [activeKeyTab, setActiveKeyTab] = useState('gemini');
  const [keysSaved, setKeysSaved] = useState(false);
  const [isKeysExpanded, setIsKeysExpanded] = useState(false);

  // Selected Models to participate
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
    if (e) e.preventDefault();
    localStorage.setItem('KEY_GEMINI', geminiKey.trim());
    localStorage.setItem('KEY_GROQ', groqKey.trim());
    localStorage.setItem('KEY_OPENAI', openaiKey.trim());
    localStorage.setItem('KEY_ANTHROPIC', anthropicKey.trim());
    localStorage.setItem('KEY_MISTRAL', mistralKey.trim());
    localStorage.setItem('URL_OLLAMA', ollamaUrl.trim());
    localStorage.setItem('URL_CUSTOM', customUrl.trim());
    localStorage.setItem('KEY_CUSTOM', customKey.trim());
    localStorage.setItem('MODEL_CUSTOM', customModel.trim());
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
      anthropic_api_key: anthropicKey.trim() || undefined,
      mistral_api_key: mistralKey.trim() || undefined,
      ollama_base_url: ollamaUrl.trim() || undefined,
      custom_endpoint_url: customUrl.trim() || undefined,
      custom_api_key: customKey.trim() || undefined,
      custom_model_name: customModel.trim() || undefined,
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
              Supply your own API keys (Gemini, Groq, OpenAI, Claude, Mistral, Ollama, Custom) to cross-evaluate defect severity scores, compare code patches, and view real-time multi-agent consensus debates.
            </p>
          </div>
        </div>

        {/* Custom API Key & Provider Configuration Hub */}
        <div className="provider-hub-card">
          <div className="hub-top-bar" onClick={() => setIsKeysExpanded(!isKeysExpanded)}>
            <div className="hub-title-group">
              <span className="hub-icon">🔐</span>
              <div>
                <h4>LLM Provider Keys & Custom Endpoints ({AVAILABLE_PROVIDERS.length} Supported)</h4>
                <p className="hub-subtitle">
                  {isKeysExpanded
                    ? 'Click to collapse provider settings'
                    : 'Configure your own API keys for Gemini, Groq, OpenAI, Claude, Mistral, local Ollama, or Custom vLLM'}
                </p>
              </div>
            </div>
            <div className="hub-toggle-btn">
              {isKeysExpanded ? '▲ Collapse' : '▼ Expand Keys Setup'}
            </div>
          </div>

          {isKeysExpanded && (
            <div className="hub-content-expanded">
              {/* Provider Subtabs */}
              <div className="provider-subtabs">
                {AVAILABLE_PROVIDERS.map((p) => (
                  <button
                    key={p.id}
                    type="button"
                    className={`btn-provider-tab ${activeKeyTab === p.id ? 'active' : ''}`}
                    onClick={() => setActiveKeyTab(p.id)}
                  >
                    <span>{p.icon}</span>
                    <span>{p.name}</span>
                    <span className="tab-badge">{p.badge}</span>
                  </button>
                ))}
              </div>

              {/* Provider Key Input Pane */}
              <div className="provider-input-pane">
                {activeKeyTab === 'gemini' && (
                  <div className="pane-form">
                    <label>Google Gemini API Key</label>
                    <input
                      type="password"
                      className="text-input"
                      placeholder="AIzaSy... (Gemini API Key)"
                      value={geminiKey}
                      onChange={(e) => setGeminiKey(e.target.value)}
                    />
                    <small className="help-text">Powering Gemini 2.5 Flash, 1.5 Flash, and 2.0 Pro.</small>
                  </div>
                )}

                {activeKeyTab === 'groq' && (
                  <div className="pane-form">
                    <label>Groq Cloud API Key</label>
                    <input
                      type="password"
                      className="text-input"
                      placeholder="gsk_... (Groq Cloud Key)"
                      value={groqKey}
                      onChange={(e) => setGroqKey(e.target.value)}
                    />
                    <small className="help-text">Powering ultra-fast Llama 3.3 70B and Mixtral 8x7B inference.</small>
                  </div>
                )}

                {activeKeyTab === 'openai' && (
                  <div className="pane-form">
                    <label>OpenAI API Key</label>
                    <input
                      type="password"
                      className="text-input"
                      placeholder="sk-proj-... (OpenAI API Key)"
                      value={openaiKey}
                      onChange={(e) => setOpenaiKey(e.target.value)}
                    />
                    <small className="help-text">Powering GPT-4o, GPT-4o-mini, and architecture reviews.</small>
                  </div>
                )}

                {activeKeyTab === 'anthropic' && (
                  <div className="pane-form">
                    <label>Anthropic Claude API Key</label>
                    <input
                      type="password"
                      className="text-input"
                      placeholder="sk-ant-... (Anthropic API Key)"
                      value={anthropicKey}
                      onChange={(e) => setAnthropicKey(e.target.value)}
                    />
                    <small className="help-text">Powering Claude 3.5 Sonnet type-safe analysis.</small>
                  </div>
                )}

                {activeKeyTab === 'mistral' && (
                  <div className="pane-form">
                    <label>Mistral AI API Key</label>
                    <input
                      type="password"
                      className="text-input"
                      placeholder="... (Mistral / Codestral Key)"
                      value={mistralKey}
                      onChange={(e) => setMistralKey(e.target.value)}
                    />
                    <small className="help-text">Powering Mistral Codestral specialized code synthesis.</small>
                  </div>
                )}

                {activeKeyTab === 'ollama' && (
                  <div className="pane-form">
                    <label>Local Ollama Base URL (No API Key Needed)</label>
                    <input
                      type="text"
                      className="text-input"
                      placeholder="http://localhost:11434"
                      value={ollamaUrl}
                      onChange={(e) => setOllamaUrl(e.target.value)}
                    />
                    <small className="help-text">100% local and private execution via your local Ollama server.</small>
                  </div>
                )}

                {activeKeyTab === 'custom' && (
                  <div className="pane-form">
                    <label>Custom OpenAI-Compatible Endpoint URL</label>
                    <input
                      type="text"
                      className="text-input"
                      placeholder="https://api.together.xyz/v1 or http://localhost:8000/v1"
                      value={customUrl}
                      onChange={(e) => setCustomUrl(e.target.value)}
                    />
                    <div className="form-row-2col" style={{ marginTop: '8px' }}>
                      <div>
                        <label>Custom API Key (Optional)</label>
                        <input
                          type="password"
                          className="text-input"
                          placeholder="API Key if required"
                          value={customKey}
                          onChange={(e) => setCustomKey(e.target.value)}
                        />
                      </div>
                      <div>
                        <label>Model Identifier</label>
                        <input
                          type="text"
                          className="text-input"
                          placeholder="e.g. deepseek-ai/DeepSeek-V3"
                          value={customModel}
                          onChange={(e) => setCustomModel(e.target.value)}
                        />
                      </div>
                    </div>
                  </div>
                )}

                <div className="save-btn-row">
                  <button type="button" className="btn-secondary" onClick={handleSaveKeys}>
                    {keysSaved ? '✅ Saved in Local Browser!' : '💾 Save All Keys & Endpoints'}
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Participating Model Checkboxes */}
        <div className="council-controls-bar">
          <div className="model-selection-group">
            <span className="selection-label">Council Participants:</span>
            <div className="models-badge-row">
              {AVAILABLE_PROVIDERS.map((m) => {
                const isSelected = selectedModels.includes(m.id);
                return (
                  <label key={m.id} className={`model-chip ${isSelected ? 'selected' : ''}`}>
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => toggleModel(m.id)}
                    />
                    <span className="chip-icon">{m.icon}</span>
                    <span className="chip-name">{m.name}</span>
                  </label>
                );
              })}
            </div>
          </div>

          {/* Defect Source Picker */}
          <div className="council-source-row">
            <div className="source-toggle-chips">
              <button
                type="button"
                className={`btn-source-chip ${bugSource === 'recent' ? 'active' : ''}`}
                onClick={() => setBugSource('recent')}
              >
                📋 From Submissions ({recentBugs.length})
              </button>
              <button
                type="button"
                className={`btn-source-chip ${bugSource === 'custom' ? 'active' : ''}`}
                onClick={() => setBugSource('custom')}
              >
                ✍ Custom Defect Report
              </button>
            </div>

            {bugSource === 'recent' ? (
              <select
                className="select-input council-bug-dropdown"
                value={selectedBugId}
                onChange={(e) => setSelectedBugId(e.target.value)}
                disabled={recentBugs.length === 0}
              >
                {recentBugs.length === 0 ? (
                  <option value="">No submissions available</option>
                ) : (
                  recentBugs.map((b) => (
                    <option key={b.bug_id} value={b.bug_id}>
                      #{b.bug_id} - {b.title.slice(0, 60)} ({b.programming_language || 'general'})
                    </option>
                  ))
                )}
              </select>
            ) : null}

            <button
              type="button"
              className="btn-launch-council"
              onClick={handleRunEvaluation}
              disabled={evaluating}
            >
              {evaluating ? '⏳ Council in Session...' : '🚀 Launch Multi-LLM Evaluation & Debate'}
            </button>
          </div>

          {/* Custom Input Fields if toggled */}
          {bugSource === 'custom' && (
            <div className="custom-defect-inputs">
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
          <p>Running independent evaluations across {selectedModels.length} models and synthesizing cross-model debate.</p>
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
                    {result.consensus.consensus_severity.toUpperCase()} SEVERITY
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
                <h3>Multi-Agent Debate & Cross-Examination ({result.discussion.length} Exchanges)</h3>
                <p>Real-time deliberation transcript between the participating AI models.</p>
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
              <h3>Independent Model Scorecards ({result.evaluations.length} Models Evaluated)</h3>
              <p>Compare how each LLM individually rated severity, localized the fault, and drafted a solution.</p>
            </div>

            <div className="scorecards-flexible-grid">
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

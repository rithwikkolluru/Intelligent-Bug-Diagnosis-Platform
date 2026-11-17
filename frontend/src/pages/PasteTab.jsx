import React, { useState } from 'react';
import api from '../services/api';

const initialForm = {
  title: '',
  description: '',
  stack_trace: '',
  error_logs: '',
  programming_language: 'Auto-detect',
};

const languageOptions = ['Auto-detect', 'Java', 'Python', 'JavaScript', 'C/C++', 'Go', 'Rust', 'Other'];

function PasteTab({ samples = [], onSaved, onDiagnosed }) {
  const [form, setForm] = useState(initialForm);
  const [autoDiagnose, setAutoDiagnose] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSelectSample = (sample) => {
    setForm({
      title: sample.title,
      description: sample.description,
      stack_trace: sample.stack_trace,
      error_logs: sample.error_logs,
      programming_language: sample.programming_language || 'Auto-detect',
    });
    setError('');
  };

  const handleClear = () => {
    setForm(initialForm);
    setError('');
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!form.title.trim() || !form.description.trim()) {
      setError('Title and Description are required.');
      return;
    }

    setLoading(true);
    setError('');

    const payload = {
      title: form.title.trim(),
      description: form.description.trim(),
      stack_trace: form.stack_trace.trim() || undefined,
      error_logs: form.error_logs.trim() || undefined,
      programming_language: form.programming_language === 'Auto-detect' ? undefined : form.programming_language,
    };

    try {
      if (autoDiagnose) {
        // One-shot submit & diagnose
        const response = await api.post('/api/diagnose', payload);
        const { bug, diagnosis } = response.data;
        onSaved?.();
        onDiagnosed?.(bug, diagnosis);
      } else {
        // Submission only
        const response = await api.post('/api/bugs', payload);
        onSaved?.();
        onDiagnosed?.(response.data, null);
      }
    } catch (err) {
      const detail = err.response?.data;
      const message = typeof detail?.detail === 'string' ? detail.detail : 'Submission failed. Please check inputs.';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="tab-content-wrapper">
      {/* Quick Sample Presets */}
      {samples.length > 0 && (
        <div className="samples-bar">
          <span className="samples-label">⚡ Quick Presets:</span>
          <div className="samples-buttons">
            {samples.map((sample) => (
              <button
                key={sample.id}
                type="button"
                className="btn-sample"
                onClick={() => handleSelectSample(sample)}
                title="Populate form with this realistic bug scenario"
              >
                {sample.label}
              </button>
            ))}
          </div>
        </div>
      )}

      <form className="submission-form" onSubmit={handleSubmit}>
        <div className="form-header-row">
          <h3>Paste Bug Report or Stack Trace</h3>
          <button type="button" className="btn-text" onClick={handleClear}>Clear Form</button>
        </div>

        <label>
          <span className="label-text">Bug Title <span className="req">*</span></span>
          <input
            type="text"
            value={form.title}
            onChange={(event) => setForm({ ...form, title: event.target.value })}
            placeholder="e.g. NullPointerException in AuthenticationService.authenticate()"
            required
            maxLength={300}
          />
          <span className="field-hint">{form.title.length}/300 characters</span>
        </label>

        <div className="form-grid-2">
          <label>
            <span className="label-text">Programming Language</span>
            <select
              value={form.programming_language}
              onChange={(event) => setForm({ ...form, programming_language: event.target.value })}
            >
              {languageOptions.map((option) => (
                <option key={option} value={option}>{option}</option>
              ))}
            </select>
          </label>

          <div className="privacy-badge-container">
            <span className="privacy-pill">🛡️ Secret Redaction Active</span>
            <span className="privacy-desc">Passwords and API keys are scrubbed before storage & LLM calls.</span>
          </div>
        </div>

        <label>
          <span className="label-text">Problem Description & Reproduction Steps <span className="req">*</span></span>
          <textarea
            value={form.description}
            onChange={(event) => setForm({ ...form, description: event.target.value })}
            rows={4}
            placeholder="Describe what occurred, expected vs actual behavior, and steps to reproduce..."
            required
            minLength={10}
          />
        </label>

        <label>
          <span className="label-text">Stack Trace (Optional)</span>
          <textarea
            value={form.stack_trace}
            onChange={(event) => setForm({ ...form, stack_trace: event.target.value })}
            rows={5}
            className="monospace"
            placeholder="Paste raw stack trace here (e.g. java.lang.NullPointerException, Traceback...)"
          />
        </label>

        <label>
          <span className="label-text">Error Logs / System Context (Optional)</span>
          <textarea
            value={form.error_logs}
            onChange={(event) => setForm({ ...form, error_logs: event.target.value })}
            rows={4}
            className="monospace"
            placeholder="Server log lines, HTTP response errors, or console output..."
          />
        </label>

        <div className="checkbox-row">
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={autoDiagnose}
              onChange={(e) => setAutoDiagnose(e.target.checked)}
            />
            <span>Auto-diagnose with AI (Gemini + RAG Retrieval) immediately upon submission</span>
          </label>
        </div>

        {error && <div className="alert alert-error">{error}</div>}

        <div className="form-actions">
          <button type="submit" className="btn-primary btn-large" disabled={loading}>
            {loading ? (
              <span className="btn-loading">
                <span className="spinner"></span> Analyzing & Diagnosing with Gemini…
              </span>
            ) : autoDiagnose ? (
              '⚡ Submit & Diagnose with AI'
            ) : (
              'Save Bug Report Only'
            )}
          </button>
        </div>
      </form>
    </div>
  );
}

export default PasteTab;

import { useState } from 'react';
import api from '../services/api';

const initialForm = {
  title: '',
  description: '',
  stack_trace: '',
  error_logs: '',
  programming_language: 'Auto-detect',
};

const languageOptions = ['Java', 'Python', 'JavaScript', 'C/C++', 'Other', 'Auto-detect'];

function PasteTab({ onSaved }) {
  const [form, setForm] = useState(initialForm);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');

  const handleSubmit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError('');
    setResult(null);

    try {
      const payload = {
        title: form.title,
        description: form.description,
        stack_trace: form.stack_trace || undefined,
        error_logs: form.error_logs || undefined,
        programming_language: form.programming_language === 'Auto-detect' ? 'Other' : form.programming_language,
      };
      const response = await api.post('/api/bugs', payload);
      setResult(response.data);
      onSaved?.();
      setForm(initialForm);
    } catch (err) {
      const detail = err.response?.data;
      setError(detail?.detail || 'Submission failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <form className="submission-form" onSubmit={handleSubmit}>
      <h2>Paste Bug Report</h2>
      <label>
        Title
        <input
          type="text"
          value={form.title}
          onChange={(event) => setForm({ ...form, title: event.target.value })}
          placeholder="e.g. NullPointerException in user service"
          required
        />
      </label>

      <label>
        Description
        <textarea
          value={form.description}
          onChange={(event) => setForm({ ...form, description: event.target.value })}
          rows={5}
          required
        />
      </label>

      <label>
        Stack trace
        <textarea
          value={form.stack_trace}
          onChange={(event) => setForm({ ...form, stack_trace: event.target.value })}
          rows={6}
          className="monospace"
        />
      </label>

      <label>
        Error logs
        <textarea
          value={form.error_logs}
          onChange={(event) => setForm({ ...form, error_logs: event.target.value })}
          rows={5}
          className="monospace"
        />
      </label>

      <label>
        Language
        <select
          value={form.programming_language}
          onChange={(event) => setForm({ ...form, programming_language: event.target.value })}
        >
          {languageOptions.map((option) => (
            <option key={option} value={option}>{option}</option>
          ))}
        </select>
      </label>

      {error && <div className="alert alert-error">{error.detail || error}</div>}

      <button type="submit" disabled={loading}>
        {loading ? 'Submitting…' : 'Submit bug'}
      </button>

      {result && (
        <div className="result-card">
          <h3>Submission saved</h3>
          <p><strong>Bug ID:</strong> {result.bug_id}</p>
          <p><strong>Status:</strong> {result.status}</p>
          <p><strong>Detected language:</strong> {result.programming_language || 'Unknown'}</p>
          <p><strong>Stack trace detected:</strong> {result.stack_trace ? 'Yes' : 'No'}</p>
          <p><strong>Secrets redacted:</strong> {result.redaction_count}</p>
          <p><strong>Created:</strong> {new Date(result.created_at).toLocaleString()}</p>
          {result.stack_trace && (
            <pre className="trace-box">{result.stack_trace}</pre>
          )}
        </div>
      )}
    </form>
  );
}

export default PasteTab;

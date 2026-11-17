import { useRef, useState } from 'react';
import api from '../services/api';

const allowedTypes = ['.txt', '.log', '.md', '.json', '.csv'];

function UploadTab({ onSaved }) {
  const fileInputRef = useRef(null);
  const [file, setFile] = useState(null);
  const [title, setTitle] = useState('');
  const [language, setLanguage] = useState('Auto-detect');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');

  const handleDrop = (event) => {
    event.preventDefault();
    const selected = event.dataTransfer.files?.[0];
    if (selected) setFile(selected);
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!file) {
      setError('Please choose a valid file first.');
      return;
    }

    setLoading(true);
    setError('');
    setResult(null);

    const formData = new FormData();
    formData.append('file', file);
    if (title) formData.append('title', title);
    if (language && language !== 'Auto-detect') formData.append('programming_language', language);

    try {
      const response = await api.post('/api/bugs/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setResult(response.data);
      onSaved?.();
      setFile(null);
      setTitle('');
      setLanguage('Auto-detect');
      fileInputRef.current.value = '';
    } catch (err) {
      const detail = err.response?.data;
      setError(detail?.detail || 'Upload failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <form className="submission-form" onSubmit={handleSubmit}>
      <h2>Upload File</h2>
      <div
        className="dropzone"
        onDragOver={(event) => event.preventDefault()}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
      >
        {file ? <span>{file.name}</span> : <span>Drag & drop a file here or click to browse</span>}
        <input
          ref={fileInputRef}
          type="file"
          accept=".txt,.log,.md,.json,.csv"
          onChange={(event) => setFile(event.target.files?.[0] || null)}
          hidden
        />
      </div>
      <p className="helper-text">Allowed: {allowedTypes.join(', ')} • Max 5 MB</p>

      <label>
        Optional title
        <input
          type="text"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          placeholder="Custom bug title"
        />
      </label>

      <label>
        Language
        <select value={language} onChange={(event) => setLanguage(event.target.value)}>
          <option value="Auto-detect">Auto-detect</option>
          <option value="Java">Java</option>
          <option value="Python">Python</option>
          <option value="JavaScript">JavaScript</option>
          <option value="C/C++">C/C++</option>
          <option value="Other">Other</option>
        </select>
      </label>

      {error && <div className="alert alert-error">{error.detail || error}</div>}

      <button type="submit" disabled={loading || !file}>
        {loading ? 'Uploading…' : 'Upload and submit'}
      </button>

      {result && (
        <div className="result-card">
          <h3>Upload processed</h3>
          <p><strong>Bug ID:</strong> {result.bug_id}</p>
          <p><strong>Status:</strong> {result.status}</p>
          <p><strong>Detected language:</strong> {result.programming_language || 'Unknown'}</p>
          <p><strong>Stack trace detected:</strong> {result.stack_trace ? 'Yes' : 'No'}</p>
          <p><strong>Secrets redacted:</strong> {result.redaction_count}</p>
          <p><strong>Created:</strong> {new Date(result.created_at).toLocaleString()}</p>
          {result.stack_trace && <pre className="trace-box">{result.stack_trace}</pre>}
        </div>
      )}
    </form>
  );
}

export default UploadTab;

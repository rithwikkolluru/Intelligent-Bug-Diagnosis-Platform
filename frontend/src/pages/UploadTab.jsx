import React, { useRef, useState } from 'react';
import api from '../services/api';

const allowedTypes = ['.txt', '.log', '.md', '.json', '.csv'];
const languageOptions = ['Auto-detect', 'Java', 'Python', 'JavaScript', 'C/C++', 'Go', 'Rust', 'Other'];

function UploadTab({ onSaved, onDiagnosed }) {
  const fileInputRef = useRef(null);
  const [file, setFile] = useState(null);
  const [title, setTitle] = useState('');
  const [language, setLanguage] = useState('Auto-detect');
  const [autoDiagnose, setAutoDiagnose] = useState(true);
  const [isDragging, setIsDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (event) => {
    event.preventDefault();
    setIsDragging(false);
    const selected = event.dataTransfer.files?.[0];
    if (selected) {
      validateAndSetFile(selected);
    }
  };

  const validateAndSetFile = (f) => {
    const ext = '.' + f.name.split('.').pop().toLowerCase();
    if (!allowedTypes.includes(ext)) {
      setError(`Unsupported file type (${ext}). Allowed: ${allowedTypes.join(', ')}`);
      return;
    }
    if (f.size > 5 * 1024 * 1024) {
      setError(`File exceeds the 5 MB limit (${(f.size / (1024 * 1024)).toFixed(2)} MB).`);
      return;
    }
    setError('');
    setFile(f);
    if (!title) {
      setTitle(f.name.replace(/\.[^/.]+$/, ''));
    }
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!file) {
      setError('Please choose a file to upload.');
      return;
    }

    setLoading(true);
    setError('');

    const formData = new FormData();
    formData.append('file', file);
    if (title.trim()) formData.append('title', title.trim());
    if (language && language !== 'Auto-detect') formData.append('programming_language', language);

    try {
      // 1. Upload bug
      const uploadResp = await api.post('/api/bugs/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      const bug = uploadResp.data;
      onSaved?.();

      if (autoDiagnose) {
        // 2. Trigger diagnosis
        const diagResp = await api.post(`/api/bugs/${bug.bug_id}/diagnose`);
        onDiagnosed?.(bug, diagResp.data);
      } else {
        onDiagnosed?.(bug, null);
      }

      setFile(null);
      setTitle('');
      setLanguage('Auto-detect');
      if (fileInputRef.current) fileInputRef.current.value = '';
    } catch (err) {
      const message = err.friendlyMessage || 'Upload failed. Please try again.';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="tab-content-wrapper">
      <form className="submission-form" onSubmit={handleSubmit}>
        <div className="form-header-row">
          <h3>Upload Crash Dump, Error Log, or Bug JSON</h3>
        </div>

        {/* Dropzone */}
        <div
          className={`dropzone ${isDragging ? 'dragging' : ''} ${file ? 'has-file' : ''}`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".txt,.log,.md,.json,.csv"
            onChange={(event) => {
              if (event.target.files?.[0]) validateAndSetFile(event.target.files[0]);
            }}
            hidden
          />

          {file ? (
            <div className="dropzone-file-info">
              <span className="file-icon">📄</span>
              <div className="file-meta">
                <span className="file-name">{file.name}</span>
                <span className="file-size">{(file.size / 1024).toFixed(1)} KB</span>
              </div>
              <button
                type="button"
                className="btn-remove"
                onClick={(e) => {
                  e.stopPropagation();
                  setFile(null);
                  if (fileInputRef.current) fileInputRef.current.value = '';
                }}
              >
                ✕
              </button>
            </div>
          ) : (
            <div className="dropzone-placeholder">
              <span className="upload-icon">☁️</span>
              <p className="primary-text">Drag & drop your bug file here, or <span className="browse-link">browse</span></p>
              <p className="helper-text">Supported: <strong>{allowedTypes.join('  ')}</strong> • Max size 5 MB</p>
            </div>
          )}
        </div>

        <div className="form-grid-2">
          <label>
            <span className="label-text">Custom Title (Optional)</span>
            <input
              type="text"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="Defaults to filename"
            />
          </label>

          <label>
            <span className="label-text">Language Hint</span>
            <select value={language} onChange={(event) => setLanguage(event.target.value)}>
              {languageOptions.map((opt) => (
                <option key={opt} value={opt}>{opt}</option>
              ))}
            </select>
          </label>
        </div>

        <div className="checkbox-row">
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={autoDiagnose}
              onChange={(e) => setAutoDiagnose(e.target.checked)}
            />
            <span>Auto-diagnose with Gemini AI immediately after upload</span>
          </label>
        </div>

        {error && <div className="alert alert-error">{error}</div>}

        <div className="form-actions">
          <button type="submit" className="btn-primary btn-large" disabled={loading || !file}>
            {loading ? (
              <span className="btn-loading">
                <span className="spinner"></span> Uploading & Diagnosing…
              </span>
            ) : autoDiagnose ? (
              '⚡ Upload & Diagnose with AI'
            ) : (
              'Upload File'
            )}
          </button>
        </div>
      </form>
    </div>
  );
}

export default UploadTab;

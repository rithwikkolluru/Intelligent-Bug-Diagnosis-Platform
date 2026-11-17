import React, { useState, useEffect } from 'react';

function SettingsModal({ isOpen, onClose, serverConfig }) {
  const [apiKey, setApiKey] = useState('');
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (isOpen) {
      const stored = localStorage.getItem('gemini_api_key') || '';
      setApiKey(stored);
      setSaved(false);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleSave = (e) => {
    e.preventDefault();
    if (apiKey.trim()) {
      localStorage.setItem('gemini_api_key', apiKey.trim());
    } else {
      localStorage.removeItem('gemini_api_key');
    }
    setSaved(true);
    setTimeout(() => {
      setSaved(false);
      onClose();
    }, 1000);
  };

  const handleClear = () => {
    localStorage.removeItem('gemini_api_key');
    setApiKey('');
    setSaved(true);
    setTimeout(() => {
      setSaved(false);
      onClose();
    }, 800);
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>⚡ Gemini AI Configuration</h3>
          <button type="button" className="btn-close" onClick={onClose}>×</button>
        </div>

        <form onSubmit={handleSave} className="modal-body">
          <p className="modal-intro">
            Connect your <strong>Google Gemini API Key</strong> to generate real-time, evidence-backed
            root-cause analyses and code fixes.
          </p>

          <div className="status-box">
            <div className="status-row">
              <span className="status-label">Backend Gemini Status:</span>
              <span className={`badge ${serverConfig?.gemini_configured ? 'badge-success' : 'badge-warning'}`}>
                {serverConfig?.gemini_configured ? 'Configured in .env' : 'Fallback Engine Active'}
              </span>
            </div>
            <div className="status-row">
              <span className="status-label">Active Model:</span>
              <span className="model-text">{serverConfig?.gemini_model || 'gemini-2.5-flash'}</span>
            </div>
          </div>

          <label className="input-group">
            <span>Custom Gemini API Key</span>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="AIzaSy..."
              autoComplete="off"
            />
            <small className="helper-text">
              Keys entered here are saved locally in your browser session and sent via secure headers.
              Get a free API key at <a href="https://aistudio.google.com/app/apikey" target="_blank" rel="noreferrer">aistudio.google.com</a>.
            </small>
          </label>

          {saved && <div className="alert alert-success">Settings saved successfully!</div>}

          <div className="modal-actions">
            {apiKey && (
              <button type="button" className="btn-secondary" onClick={handleClear}>
                Clear Custom Key
              </button>
            )}
            <button type="button" className="btn-secondary" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn-primary">
              Save Configuration
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default SettingsModal;

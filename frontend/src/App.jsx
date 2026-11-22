import React, { useEffect, useState } from 'react';
import api from './services/api';
import PasteTab from './pages/PasteTab';
import UploadTab from './pages/UploadTab';
import DiagnosisView from './components/DiagnosisView';
import ArchitectureDocs from './components/ArchitectureDocs';
import SettingsModal from './components/SettingsModal';
import CodeFixDiffPage from './pages/CodeFixDiffPage';
import MultiLlmCouncilPage from './pages/MultiLlmCouncilPage';

const tabs = [
  'Paste Bug Report',
  'Upload File',
  'Diagnosis Dashboard',
  'Code Fix & Diff (Before/After)',
  'Multi-LLM Council Arena',
  'Architecture & Specs',
];

function App() {
  const [activeTab, setActiveTab] = useState(0);
  const [recent, setRecent] = useState([]);
  const [loadingRecent, setLoadingRecent] = useState(false);
  const [samples, setSamples] = useState([]);
  const [serverHealth, setServerHealth] = useState(null);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

  // Active bug and diagnosis
  const [selectedBug, setSelectedBug] = useState(null);
  const [selectedDiagnosis, setSelectedDiagnosis] = useState(null);
  const [diagnosisLoading, setDiagnosisLoading] = useState(false);

  // Load health and samples
  const loadSystemData = async () => {
    try {
      const [healthResp, samplesResp] = await Promise.allSettled([
        api.get('/health'),
        api.get('/api/samples'),
      ]);
      if (healthResp.status === 'fulfilled') {
        setServerHealth(healthResp.value.data);
      }
      if (samplesResp.status === 'fulfilled') {
        setSamples(samplesResp.value.data || []);
      }
    } catch (e) {
      // ignore
    }
  };

  // Load recent submissions
  const loadRecent = async () => {
    try {
      setLoadingRecent(true);
      const response = await api.get('/api/bugs?limit=15&offset=0');
      setRecent(response.data.items || []);
    } catch (error) {
      setRecent([]);
    } finally {
      setLoadingRecent(false);
    }
  };

  useEffect(() => {
    loadSystemData();
    loadRecent();
  }, []);

  // When a bug is submitted and diagnosed from PasteTab or UploadTab
  const handleBugDiagnosed = (bug, diagnosis) => {
    setSelectedBug(bug);
    setSelectedDiagnosis(diagnosis);
    loadRecent();
    if (diagnosis) {
      setActiveTab(2); // Switch to Diagnosis Dashboard
    }
  };

  // When clicking a recent bug from the sidebar
  const handleSelectRecentBug = async (bug) => {
    setSelectedBug(bug);
    setSelectedDiagnosis(null);
    setActiveTab(2); // Switch to Diagnosis Dashboard

    try {
      setDiagnosisLoading(true);
      const resp = await api.get(`/api/bugs/${bug.bug_id}/diagnosis`);
      setSelectedDiagnosis(resp.data);
    } catch (err) {
      // If 404, not yet diagnosed
      setSelectedDiagnosis(null);
    } finally {
      setDiagnosisLoading(false);
    }
  };

  // Run or refresh diagnosis for a bug
  const handleTriggerDiagnosis = async (bugId, force = false) => {
    if (!bugId) return;
    try {
      setDiagnosisLoading(true);
      const resp = await api.post(`/api/bugs/${bugId}/diagnose`, {
        force_refresh: force,
      });
      setSelectedDiagnosis(resp.data);
      // Update bug status in local list
      setRecent((prev) =>
        prev.map((b) => (b.bug_id === bugId ? { ...b, status: 'diagnosed' } : b))
      );
      if (selectedBug && selectedBug.bug_id === bugId) {
        setSelectedBug((prev) => ({ ...prev, status: 'diagnosed' }));
      }
    } catch (err) {
      console.error('Diagnosis failed:', err);
    } finally {
      setDiagnosisLoading(false);
    }
  };

  return (
    <div className="app-shell">
      {/* Top Header */}
      <header className="app-header">
        <div className="header-brand">
          <div className="brand-logo">🐞</div>
          <div>
            <div className="brand-badge-row">
              <span className="brand-pill">Infosys Springboard Internship</span>
              <span className="version-pill">v0.2.0 • Production Ready</span>
            </div>
            <h1>Intelligent Bug Diagnosis Platform</h1>
            <p className="subtitle">
              Retrieval-Augmented Generation (RAG) • Multi-Agent Defect Reasoning • Gemini AI Fix Engine
            </p>
          </div>
        </div>

        <div className="header-controls">
          <div className="system-status-indicator">
            <span className="status-dot"></span>
            <span className="status-text">
              {serverHealth?.gemini_configured ? 'Gemini AI Active' : 'Heuristic Engine Ready'}
            </span>
          </div>

          <button
            type="button"
            className="btn-settings"
            onClick={() => setIsSettingsOpen(true)}
            title="Configure Gemini API Key"
          >
            ⚙️ Settings
          </button>
        </div>
      </header>

      {/* Main Tabs Navigation */}
      <nav className="tab-row" role="tablist" aria-label="Main navigation">
        {tabs.map((tab, index) => (
          <button
            key={tab}
            type="button"
            className={index === activeTab ? 'tab active' : 'tab'}
            onClick={() => setActiveTab(index)}
          >
            {index === 0 && '📝 '}
            {index === 1 && '📁 '}
            {index === 2 && '⚡ '}
            {index === 3 && '🔄 '}
            {index === 4 && '🏛️ '}
            {index === 5 && '📖 '}
            {tab}
            {index === 2 && selectedBug && (
              <span className="tab-pill">#{selectedBug.bug_id}</span>
            )}
          </button>
        ))}
      </nav>

      {/* Content Layout */}
      <main className="content-grid">
        {/* Primary Panel */}
        <section className="panel primary-panel">
          {activeTab === 0 && (
            <PasteTab
              samples={samples}
              onSaved={loadRecent}
              onDiagnosed={handleBugDiagnosed}
            />
          )}

          {activeTab === 1 && (
            <UploadTab
              onSaved={loadRecent}
              onDiagnosed={handleBugDiagnosed}
            />
          )}

          {activeTab === 2 && (
            <DiagnosisView
              bug={selectedBug}
              diagnosis={selectedDiagnosis}
              loading={diagnosisLoading}
              onRefresh={(bugId, force) => handleTriggerDiagnosis(bugId || selectedBug?.bug_id, force)}
            />
          )}

          {activeTab === 3 && (
            <CodeFixDiffPage recentBugs={recent} />
          )}

          {activeTab === 4 && (
            <MultiLlmCouncilPage recentBugs={recent} />
          )}

          {activeTab === 5 && <ArchitectureDocs />}
        </section>

        {/* Secondary Sidebar Panel */}
        <aside className="panel secondary-panel">
          <div className="sidebar-header">
            <h3>Recent Submissions</h3>
            <button
              type="button"
              className="btn-icon"
              onClick={loadRecent}
              disabled={loadingRecent}
              title="Refresh list"
            >
              🔄
            </button>
          </div>

          {loadingRecent ? (
            <div className="sidebar-loading">
              <span className="spinner"></span> Loading submissions…
            </div>
          ) : recent.length === 0 ? (
            <div className="empty-submissions">
              <p>No submissions yet.</p>
              <small>Use the presets in Paste tab to submit a demo bug.</small>
            </div>
          ) : (
            <ul className="recent-list">
              {recent.map((item) => {
                const isSelected = selectedBug?.bug_id === item.bug_id;
                return (
                  <li
                    key={item.bug_id}
                    className={`recent-item ${isSelected ? 'selected' : ''}`}
                    onClick={() => handleSelectRecentBug(item)}
                  >
                    <div className="recent-item-top">
                      <span className="recent-id">#{item.bug_id}</span>
                      <span className={`status-pill ${
                        item.status === 'diagnosed' ? 'pill-diagnosed' :
                        item.status?.startsWith('analysis_complete') ? 'pill-diagnosed' :
                        item.status?.startsWith('analysis_partial') ? 'pill-partial' :
                        item.status?.startsWith('analysis_failed') ? 'pill-failed' :
                        item.status === 'analyzing' ? 'pill-analyzing' :
                        'pill-received'
                      }`}>
                        {item.status?.startsWith('analysis_') ? item.status.replace('analysis_', '⚡ ') : item.status}
                      </span>
                    </div>

                    <div className="recent-title">{item.title}</div>

                    <div className="recent-item-meta">
                      <span className="meta-lang">{item.programming_language || 'Other'}</span>
                      {item.redaction_count > 0 && (
                        <span className="meta-redact" title="Secrets redacted">
                          🛡️ {item.redaction_count}
                        </span>
                      )}
                      <span className="meta-time">
                        {new Date(item.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}

          {/* Knowledge Base Info Card */}
          <div className="knowledge-base-card">
            <h4>Vector Knowledge Base</h4>
            <div className="kb-stat">
              <span className="kb-icon">📚</span>
              <div>
                <strong>36 Defect Chunks Indexed</strong>
                <p>Mozilla • Apache • Eclipse historical defects stored in ChromaDB.</p>
              </div>
            </div>
          </div>
        </aside>
      </main>

      {/* Settings Modal */}
      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => {
          setIsSettingsOpen(false);
          loadSystemData();
        }}
        serverConfig={serverHealth}
      />
    </div>
  );
}

export default App;

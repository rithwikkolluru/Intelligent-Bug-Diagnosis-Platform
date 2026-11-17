import { useEffect, useState } from 'react';
import api from './services/api';
import PasteTab from './pages/PasteTab';
import UploadTab from './pages/UploadTab';

const tabs = ['Paste Bug Report', 'Upload File'];

function App() {
  const [activeTab, setActiveTab] = useState(0);
  const [recent, setRecent] = useState([]);
  const [loadingRecent, setLoadingRecent] = useState(false);

  const loadRecent = async () => {
    try {
      setLoadingRecent(true);
      const response = await api.get('/api/bugs?limit=5&offset=0');
      setRecent(response.data.items || []);
    } catch (error) {
      setRecent([]);
    } finally {
      setLoadingRecent(false);
    }
  };

  useEffect(() => {
    loadRecent();
  }, []);

  return (
    <div className="app-shell">
      <header className="app-header">
        <h1>Intelligent Bug Diagnosis Platform</h1>
      </header>

      <div className="tab-row" role="tablist" aria-label="Submission tabs">
        {tabs.map((tab, index) => (
          <button
            key={tab}
            type="button"
            className={index === activeTab ? 'tab active' : 'tab'}
            onClick={() => setActiveTab(index)}
          >
            {tab}
          </button>
        ))}
      </div>

      <main className="content-grid">
        <section className="panel primary-panel">
          {activeTab === 0 ? <PasteTab onSaved={loadRecent} /> : <UploadTab onSaved={loadRecent} />}
        </section>

        <aside className="panel secondary-panel">
          <h2>Recent submissions</h2>
          {loadingRecent ? <p>Loading…</p> : recent.length === 0 ? <p>No submissions yet.</p> : (
            <ul className="recent-list">
              {recent.map((item) => (
                <li key={item.bug_id}>
                  <strong>#{item.bug_id}</strong> — {item.title}
                </li>
              ))}
            </ul>
          )}
        </aside>
      </main>
    </div>
  );
}

export default App;

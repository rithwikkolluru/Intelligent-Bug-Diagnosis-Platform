import React from 'react';

function ArchitectureDocs() {
  return (
    <div className="architecture-container">
      <div className="section-card">
        <div className="section-title">
          <span className="section-icon">🏛️</span>
          <h3>System Architecture & Pipeline Flow</h3>
        </div>
        <p className="architecture-intro">
          The <strong>Intelligent Bug Diagnosis Platform</strong> operates across two primary pipelines:
          an <em>Offline Knowledge Indexing Pipeline</em> that cleans and indexes historical defect repositories,
          and an <em>Online Real-time Diagnosis Pipeline</em> powered by Retrieval-Augmented Generation (RAG)
          and Google Gemini AI.
        </p>

        <div className="pipeline-grid">
          <div className="pipeline-card">
            <h4>1. Ingestion & Security Guard</h4>
            <ul>
              <li>Dual submission: Paste raw text or upload (.txt, .log, .md, .json, .csv).</li>
              <li>Strict 5MB upload limits and extension whitelisting.</li>
              <li>Automated regex secret redaction (API keys, Bearer tokens, passwords).</li>
              <li>Deterministic stack-trace regex segmentation & language inference.</li>
            </ul>
          </div>

          <div className="pipeline-card">
            <h4>2. RAG Semantic Search</h4>
            <ul>
              <li>Knowledge base: Historical defects from Mozilla, Apache, and Eclipse.</li>
              <li>Embeddings: Local <code>sentence-transformers/all-MiniLM-L6-v2</code> (384-dim).</li>
              <li>Vector Store: ChromaDB with cosine similarity distance metrics.</li>
              <li>Retrieval by error signature, stack-trace frames, and description chunks.</li>
            </ul>
          </div>

          <div className="pipeline-card">
            <h4>3. Multi-Agent Reasoning</h4>
            <ul>
              <li><strong>Triage Agent:</strong> Classifies severity, category, and language.</li>
              <li><strong>Log Analysis Agent:</strong> Extracts exception signatures and failing frames.</li>
              <li><strong>Duplicate Agent:</strong> Identifies matches in historical databases.</li>
              <li><strong>Remediation Agent:</strong> Synthesizes code fixes and verification steps.</li>
            </ul>
          </div>

          <div className="pipeline-card">
            <h4>4. Gemini Fix Engine</h4>
            <ul>
              <li>Direct Google Gemini API integration with JSON schema constraints.</li>
              <li>Supplies bug context + retrieved historical evidence citations.</li>
              <li>Zero-downtime heuristic fallback when API key is unconfigured or offline.</li>
              <li>Interactive code copy and verification test checklist.</li>
            </ul>
          </div>
        </div>
      </div>

      <div className="section-card">
        <div className="section-title">
          <span className="section-icon">🛡️</span>
          <h3>Security & Responsible AI Architecture</h3>
        </div>
        <div className="security-badges-row">
          <div className="sec-item">
            <strong>Client-Side & Server Redaction:</strong> Sensitive credentials stripped before persistence.
          </div>
          <div className="sec-item">
            <strong>Bounded Memory:</strong> Streaming and chunked file reads prevent OOM denial of service.
          </div>
          <div className="sec-item">
            <strong>Evidence-First Citations:</strong> LLM conclusions must reference historical defects.
          </div>
          <div className="sec-item">
            <strong>Local Vector Database:</strong> Zero third-party telemetry or cloud database locks.
          </div>
        </div>
      </div>
    </div>
  );
}

export default ArchitectureDocs;

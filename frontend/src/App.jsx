import React, { useState, useEffect } from 'react';
import PdfUploader from './components/PdfUploader';
import SummaryRoadmapView from './components/SummaryRoadmapView';
import RagChat from './components/RagChat';
import { 
  FileText, 
  Settings, 
  Columns, 
  BookOpen, 
  Terminal, 
  RefreshCw, 
  X, 
  Key, 
  Server, 
  PlusCircle, 
  Check, 
  Layers 
} from 'lucide-react';
import { getApiBaseUrl } from './api/client';
import axios from 'axios';

export default function App() {
  const [apiKey, setApiKey] = useState(localStorage.getItem('openai_api_key') || '');
  const [backendUrl, setBackendUrl] = useState(localStorage.getItem('custom_backend_url') || '');
  const [backendStatus, setBackendStatus] = useState('checking'); // 'connected', 'disconnected', 'checking'
  const [activeDocument, setActiveDocument] = useState(null);
  const [viewMode, setViewMode] = useState('split'); // 'split', 'dossier', 'inquiry'
  const [showSettings, setShowSettings] = useState(false);

  useEffect(() => {
    localStorage.setItem('openai_api_key', apiKey);
  }, [apiKey]);

  // Check backend server health
  const checkBackendHealth = async (url) => {
    setBackendStatus('checking');
    try {
      let targetUrl = `${getApiBaseUrl()}/health`;
      if (url) {
        targetUrl = url.endsWith('/api') ? `${url}/health` : `${url.replace(/\/$/, '')}/api/health`;
      }
      await axios.get(targetUrl, { timeout: 4000 });
      setBackendStatus('connected');
    } catch (err) {
      setBackendStatus('disconnected');
    }
  };

  useEffect(() => {
    checkBackendHealth(backendUrl);
  }, [backendUrl]);

  const handleBackendUrlChange = (e) => {
    const val = e.target.value;
    setBackendUrl(val);
    if (val) {
      localStorage.setItem('custom_backend_url', val);
    } else {
      localStorage.removeItem('custom_backend_url');
    }
  };

  const handleResetToDefaultCloud = () => {
    setBackendUrl('');
    localStorage.removeItem('custom_backend_url');
    checkBackendHealth('');
  };

  const getFormatLabel = (doc) => {
    if (!doc) return 'DOC';
    if (doc.format) return doc.format.toUpperCase();
    const name = (doc.filename || '').toLowerCase();
    if (name.endsWith('.pdf')) return 'PDF';
    if (name.endsWith('.docx') || name.endsWith('.doc')) return 'DOCX';
    if (name.endsWith('.pptx') || name.endsWith('.ppt')) return 'PPTX';
    if (name.endsWith('.xlsx') || name.endsWith('.csv')) return 'XLSX';
    return 'DOC';
  };

  const getUnitDisplay = (doc) => {
    if (!doc) return '';
    if (doc.details) return doc.details;
    if (doc.unit_count && doc.unit_name) {
      return `${doc.unit_count} ${doc.unit_name}`;
    }
    if (doc.format === 'docx' || (doc.filename || '').toLowerCase().endsWith('.docx')) {
      return 'Paragraphs & Tables';
    }
    if (doc.format === 'pptx' || (doc.filename || '').toLowerCase().endsWith('.pptx')) {
      return `${doc.unit_count || 1} Slides`;
    }
    return `${doc.total_pages || doc.unit_count || 1} Pages`;
  };

  return (
    <div className="studio-shell">
      {/* Studio Top Navigation Bar */}
      <header className="studio-navbar">
        <div className="navbar-brand-group">
          <div className="brand-icon-box">
            <Layers size={17} strokeWidth={2} />
          </div>
          <div className="brand-title-wrap">
            <span className="brand-name">DOCUMENT RESEARCH STUDIO</span>
            <span className="brand-tagline">RETRIEVAL & SYNTHESIS</span>
          </div>
        </div>

        <div className="navbar-actions">
          <div className="status-pill" title={`Backend status: ${backendStatus}`}>
            <span className={`status-dot ${backendStatus}`} />
            <span>{backendStatus === 'connected' ? 'Core Online' : backendStatus === 'checking' ? 'Checking' : 'Offline'}</span>
          </div>

          <button 
            type="button" 
            className="icon-button"
            onClick={() => setShowSettings(true)}
            title="Configure System Settings"
          >
            <Settings size={14} />
            <span>Settings</span>
          </button>
        </div>
      </header>

      {/* Settings Modal */}
      {showSettings && (
        <div className="modal-backdrop" onClick={() => setShowSettings(false)}>
          <div className="settings-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <span className="modal-title">System Configuration</span>
              <button 
                type="button" 
                className="action-btn-subtle" 
                onClick={() => setShowSettings(false)}
              >
                <X size={16} />
              </button>
            </div>

            <div className="modal-body">
              <div className="form-field">
                <label className="field-label">
                  <span>OpenAI Synthesis Key (Optional)</span>
                  <Key size={13} style={{ color: 'var(--text-muted)' }} />
                </label>
                <div className="field-input-wrap">
                  <input 
                    type="password"
                    className="field-input"
                    placeholder="sk-... (Leave empty for zero-config Gemini/local pipeline)"
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                  />
                </div>
                <span className="field-hint">
                  Retriever uses local Nomic embeddings and BGE reranking. Synthesis runs via cloud synthesis.
                </span>
              </div>

              <div className="form-field">
                <label className="field-label">
                  <span>Backend Endpoint URL</span>
                  <Server size={13} style={{ color: 'var(--text-muted)' }} />
                </label>
                <div className="field-input-wrap">
                  <input 
                    type="text"
                    className="field-input"
                    placeholder="https://your-api.domain.com/api"
                    value={backendUrl}
                    onChange={handleBackendUrlChange}
                  />
                  {backendUrl && (
                    <button 
                      type="button"
                      onClick={handleResetToDefaultCloud}
                      title="Reset to default cloud server"
                      className="action-btn-subtle"
                    >
                      <RefreshCw size={13} />
                    </button>
                  )}
                </div>
                <span className="field-hint">
                  Default: Active tunnel / cloud backend with 24/7 availability.
                </span>
              </div>
            </div>

            <div className="modal-footer">
              <button 
                type="button" 
                className="btn-primary"
                onClick={() => setShowSettings(false)}
              >
                <Check size={14} />
                <span>Apply & Close</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Main Workspace Layout */}
      {!activeDocument ? (
        <main className="ingestion-hub">
          <div className="hub-hero">
            <div className="hub-classification">
              Multi-Format Analysis • Local Embeddings • Cloud Synthesis
            </div>
            <h1 className="hub-title">Document Intelligence Platform</h1>
            <p className="hub-subtitle">
              Ingest PDF, Word, and PowerPoint files to extract structured strategic dossiers, index visual figures, and execute fact-checked citations without vendor lock-in.
            </p>

            <div className="format-ribbon">
              <span className="format-tag">PDF (Vectorized Text & Tables)</span>
              <span className="format-tag">DOCX (Full AST Extraction)</span>
              <span className="format-tag">PPTX (Slide Outlines)</span>
              <span className="format-tag">Nomic 768d + BGE Reranker</span>
            </div>
          </div>

          <PdfUploader 
            apiKey={apiKey} 
            onPdfUploaded={(doc) => {
              setActiveDocument(doc);
              setViewMode('split');
            }} 
          />
        </main>
      ) : (
        <main style={{ display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden' }}>
          {/* Active Document Header Strip */}
          <div className="workspace-meta-strip">
            <div className="meta-doc-identity">
              <span className="doc-format-badge">
                {getFormatLabel(activeDocument)}
              </span>
              <span className="doc-filename" title={activeDocument.filename}>
                {activeDocument.filename}
              </span>
            </div>

            <div className="meta-stats-group">
              <span className="meta-stat-item">
                Units: <strong>{getUnitDisplay(activeDocument)}</strong>
              </span>
              <span className="meta-stat-item">
                Vectors: <strong>{activeDocument.total_chunks} chunks</strong>
              </span>

              {/* View Mode Controls */}
              <div className="view-mode-toggle">
                <button 
                  type="button" 
                  className={`mode-btn ${viewMode === 'split' ? 'active' : ''}`}
                  onClick={() => setViewMode('split')}
                  title="Dual-Pane Workspace"
                >
                  <Columns size={12} />
                  <span>Split</span>
                </button>
                <button 
                  type="button" 
                  className={`mode-btn ${viewMode === 'dossier' ? 'active' : ''}`}
                  onClick={() => setViewMode('dossier')}
                  title="Executive Dossier Only"
                >
                  <BookOpen size={12} />
                  <span>Dossier</span>
                </button>
                <button 
                  type="button" 
                  className={`mode-btn ${viewMode === 'inquiry' ? 'active' : ''}`}
                  onClick={() => setViewMode('inquiry')}
                  title="Inquiry Console Only"
                >
                  <Terminal size={12} />
                  <span>Inquiry</span>
                </button>
              </div>

              <button 
                type="button" 
                className="icon-button"
                onClick={() => setActiveDocument(null)}
                title="Ingest a different document"
              >
                <PlusCircle size={13} />
                <span>New Document</span>
              </button>
            </div>
          </div>

          {/* Two-Column Studio Workspace */}
          <div className={`studio-workspace-body ${viewMode === 'dossier' ? 'single-dossier' : ''} ${viewMode === 'inquiry' ? 'single-inquiry' : ''}`}>
            {(viewMode === 'split' || viewMode === 'dossier') && (
              <SummaryRoadmapView 
                documentId={activeDocument.document_id} 
                apiKey={apiKey} 
                filename={activeDocument.filename}
              />
            )}

            {(viewMode === 'split' || viewMode === 'inquiry') && (
              <RagChat 
                documentId={activeDocument.document_id} 
                apiKey={apiKey} 
              />
            )}
          </div>
        </main>
      )}
    </div>
  );
}

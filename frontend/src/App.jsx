import React, { useState, useEffect } from 'react';
import PdfUploader from './components/PdfUploader';
import SummaryRoadmapView from './components/SummaryRoadmapView';
import RagChat from './components/RagChat';
import { FileText, MessageSquare, Key, Server, Sparkles, Layers, CheckCircle2, AlertCircle, RefreshCw } from 'lucide-react';
import { getApiBaseUrl } from './api/client';
import axios from 'axios';

export default function App() {
  const [apiKey, setApiKey] = useState(localStorage.getItem('openai_api_key') || '');
  const [backendUrl, setBackendUrl] = useState(localStorage.getItem('custom_backend_url') || '');
  const [backendStatus, setBackendStatus] = useState('checking'); // 'connected', 'disconnected', 'checking'
  const [activeDocument, setActiveDocument] = useState(null);
  const [activeTab, setActiveTab] = useState('summary');

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

  return (
    <div className="app-container">
      <header className="header">
        <div className="brand-badge">
          <Layers size={14} /> Offline Retrieval • Cloud Synthesis
        </div>
        <h1>Document Intelligence Platform</h1>
        <p>Extract structured roadmaps, index visual diagrams, and query documents with grounded citations across PDF, Word, PowerPoint, and Excel.</p>

        {/* Configurations */}
        <div className="config-bar">
          <div className="input-container">
            <Key size={16} style={{ color: '#9ca3af', marginRight: '0.75rem' }} />
            <input 
              type="password"
              placeholder="OpenAI API Key (Optional - leave empty for zero-config local embeddings)"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
            />
          </div>

          <div className="input-container" style={{ position: 'relative' }}>
            <Server size={16} style={{ color: '#6366f1', marginRight: '0.75rem' }} />
            <input 
              type="text"
              placeholder="Cloud Backend (Auto 24/7) — or paste custom endpoint"
              value={backendUrl}
              onChange={handleBackendUrlChange}
            />
            {backendUrl && (
              <button 
                onClick={handleResetToDefaultCloud}
                title="Reset to Default 24/7 Vercel Cloud Server"
                style={{
                  position: 'absolute',
                  right: '100px',
                  background: 'none',
                  border: 'none',
                  color: '#9ca3af',
                  cursor: 'pointer',
                  padding: '4px',
                  display: 'flex',
                  alignItems: 'center'
                }}
              >
                <RefreshCw size={13} />
              </button>
            )}
            <span style={{ position: 'absolute', right: '12px', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
              {backendStatus === 'connected' ? (
                <span style={{ color: '#10b981', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                  <CheckCircle2 size={14} /> Connected
                </span>
              ) : backendStatus === 'disconnected' ? (
                <span style={{ color: '#ef4444', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                  <AlertCircle size={14} /> Disconnected
                </span>
              ) : (
                <span style={{ color: '#9ca3af' }}>Connecting...</span>
              )}
            </span>
          </div>
        </div>
      </header>

      <main>
        <PdfUploader apiKey={apiKey} onPdfUploaded={(doc) => setActiveDocument(doc)} />

        {activeDocument ? (
          <div style={{ marginTop: '2rem' }}>
            <div className="tabs-header">
              <button 
                className={`tab-btn ${activeTab === 'summary' ? 'active' : ''}`}
                onClick={() => setActiveTab('summary')}
              >
                <Sparkles size={16} /> Summary & Roadmap
              </button>
              <button 
                className={`tab-btn ${activeTab === 'chat' ? 'active' : ''}`}
                onClick={() => setActiveTab('chat')}
              >
                <MessageSquare size={16} /> Conversational RAG Q&A
              </button>
            </div>

            {activeTab === 'summary' ? (
              <SummaryRoadmapView documentId={activeDocument.document_id} apiKey={apiKey} />
            ) : (
              <RagChat documentId={activeDocument.document_id} apiKey={apiKey} />
            )}
          </div>
        ) : (
          <div style={{ textAlign: 'center', marginTop: '2.5rem', color: '#6b7280', fontSize: '0.9rem' }}>
            <p>Upload a PDF document above to get started.</p>
          </div>
        )}
      </main>
    </div>
  );
}

import React, { useState } from 'react';
import { summarizePdfApi } from '../api/client';
import ReactMarkdown from 'react-markdown';
import { FileText, Loader2, Copy, Check, BarChart2 } from 'lucide-react';

export default function SummaryRoadmapView({ documentId, apiKey, filename }) {
  const [loading, setLoading] = useState(false);
  const [summaryData, setSummaryData] = useState(null);
  const [error, setError] = useState(null);
  const [copied, setCopied] = useState(false);

  const handleGenerateSummary = async () => {
    if (!documentId) return;
    setLoading(true);
    setError(null);

    try {
      const data = await summarizePdfApi(documentId, apiKey);
      setSummaryData(data.summary_and_roadmap);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to synthesize document dossier.');
    } finally {
      setLoading(false);
    }
  };

  const handleCopyMemo = () => {
    if (!summaryData) return;
    navigator.clipboard.writeText(summaryData);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="dossier-column">
      <div className="column-header">
        <div className="column-heading-wrap">
          <FileText size={15} style={{ color: 'var(--accent-cyan)' }} />
          <h2 className="column-title">Executive Dossier & Strategy</h2>
        </div>

        <div className="column-actions">
          {summaryData && (
            <button 
              type="button" 
              className="icon-button"
              onClick={handleCopyMemo}
              title="Copy executive brief"
            >
              {copied ? <Check size={12} style={{ color: 'var(--accent-emerald)' }} /> : <Copy size={12} />}
              <span>{copied ? 'Copied' : 'Copy Brief'}</span>
            </button>
          )}

          <button 
            type="button"
            className="btn-primary" 
            onClick={handleGenerateSummary} 
            disabled={loading || !documentId}
          >
            {loading ? <Loader2 className="animate-spin" size={14} /> : <BarChart2 size={14} />}
            <span>{summaryData ? 'Re-Analyze Document' : 'Generate Dossier'}</span>
          </button>
        </div>
      </div>

      <div className="dossier-scroll-area">
        {error && (
          <div className="audit-error-card" style={{ marginBottom: '1.25rem' }}>
            <div>
              <div className="audit-error-title">SYNTHESIS FAILED</div>
              <div className="audit-error-desc">{error}</div>
            </div>
          </div>
        )}

        {summaryData ? (
          <div className="dossier-memo">
            <div className="memo-header">
              <div className="memo-kicker">EXECUTIVE BRIEFING & ACTIONABLE ROADMAP</div>
              <h1 className="memo-title">{filename || 'Document Synthesis'}</h1>
            </div>
            <div className="markdown-body">
              <ReactMarkdown>{summaryData}</ReactMarkdown>
            </div>
          </div>
        ) : (
          <div className="memo-empty-state">
            <div className="vault-icon-wrap" style={{ width: 44, height: 44, marginBottom: '1rem' }}>
              <FileText size={20} />
            </div>
            <h3 className="memo-empty-title">Document Indexed & Verified</h3>
            <p className="memo-empty-desc">
              Run executive analysis to compile high-level strategic takeaways, key milestones, and section breakdowns from the ingested text.
            </p>
            <button 
              type="button"
              className="btn-primary"
              onClick={handleGenerateSummary}
              disabled={loading || !documentId}
            >
              {loading ? <Loader2 className="animate-spin" size={14} /> : <BarChart2 size={14} />}
              <span>{loading ? 'Synthesizing Dossier...' : 'Run Executive Analysis'}</span>
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

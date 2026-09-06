import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { Copy, Check, Clock, ShieldCheck } from 'lucide-react';
import SourcePanel from './SourcePanel';

export default function Message({ message }) {
  const [copied, setCopied] = useState(false);
  const isUser = message.role === 'user';

  const handleCopy = () => {
    if (!message.content) return;
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (isUser) {
    return (
      <div className="inquiry-user-entry">
        <div className="inquiry-meta-bar">
          <span className="inquiry-tag">Query / Inquiry</span>
        </div>
        <div className="inquiry-text">
          {message.content}
        </div>
      </div>
    );
  }

  return (
    <div className="finding-entry">
      <div className="finding-meta-bar">
        <div className="finding-tag-group">
          <ShieldCheck size={14} style={{ color: 'var(--accent-cyan)' }} />
          <span className="finding-tag">Grounded Finding</span>
          {message.served_by && (
            <span className="finding-stats">
              • {message.served_by.replace(/_/g, ' ')}
            </span>
          )}
          {message.latency_ms ? (
            <span className="finding-stats">
              <Clock size={11} /> {Math.round(message.latency_ms)}ms
            </span>
          ) : null}
        </div>

        <div className="finding-actions">
          <button 
            type="button" 
            className="action-btn-subtle" 
            onClick={handleCopy} 
            title="Copy finding"
          >
            {copied ? <Check size={13} style={{ color: 'var(--accent-emerald)' }} /> : <Copy size={13} />}
          </button>
        </div>
      </div>

      <div className="markdown-body">
        <ReactMarkdown>
          {message.content}
        </ReactMarkdown>
      </div>

      {message.sources && message.sources.length > 0 && (
        <SourcePanel sources={message.sources} />
      )}
    </div>
  );
}

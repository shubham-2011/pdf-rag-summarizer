import React, { useEffect, useRef } from 'react';
import Message from './Message';
import ErrorMessage from './ErrorMessage';
import { Search, Loader2, ArrowRight } from 'lucide-react';

const PRESET_INQUIRIES = [
  'What is the core premise and conclusion of this document?',
  'List the primary methodologies, findings, and empirical figures.',
  'Identify key risks, open questions, and next steps described.',
  'Summarize the quantitative metrics, tables, and statistics.'
];

export default function MessageList({ messages, loading, error, onRetry, onSelectPrompt }) {
  const scrollRef = useRef(null);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading, error]);

  return (
    <div className="inquiry-feed-viewport">
      {messages.length === 0 && !loading && (
        <div className="inquiry-ledger-empty">
          <div className="ledger-empty-icon">
            <Search size={22} strokeWidth={1.8} />
          </div>
          <h3 className="ledger-empty-title">Document Inquiry & Fact-Checking Console</h3>
          <p className="ledger-empty-desc">
            Submit inquiries to inspect exact page-anchored passages, verify claims, or extract quantitative data.
          </p>

          <div className="preset-queries-ledger">
            {PRESET_INQUIRIES.map((prompt, i) => (
              <div
                key={i}
                className="preset-query-item"
                onClick={() => onSelectPrompt && onSelectPrompt(prompt)}
              >
                <span>{prompt}</span>
                <ArrowRight size={13} style={{ color: 'var(--accent-cyan)', flexShrink: 0 }} />
              </div>
            ))}
          </div>
        </div>
      )}

      {messages.map((msg, index) => (
        <Message key={index} message={msg} />
      ))}

      {loading && (
        <div className="ledger-loading-card">
          <Loader2 size={16} strokeWidth={2} className="animate-spin" style={{ color: 'var(--accent-cyan)' }} />
          <span>Scanning index vectors & synthesizing grounded evidence...</span>
        </div>
      )}

      {error && (
        <ErrorMessage error={error} onRetry={onRetry} />
      )}

      <div ref={scrollRef} />
    </div>
  );
}

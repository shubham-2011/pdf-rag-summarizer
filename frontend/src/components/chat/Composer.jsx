import React, { useRef, useEffect } from 'react';
import { Send, Globe, Square } from 'lucide-react';

export default function Composer({
  inputQuery,
  setInputQuery,
  onSend,
  loading,
  onAbort,
  disabled,
  enableWebSearch,
  setEnableWebSearch
}) {
  const textareaRef = useRef(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 180)}px`;
    }
  }, [inputQuery]);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (inputQuery.trim() && !loading && !disabled) {
        onSend();
      }
    }
  };

  return (
    <form className="composer-form" onSubmit={(e) => { e.preventDefault(); if (inputQuery.trim() && !loading && !disabled) onSend(); }}>
      <div className="composer-box">
        <textarea
          ref={textareaRef}
          className="composer-textarea"
          rows={1}
          placeholder={disabled ? "Upload a document to begin questioning..." : "Ask a question, request an executive summary, or query specific sections..."}
          value={inputQuery}
          onChange={(e) => setInputQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
        />

        <div className="composer-toolbar">
          <label className={`web-search-toggle ${enableWebSearch ? 'active' : ''}`} title="Augment retrieval with real-world web search data">
            <Globe size={13} strokeWidth={1.5} />
            <span>Web Search</span>
            <input 
              type="checkbox" 
              checked={enableWebSearch} 
              onChange={(e) => setEnableWebSearch(e.target.checked)}
              className="sr-only"
            />
          </label>

          <div className="composer-right-actions">
            <span className="composer-hint mono-label">
              ↵ Send · Shift+↵ Newline
            </span>

            {loading ? (
              <button 
                type="button" 
                className="abort-btn" 
                onClick={onAbort} 
                title="Stop generating response"
              >
                <Square size={13} strokeWidth={2} fill="currentColor" />
                <span>Stop</span>
              </button>
            ) : (
              <button 
                type="submit" 
                className="send-btn" 
                disabled={disabled || !inputQuery.trim()}
                title="Send message"
              >
                <Send size={14} strokeWidth={1.5} />
              </button>
            )}
          </div>
        </div>
      </div>
    </form>
  );
}

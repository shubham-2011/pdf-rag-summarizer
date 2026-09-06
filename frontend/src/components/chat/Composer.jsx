import React, { useRef, useEffect } from 'react';
import { CornerDownLeft, Globe, Square } from 'lucide-react';

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
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 140)}px`;
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
    <form className="inquiry-composer-area" onSubmit={(e) => { e.preventDefault(); if (inputQuery.trim() && !loading && !disabled) onSend(); }}>
      <div className="query-input-box">
        <textarea
          ref={textareaRef}
          className="query-textarea"
          rows={1}
          placeholder={disabled ? "Ingest a document to begin questioning..." : "Enter inquiry, verify specific clauses, or cross-examine facts..."}
          value={inputQuery}
          onChange={(e) => setInputQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
        />

        <div className="query-toolbar">
          <label className={`web-toggle-label ${enableWebSearch ? 'active' : ''}`} title="Augment offline document retrieval with live web corroboration">
            <Globe size={12} strokeWidth={1.7} />
            <span>Web Corroboration</span>
            <input 
              type="checkbox" 
              checked={enableWebSearch} 
              onChange={(e) => setEnableWebSearch(e.target.checked)}
              className="sr-only"
            />
          </label>

          <div className="query-toolbar-right">
            <span className="keyboard-shortcut-hint">
              ↵ Query · Shift+↵ Line
            </span>

            {loading ? (
              <button 
                type="button" 
                className="btn-query-stop" 
                onClick={onAbort} 
                title="Halt analysis"
              >
                <Square size={11} strokeWidth={2} fill="currentColor" />
                <span>Halt</span>
              </button>
            ) : (
              <button 
                type="submit" 
                className="btn-query-run" 
                disabled={disabled || !inputQuery.trim()}
                title="Run inquiry"
              >
                <span>Run</span>
                <CornerDownLeft size={12} strokeWidth={2} />
              </button>
            )}
          </div>
        </div>
      </div>
    </form>
  );
}

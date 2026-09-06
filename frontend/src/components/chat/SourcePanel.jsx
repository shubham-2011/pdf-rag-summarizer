import React, { useState } from 'react';
import { ChevronDown, ChevronRight, Layers } from 'lucide-react';
import SourceCard from './SourceCard';

export default function SourcePanel({ sources }) {
  const [isOpen, setIsOpen] = useState(false);
  if (!sources || sources.length === 0) return null;

  const citedPages = Array.from(new Set(
    sources
      .map(s => (s.page === '🌐 Web Search' || s.page === 'web') ? 'web' : `p.${s.page}`)
      .filter(Boolean)
  ));
  
  const summaryPages = citedPages.join(', ');

  return (
    <div className="source-panel-container">
      <button 
        type="button"
        className="source-panel-toggle"
        onClick={() => setIsOpen(!isOpen)}
        aria-expanded={isOpen}
      >
        <span className="source-panel-toggle-left">
          <Layers size={13} strokeWidth={1.5} className="text-accent" />
          <span className="source-count-label">
            {sources.length} {sources.length === 1 ? 'source' : 'sources'}
          </span>
          <span className="source-pages-pill mono-label">
            {summaryPages}
          </span>
        </span>
        <span className="source-panel-toggle-icon">
          {isOpen ? <ChevronDown size={14} strokeWidth={1.5} /> : <ChevronRight size={14} strokeWidth={1.5} />}
        </span>
      </button>

      {isOpen && (
        <div className="source-cards-grid animate-fade-in">
          {sources.map((src, idx) => (
            <SourceCard key={idx} source={src} />
          ))}
        </div>
      )}
    </div>
  );
}

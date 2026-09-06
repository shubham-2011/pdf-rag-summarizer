import React, { useState } from 'react';
import { ChevronDown, ChevronRight, FileCheck } from 'lucide-react';
import SourceCard from './SourceCard';

export default function SourcePanel({ sources }) {
  const [isOpen, setIsOpen] = useState(false);
  if (!sources || sources.length === 0) return null;

  const citedUnits = Array.from(new Set(
    sources
      .map(s => (s.page === '🌐 Web Search' || s.page === 'web') ? 'web' : `p.${s.page}`)
      .filter(Boolean)
  ));
  
  const unitList = citedUnits.join(', ');

  return (
    <div className="evidence-panel">
      <button 
        type="button"
        className="evidence-panel-header"
        onClick={() => setIsOpen(!isOpen)}
        aria-expanded={isOpen}
      >
        <div className="evidence-header-left">
          <FileCheck size={13} strokeWidth={1.7} style={{ color: 'var(--accent-cyan)' }} />
          <span>Cited Sources:</span>
          <span className="evidence-count-pill">
            {sources.length} {sources.length === 1 ? 'passage' : 'passages'}
          </span>
          {unitList && (
            <span className="mono" style={{ color: 'var(--text-muted)', fontSize: '0.725rem' }}>
              [{unitList}]
            </span>
          )}
        </div>
        <div>
          {isOpen ? <ChevronDown size={14} strokeWidth={1.7} /> : <ChevronRight size={14} strokeWidth={1.7} />}
        </div>
      </button>

      {isOpen && (
        <div className="evidence-grid">
          {sources.map((src, idx) => (
            <SourceCard key={idx} source={src} />
          ))}
        </div>
      )}
    </div>
  );
}

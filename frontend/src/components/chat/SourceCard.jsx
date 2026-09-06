import React from 'react';
import { BookOpen, Globe, FileText } from 'lucide-react';

export default function SourceCard({ source }) {
  if (!source) return null;

  const isWeb = source.page === '🌐 Web Search' || source.page === 'web' || !!source.url;
  const pageLabel = isWeb ? 'WEB' : (typeof source.page === 'string' && source.page.startsWith('p.') ? source.page : `p.${source.page || 1}`);
  const sectionLabel = source.section && source.section !== 'GENERAL' ? source.section : null;
  
  const formatSnippet = (text, maxLen = 220) => {
    if (!text) return '';
    const clean = text.replace(/\s+/g, ' ').trim();
    if (clean.length <= maxLen) return clean;
    const truncated = clean.substring(0, maxLen);
    const lastSpace = truncated.lastIndexOf(' ');
    return (lastSpace > 40 ? truncated.substring(0, lastSpace) : truncated) + '...';
  };

  return (
    <div className="evidence-card">
      <div className="evidence-card-header">
        <span className={`evidence-unit-badge ${isWeb ? 'web' : ''}`}>
          {isWeb ? <Globe size={11} strokeWidth={1.7} /> : <BookOpen size={11} strokeWidth={1.7} />}
          <span>{pageLabel}</span>
        </span>
        {sectionLabel && (
          <span className="evidence-section-label" title={sectionLabel}>
            § {sectionLabel}
          </span>
        )}
        <span className="mono" style={{ fontSize: '0.7rem', color: '#64748b', marginLeft: 'auto' }}>
          {source.file || 'Document Passage'}
        </span>
      </div>
      <div className="evidence-excerpt">
        “{formatSnippet(source.snippet)}”
      </div>
    </div>
  );
}

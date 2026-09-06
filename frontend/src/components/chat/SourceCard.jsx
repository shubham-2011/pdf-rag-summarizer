import React from 'react';
import { BookOpen, Globe } from 'lucide-react';

export default function SourceCard({ source }) {
  if (!source) return null;

  const isWeb = source.page === '🌐 Web Search' || source.page === 'web' || !!source.url;
  const pageLabel = isWeb ? 'WEB' : `p.${source.page || 1}`;
  const sectionLabel = source.section && source.section !== 'GENERAL' ? source.section : null;
  
  const formatSnippet = (text, maxLen = 150) => {
    if (!text) return '';
    const clean = text.replace(/\s+/g, ' ').trim();
    if (clean.length <= maxLen) return clean;
    const truncated = clean.substring(0, maxLen);
    const lastSpace = truncated.lastIndexOf(' ');
    return (lastSpace > 30 ? truncated.substring(0, lastSpace) : truncated) + '...';
  };

  return (
    <div className="source-card">
      <div className="source-card-header">
        <span className={`source-badge ${isWeb ? 'web-badge' : 'page-badge'}`}>
          {isWeb ? <Globe size={11} strokeWidth={1.5} /> : <BookOpen size={11} strokeWidth={1.5} />}
          <span className="mono-label">{pageLabel}</span>
        </span>
        {sectionLabel && (
          <span className="source-section-tag" title={sectionLabel}>
            {sectionLabel}
          </span>
        )}
        <span className="source-filename" title={source.file || 'Document'}>
          {source.file || 'Document'}
        </span>
      </div>
      <div className="source-snippet">
        "{formatSnippet(source.snippet)}"
      </div>
    </div>
  );
}
